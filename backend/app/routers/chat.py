import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_ro_session, rw_session
from app.agent.chat import run_chat
from app.models.chat import AiChatMessage, AiChatSession
from app.models.survey import Survey

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/surveys", tags=["chat"])

_ANON_USER = "anonymous"


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[int] = None
    reportContext: Optional[dict] = None


@router.post("/{survey_number}/chat")
async def chat(
    survey_number: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_ro_session),
):
    row = await db.execute(
        select(Survey.id).where(
            Survey.survey_number == survey_number,
            Survey.is_deleted == False,  # noqa: E712
        )
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")

    async def event_stream():
        try:
            async for event in run_chat(
                survey_number, _ANON_USER, body.message, body.sessionId, body.reportContext
            ):
                data = event["data"]
                if not isinstance(data, str):
                    data = json.dumps(data, ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {data}\n\n"
        except Exception as exc:
            logger.error("Chat stream error: %s", exc)
            yield f"event: error\ndata: {json.dumps(str(exc))}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{survey_number}/chat/history")
async def chat_history(
    survey_number: str,
    sessionId: int,
) -> list[dict]:
    async with rw_session() as db:
        session_row = await db.execute(
            select(AiChatSession).where(
                AiChatSession.id == sessionId,
                AiChatSession.survey_number == survey_number,
            )
        )
        session = session_row.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        messages = (
            await db.execute(
                select(AiChatMessage)
                .where(AiChatMessage.session_id == sessionId)
                .order_by(AiChatMessage.created_at)
            )
        ).scalars().all()

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "toolName": m.tool_name,
            "language": m.language,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.get("/{survey_number}/chat/sessions")
async def list_sessions(survey_number: str) -> list[dict]:
    async with rw_session() as db:
        rows = (
            await db.execute(
                select(AiChatSession)
                .where(AiChatSession.survey_number == survey_number)
                .order_by(AiChatSession.created_at.desc())
            )
        ).scalars().all()

    return [
        {"id": s.id, "createdAt": s.created_at.isoformat() if s.created_at else None}
        for s in rows
    ]
