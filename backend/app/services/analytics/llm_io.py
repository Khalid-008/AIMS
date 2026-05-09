"""LLM I/O wrapper with two retry policies.

- ``call_json``: single LLM call returning parsed JSON. Transport errors retry
  with jittered exponential backoff (3 attempts). JSON parse errors raise
  ``LlmJsonError`` so callers can decide whether to split-and-retry.
- ``call_batch_with_split_retry``: per-batch wrapper. JSON parse errors trigger
  splitting the batch in halves down to ``min_batch``; transport errors are
  retried inside ``call_json``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any, Awaitable, Callable, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_keyword_extraction_model

logger = logging.getLogger(__name__)


class LlmJsonError(Exception):
    """The model returned text that could not be parsed as the expected JSON shape."""


class LlmTransportError(Exception):
    """Network/HTTP-level failure talking to the LLM endpoint."""


_TRANSPORT_RETRYABLE = (
    asyncio.TimeoutError,
    ConnectionError,
)


def _extract_json(text: str, root: Literal["array", "object"]) -> Any:
    if not text:
        raise LlmJsonError("empty response")
    pattern = r"\[[\s\S]*\]" if root == "array" else r"\{[\s\S]*\}"
    match = re.search(pattern, text)
    if not match:
        raise LlmJsonError(f"no JSON {root} found in response")
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise LlmJsonError(f"invalid JSON {root}: {exc}") from exc


async def call_json(
    user_prompt: str,
    *,
    semaphore: asyncio.Semaphore,
    json_root: Literal["array", "object"] = "array",
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.1,
    transport_retries: int = 3,
) -> Any:
    """One LLM call returning parsed JSON.

    Retries transport errors with jittered backoff. Raises ``LlmJsonError``
    on parse failure (so callers can split-and-retry per their policy).
    """
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=user_prompt))

    base_model = get_keyword_extraction_model()
    model = base_model.bind(max_tokens=max_tokens, temperature=temperature)

    last_exc: Exception | None = None
    for attempt in range(1, transport_retries + 1):
        try:
            async with semaphore:
                response = await model.ainvoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            return _extract_json(content, json_root)
        except LlmJsonError:
            raise
        except _TRANSPORT_RETRYABLE as exc:
            last_exc = exc
        except Exception as exc:  # broad: providers raise many unrelated types
            text = str(exc).lower()
            # Common transient signatures
            if any(s in text for s in ("timeout", "timed out", "429", "rate limit", "5xx", "503", "502", "connection")):
                last_exc = exc
            else:
                raise LlmTransportError(str(exc)) from exc

        if attempt < transport_retries:
            delay = (2 ** (attempt - 1)) * 2.0 + random.uniform(0, 1.0)
            logger.warning("LLM transport retry %d after %.1fs: %s", attempt, delay, last_exc)
            await asyncio.sleep(delay)

    raise LlmTransportError(f"transport retries exhausted: {last_exc}")


async def call_batch_with_split_retry(
    items: list[dict],
    build_prompt: Callable[[list[dict]], str],
    *,
    semaphore: asyncio.Semaphore,
    json_root: Literal["array", "object"] = "array",
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    min_batch: int = 12,
    parse_items: Callable[[Any, list[dict]], list[Any]] | None = None,
) -> tuple[list[Any], list[dict]]:
    """Run an LLM call over ``items``; on JSON parse failure split the batch in halves.

    Returns (parsed_items, failed_items_that_could_not_be_parsed_at_min_batch).

    ``parse_items`` is an optional adapter that turns the raw parsed JSON +
    submitted items into an ordered list of per-item results. If omitted, the
    parsed JSON is expected to already be a list of length ``len(items)``.
    """
    parsed: list[Any] = []
    failed: list[dict] = []

    async def _run(batch: list[dict]) -> None:
        if not batch:
            return
        try:
            raw = await call_json(
                build_prompt(batch),
                semaphore=semaphore,
                json_root=json_root,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except LlmJsonError as exc:
            if len(batch) <= min_batch:
                logger.warning("min batch size hit after split retries: %s; %d items lost", exc, len(batch))
                failed.extend(batch)
                return
            mid = len(batch) // 2
            await _run(batch[:mid])
            await _run(batch[mid:])
            return
        except LlmTransportError as exc:
            logger.warning("transport failure on batch of %d: %s", len(batch), exc)
            failed.extend(batch)
            return

        if parse_items is not None:
            try:
                items_out = parse_items(raw, batch)
            except Exception as exc:  # noqa: BLE001 — adapter errors treated like JSON errors
                if len(batch) <= min_batch:
                    failed.extend(batch)
                    return
                mid = len(batch) // 2
                await _run(batch[:mid])
                await _run(batch[mid:])
                return
            parsed.extend(items_out)
        else:
            if not isinstance(raw, list):
                if len(batch) <= min_batch:
                    failed.extend(batch)
                    return
                mid = len(batch) // 2
                await _run(batch[:mid])
                await _run(batch[mid:])
                return
            parsed.extend(raw)

    await _run(items)
    return parsed, failed


def split_by_char_budget(items: list[dict], char_field: str, budget: int) -> list[list[dict]]:
    """Greedy split: pack items into sub-batches whose summed char_field length <= budget."""
    out: list[list[dict]] = []
    current: list[dict] = []
    running = 0
    for it in items:
        size = len(it.get(char_field, "") or "")
        if current and running + size > budget:
            out.append(current)
            current = []
            running = 0
        current.append(it)
        running += size
    if current:
        out.append(current)
    return out
