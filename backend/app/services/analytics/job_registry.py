"""In-process registry of running analytics-report tasks.

Each report has a queue (live events for SSE consumers attached now) and a
history list (for late-attaching consumers to replay). Progress events are
streamed live-only and not stored in history to bound memory.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

_HISTORY_CAP = 200
_LIVE_ONLY_EVENTS = {"analysis_progress", "heartbeat"}


@dataclass
class JobHandle:
    report_id: int
    queue: asyncio.Queue[dict | None]
    task: asyncio.Task | None = None
    history: list[dict] = field(default_factory=list)
    done: bool = False


_jobs: dict[int, JobHandle] = {}


def reserve(report_id: int, queue: asyncio.Queue) -> JobHandle:
    """Synchronously reserve a slot for ``report_id`` BEFORE creating the task.

    Synchronous so callers can be certain the registry sees the report_id
    before any event is emitted by the worker task.
    """
    handle = JobHandle(report_id=report_id, queue=queue)
    _jobs[report_id] = handle
    return handle


def attach_task(report_id: int, task: asyncio.Task) -> None:
    handle = _jobs.get(report_id)
    if handle is not None:
        handle.task = task


def get(report_id: int) -> JobHandle | None:
    return _jobs.get(report_id)


async def append_event(report_id: int, event: dict[str, Any]) -> None:
    handle = get(report_id)
    if handle is None:
        return
    if event.get("event") not in _LIVE_ONLY_EVENTS:
        handle.history.append(event)
        if len(handle.history) > _HISTORY_CAP:
            del handle.history[: len(handle.history) - _HISTORY_CAP]
    try:
        await handle.queue.put(event)
    except Exception:
        pass


async def close(report_id: int) -> None:
    """Push the sentinel that ends SSE streams listening to this report."""
    handle = get(report_id)
    if handle is None:
        return
    handle.done = True
    try:
        await handle.queue.put(None)
    except Exception:
        pass


def cleanup(report_id: int) -> None:
    _jobs.pop(report_id, None)


def schedule_cleanup(report_id: int, delay_seconds: int = 300) -> None:
    async def _later() -> None:
        await asyncio.sleep(delay_seconds)
        cleanup(report_id)

    asyncio.create_task(_later(), name=f"analytics-cleanup-{report_id}")
