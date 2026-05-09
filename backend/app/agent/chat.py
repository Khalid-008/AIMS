"""
LangGraph-based ReAct agent loop.

Yields SSE-compatible dicts:
  {"event": "token",       "data": "<json-encoded text chunk>"}
  {"event": "tool_call",   "data": {"name": ..., "args": ...}}
  {"event": "tool_result", "data": {"name": ..., "result": ...}}
  {"event": "heartbeat",   "data": "thinking"}
  {"event": "error",       "data": "<json-encoded message>"}
  {"event": "done",        "data": "<session_id>"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy import select

from app.agent.llm import get_chat_model, get_langfuse_handler
from app.agent.prompt import build_system_prompt
from app.agent.tools import build_tools
from app.db import rw_session
from app.models.chat import AiChatMessage, AiChatSession
from app.services.language import detect_language

logger = logging.getLogger(__name__)


async def _get_or_create_session(survey_number: str, user_id: str, session_id: int | None) -> int:
    async with rw_session() as db:
        if session_id:
            row = await db.execute(
                select(AiChatSession).where(
                    AiChatSession.id == session_id,
                    AiChatSession.survey_number == survey_number,
                    AiChatSession.user_id == user_id,
                )
            )
            session = row.scalar_one_or_none()
            if session:
                return session.id

        session = AiChatSession(
            survey_number=survey_number,
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session.id


async def _save_message(
    session_id: int,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_args: dict | None = None,
    language: str | None = None,
) -> None:
    async with rw_session() as db:
        msg = AiChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            language=language,
            created_at=datetime.utcnow(),
        )
        db.add(msg)
        await db.commit()


async def _load_history(session_id: int) -> list:
    """Load prior conversation as LangChain messages (user/assistant only)."""
    async with rw_session() as db:
        rows = (
            await db.execute(
                select(AiChatMessage)
                .where(AiChatMessage.session_id == session_id)
                .order_by(AiChatMessage.created_at)
            )
        ).scalars().all()

    messages = []
    for m in rows:
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant" and m.content:
            messages.append(AIMessage(content=m.content))
    return messages


async def run_chat(
    survey_number: str,
    user_id: str,
    user_message: str,
    session_id: int | None,
    report_context: dict | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    language = detect_language(user_message)
    sid = await _get_or_create_session(survey_number, user_id, session_id)
    await _save_message(sid, "user", user_message, language=language)

    # history includes the just-saved user message
    history = await _load_history(sid)
    system_prompt = build_system_prompt(survey_number, language, report_context)

    model = get_chat_model()
    tools = build_tools(survey_number)

    # prompt prepends the system message to the message list on every agent step
    agent = create_react_agent(model, tools, prompt=system_prompt)

    # Use mutable containers to share state with nested async functions
    state: dict[str, Any] = {
        "full_answer": "",
        "last_heartbeat_time": 0.0,
    }
    heartbeat_interval = 0.5  # seconds between heartbeat events during thinking

    async def _event_producer(queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        """Produce events from astream_events into the queue."""
        langfuse_handler = get_langfuse_handler()
        try:
            async for event in agent.astream_events(
                {"messages": history},
                version="v2",
                config={"callbacks": [langfuse_handler]},
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = ""
                    if isinstance(chunk.content, str):
                        text = chunk.content
                    elif isinstance(chunk.content, list):
                        for item in chunk.content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text += item.get("text", "")
                    if text:
                        state["full_answer"] += text
                        yield_event = {"event": "token", "data": json.dumps(text, ensure_ascii=False)}
                    else:
                        # Emit heartbeat when chunks arrive but contain no user-visible text
                        # (covers Qwen3 thinking-mode with reasoning_content only)
                        now = time.monotonic()
                        if now - state["last_heartbeat_time"] >= heartbeat_interval:
                            state["last_heartbeat_time"] = now
                            yield_event = {"event": "heartbeat", "data": "thinking"}
                        else:
                            yield_event = None  # skip throttled heartbeat
                    if yield_event is not None:
                        await queue.put(yield_event)

                elif kind == "on_tool_start":
                    name = event.get("name", "")
                    args = event["data"].get("input") or {}
                    await queue.put({"event": "tool_call", "data": {"name": name, "args": args}})

                elif kind == "on_tool_end":
                    name = event.get("name", "")
                    output = event["data"].get("output", "")
                    if not isinstance(output, str):
                        output = json.dumps(output, ensure_ascii=False, default=str)
                    await queue.put({"event": "tool_result", "data": {"name": name, "result": output}})
                    await _save_message(sid, "tool", output, tool_name=name)
        except Exception as exc:
            await queue.put({"event": "error", "data": json.dumps(str(exc))})
        finally:
            await queue.put(None)  # sentinel to signal completion

    try:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)
        producer_task = asyncio.create_task(_event_producer(queue))
        heartbeat_task: asyncio.Task | None = None

        async def _background_heartbeat() -> None:
            """Belt-and-suspenders: emit a heartbeat every 5s even if provider is silent."""
            while True:
                await asyncio.sleep(5)
                await queue.put({"event": "heartbeat", "data": "thinking"})

        heartbeat_task = asyncio.create_task(_background_heartbeat())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass

    except Exception as exc:
        logger.error("Agent error for session %s: %s", sid, exc, exc_info=True)
        yield {"event": "error", "data": json.dumps(str(exc))}

    if state["full_answer"]:
        await _save_message(sid, "assistant", state["full_answer"], language=language)
    yield {"event": "done", "data": str(sid)}