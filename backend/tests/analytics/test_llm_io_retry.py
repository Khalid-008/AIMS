"""``call_batch_with_split_retry`` retry policies."""
import asyncio

import pytest

from app.services.analytics import llm_io
from app.services.analytics.llm_io import LlmJsonError, call_batch_with_split_retry


@pytest.mark.asyncio
async def test_split_on_json_error_until_success(monkeypatch):
    """First call raises LlmJsonError; halves succeed."""
    call_log: list[int] = []

    async def fake_call_json(prompt, **kw):
        # Count the number of items implied by the answers_block
        n = prompt.count("[")
        call_log.append(n)
        if n > 4:
            raise LlmJsonError("bad json")
        return [{"answer_id": i, "ok": True} for i in range(n)]

    def parse_items(raw, batch):
        # match by length
        return raw[: len(batch)]

    monkeypatch.setattr(llm_io, "call_json", fake_call_json)

    items = [{"answer_id": i, "answer": f"[{i}]"} for i in range(8)]
    sem = asyncio.Semaphore(4)

    parsed, failed = await call_batch_with_split_retry(
        items,
        build_prompt=lambda batch: "".join(it["answer"] for it in batch),
        semaphore=sem,
        json_root="array",
        min_batch=2,
        parse_items=parse_items,
    )
    # 8 items split twice eventually succeed in halves of 4
    assert len(parsed) == 8
    assert failed == []


@pytest.mark.asyncio
async def test_min_batch_failure_collects_items(monkeypatch):
    """When min_batch reached and JSON still fails, items become 'failed'."""

    async def always_fail(prompt, **kw):
        raise LlmJsonError("nope")

    monkeypatch.setattr(llm_io, "call_json", always_fail)

    items = [{"answer_id": i, "answer": f"[{i}]"} for i in range(4)]
    sem = asyncio.Semaphore(4)

    parsed, failed = await call_batch_with_split_retry(
        items,
        build_prompt=lambda b: "x",
        semaphore=sem,
        json_root="array",
        min_batch=4,
        parse_items=lambda raw, batch: raw,
    )
    assert parsed == []
    assert len(failed) == 4
