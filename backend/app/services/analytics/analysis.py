"""Analysis: per-answer LLM analysis, batched."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.config import settings
from app.services.analytics.data_loader import TextAnswer
from app.services.analytics.llm_io import call_batch_with_split_retry, split_by_char_budget
from app.services.analytics.prompts import ANALYSIS_SYSTEM, ANALYSIS_USER_TEMPLATE
from app.services.analytics.schemas import AnswerAnalysis

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    per_answer: list[AnswerAnalysis]
    failed_answer_ids: list[int]
    llm_calls: int
    failure_ratio: float


def _build_prompt(question_en: str, question_ar: str) -> Callable[[list[dict]], str]:
    def build(batch: list[dict]) -> str:
        block = "\n".join(f"[{a['answer_id']}] {a['answer']}" for a in batch)
        return ANALYSIS_USER_TEMPLATE.format(
            question_en=question_en or "(none)",
            question_ar=question_ar or "(none)",
            n=len(batch),
            answers_block=block,
        )

    return build


def _parse_items(raw, batch: list[dict]) -> list[AnswerAnalysis]:
    if not isinstance(raw, list):
        raise ValueError("expected JSON array")
    by_id = {a["answer_id"]: a for a in batch}
    out: list[AnswerAnalysis] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        aid = item.get("answer_id")
        if aid is None or int(aid) not in by_id:
            continue
        try:
            out.append(AnswerAnalysis.model_validate(item))
        except Exception as exc:  # noqa: BLE001 — drop malformed rows, keep others
            logger.debug("dropping malformed AnswerAnalysis for %s: %s", aid, exc)
    if len(out) < max(1, len(batch) // 2):
        # too few rows parsed — let caller treat as a parse failure and split
        raise ValueError(f"parsed only {len(out)}/{len(batch)} answers")
    return out


async def run_analysis(
    *,
    question_en: str | None,
    question_ar: str | None,
    answers: list[TextAnswer],
    semaphore: asyncio.Semaphore,
    on_batch_complete: Callable[[int, int, int], Awaitable[None]] | None = None,
) -> AnalysisResult:
    if not answers:
        return AnalysisResult(per_answer=[], failed_answer_ids=[], llm_calls=0, failure_ratio=0.0)

    items = [{"answer_id": a.answer_id, "answer": a.answer} for a in answers]
    char_budget = settings.nlp_batch_char_budget
    nominal_size = settings.nlp_batch_size

    # First split by char budget to avoid input-token overflow on long Arabic answers,
    # then split each char-bounded chunk into nominal-size sub-batches.
    char_chunks = split_by_char_budget(items, "answer", char_budget)
    sub_batches: list[list[dict]] = []
    for chunk in char_chunks:
        for i in range(0, len(chunk), nominal_size):
            sub_batches.append(chunk[i : i + nominal_size])

    total_batches = len(sub_batches)
    completed = 0
    parsed: list[AnswerAnalysis] = []
    failed: list[dict] = []
    build = _build_prompt(question_en or "", question_ar or "")
    llm_calls = 0

    async def _do_batch(batch: list[dict]) -> None:
        nonlocal llm_calls, completed
        before_failed = len(failed)
        before_parsed = len(parsed)
        chunk_parsed, chunk_failed = await call_batch_with_split_retry(
            batch,
            build,
            semaphore=semaphore,
            json_root="array",
            system_prompt=ANALYSIS_SYSTEM,
            max_tokens=4096,
            min_batch=settings.nlp_batch_min_split,
            parse_items=_parse_items,
        )
        parsed.extend(chunk_parsed)
        failed.extend(chunk_failed)
        llm_calls += 1
        completed += 1
        if on_batch_complete is not None:
            failed_count = len(failed) - before_failed + 0
            await on_batch_complete(completed, total_batches, failed_count)
        del before_failed, before_parsed

    await asyncio.gather(*[_do_batch(b) for b in sub_batches])

    failed_ids = [int(it["answer_id"]) for it in failed]
    failure_ratio = (len(failed_ids) / len(answers)) if answers else 0.0
    return AnalysisResult(
        per_answer=parsed,
        failed_answer_ids=failed_ids,
        llm_calls=llm_calls,
        failure_ratio=failure_ratio,
    )
