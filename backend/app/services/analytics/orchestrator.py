"""Top-level analytics-report pipeline orchestrator.

Resolves auto-language via a probe, computes the input hash, checks the cache,
and either returns immediately (cache hit) or schedules a background task that
runs SQL + NLP branches in parallel and emits SSE events.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import date, datetime, time as dtime
from typing import Literal

from app.config import settings
from app.services.analytics import job_registry, repository
from app.services.analytics.data_loader import (
    QuestionMeta,
    get_recent_submission_ids,
    load_questions,
    load_text_answers,
    resolve_survey,
    sample_text_for_language_probe,
    total_submission_count,
)
from app.services.analytics.hashing import compute_input_hash
from app.services.analytics.schemas import (
    QuestionNlpResult,
    QuestionSqlResult,
    ReportLanguage,
    SynthesisInput,
)
from app.services.analytics.aggregation import aggregate_question
from app.services.analytics.analysis import run_analysis
from app.services.analytics.clustering import build_entity_map, build_subtopic_map
from app.services.analytics.sql_branch import run_sql_branch
from app.services.analytics.summarization import run_summarization
from app.services.analytics.synthesis import (
    assemble_payload,
    empty_synthesis,
    run_synthesis,
)
from app.services.language import detect_language

logger = logging.getLogger(__name__)

LanguageRequest = Literal["ar", "en", "auto"]


def _to_window(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    """Convert YYYY-MM-DD inputs to a [start-of-day, end-of-day] datetime window."""
    df = datetime.combine(date_from, dtime.min) if date_from is not None else None
    dt = datetime.combine(date_to, dtime.max) if date_to is not None else None
    return df, dt


async def _probe_language(
    survey_number: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> ReportLanguage:
    """Decide the report language for ``auto`` requests.

    Counts Arabic-script presence across a 50-row sample of TEXT_INPUT answers.
    Tie / no text → "ar" per spec.
    """
    sample = await sample_text_for_language_probe(
        survey_number,
        limit=50,
        date_from=date_from,
        date_to=date_to,
        submission_ids=submission_ids,
    )
    if not sample:
        return "ar"
    counts: Counter[str] = Counter()
    for s in sample:
        counts[detect_language(s)] += 1
    return "ar" if counts["ar"] >= counts["en"] else "en"


async def _emit(report_id: int, event: str, data: dict | None = None) -> None:
    await job_registry.append_event(report_id, {"event": event, "data": data or {}})


async def _process_text_question(
    *,
    report_id: int,
    q: QuestionMeta,
    report_language: ReportLanguage,
    analysis_sem: asyncio.Semaphore,
    summary_sem: asyncio.Semaphore,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> tuple[QuestionNlpResult | None, int]:
    """Returns (nlp_result_or_None, llm_calls)."""
    answers = await load_text_answers(
        q.question_id,
        date_from=date_from,
        date_to=date_to,
        submission_ids=submission_ids,
    )
    if not answers:
        return (
            QuestionNlpResult(
                question_id=q.question_id,
                question_text=q.question_ar or q.question_en or "",
                valid_count=0,
                sarcastic_count=0,
                sentiment_distribution={"positive": 0, "neutral": 0, "negative": 0, "mixed": 0},
            ),
            0,
        )

    async def _on_batch(done: int, total: int, failed: int) -> None:
        await _emit(
            report_id,
            "analysis_progress",
            {"questionId": q.question_id, "completedBatches": done, "totalBatches": total, "failedAnswers": failed},
        )

    s1 = await run_analysis(
        question_en=q.question_en,
        question_ar=q.question_ar,
        answers=answers,
        semaphore=analysis_sem,
        on_batch_complete=_on_batch,
    )
    await _emit(
        report_id,
        "analysis_done",
        {
            "questionId": q.question_id,
            "validCount": sum(1 for a in s1.per_answer if a.is_valid),
            "failureRatio": round(s1.failure_ratio, 3),
            "partial": s1.failure_ratio > 0.5,
        },
    )

    sub_map, sub_calls = await build_subtopic_map(
        s1.per_answer, target_language=report_language, semaphore=summary_sem
    )
    ent_map, ent_calls = await build_entity_map(
        s1.per_answer, target_language=report_language, semaphore=summary_sem
    )
    await _emit(report_id, "clustering_done", {"questionId": q.question_id})

    nlp = aggregate_question(
        question_id=q.question_id,
        question_text=q.question_ar or q.question_en or "",
        per_answer=s1.per_answer,
        subtopic_map=sub_map,
        entity_map=ent_map,
        failure_ratio=s1.failure_ratio,
    )
    await _emit(
        report_id,
        "aggregation_done",
        {
            "questionId": q.question_id,
            "topTopicsCount": len(nlp.top_topics),
            "topEntitiesCount": len(nlp.top_entities),
        },
    )

    summary, summary_calls = await run_summarization(
        nlp, report_language=report_language, semaphore=summary_sem
    )
    nlp.narrative_summary = summary
    await _emit(report_id, "summarization_done", {"questionId": q.question_id, "summaryChars": len(summary)})
    await _emit(report_id, "nlp_question_done", {"questionId": q.question_id})

    return nlp, s1.llm_calls + sub_calls + ent_calls + summary_calls


async def _run_pipeline(
    report_id: int,
    survey_number: str,
    report_language: ReportLanguage,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submissions_limit: int | None = None,
    submission_ids: list[str] | None = None,
) -> None:
    started = time.monotonic()
    llm_calls = 0
    try:
        await repository.mark_running(report_id)

        survey_id, subject_en, subject_ar = await resolve_survey(survey_number)
        questions = await load_questions(survey_number)

        text_questions = [q for q in questions if q.type == "TEXT_INPUT"]
        sql_questions = [
            q for q in questions if q.type in {"MULTIPLE_CHOICE", "YES_NO", "DROPDOWN", "EMOJIS"}
        ]

        await _emit(
            report_id,
            "started",
            {
                "reportId": report_id,
                "reportLanguage": report_language,
                "totalQuestions": len(questions),
                "textQuestions": len(text_questions),
                "sqlQuestions": len(sql_questions),
            },
        )

        # Empty-survey (or empty-window) short circuit
        sub_count = await total_submission_count(
            survey_number,
            date_from=date_from,
            date_to=date_to,
            submission_ids=submission_ids,
        )
        if sub_count == 0:
            await repository.mark_empty(
                report_id,
                message_ar="لا توجد ردود في هذا الاستبيان حتى الآن.",
                message_en="No responses for this survey yet.",
            )
            await _emit(report_id, "done", {"reportId": report_id, "status": "empty"})
            return

        analysis_sem = asyncio.Semaphore(settings.nlp_stage1_concurrency)
        sql_sem = asyncio.Semaphore(settings.sql_concurrency)
        summary_sem = asyncio.Semaphore(settings.llm_summary_concurrency)

        # SQL branch (parallel)
        async def _sql_branch_task() -> list[QuestionSqlResult]:
            await _emit(report_id, "sql_branch_started", {"questions": [q.question_id for q in sql_questions]})
            results: list[QuestionSqlResult] = []
            if sql_questions:
                results = await run_sql_branch(
                    survey_number,
                    sql_questions,
                    semaphore=sql_sem,
                    date_from=date_from,
                    date_to=date_to,
                    submission_ids=submission_ids,
                )
                for r in results:
                    await _emit(report_id, "sql_question_done", {"questionId": r.question_id, "type": r.type})
            await _emit(report_id, "sql_branch_done", {"count": len(results)})
            return results

        # NLP branch (parallel across questions)
        async def _nlp_branch_task() -> list[QuestionNlpResult]:
            nonlocal llm_calls
            await _emit(report_id, "nlp_branch_started", {"questions": [q.question_id for q in text_questions]})
            if not text_questions:
                await _emit(report_id, "nlp_branch_done", {})
                return []
            outs = await asyncio.gather(
                *[
                    _process_text_question(
                        report_id=report_id,
                        q=q,
                        report_language=report_language,
                        analysis_sem=analysis_sem,
                        summary_sem=summary_sem,
                        date_from=date_from,
                        date_to=date_to,
                        submission_ids=submission_ids,
                    )
                    for q in text_questions
                ]
            )
            results: list[QuestionNlpResult] = []
            for nlp_res, calls in outs:
                if nlp_res is not None:
                    results.append(nlp_res)
                llm_calls += calls
            await _emit(report_id, "nlp_branch_done", {})
            return results

        sql_results, nlp_results = await asyncio.gather(_sql_branch_task(), _nlp_branch_task())

        # Synthesis
        from app.services.analytics.token_budget import estimate_payload_tokens

        synth_input = SynthesisInput(
            report_language=report_language,
            survey_subject=(subject_ar if report_language == "ar" else subject_en) or None,
            sql=sql_results,
            nlp=nlp_results,
        )
        await _emit(
            report_id,
            "synthesis_started",
            {
                "estimatedTokens": estimate_payload_tokens(synth_input),
                "trimmed": False,
            },
        )

        if not sql_results and not any(n.valid_count > 0 for n in nlp_results):
            synthesis = empty_synthesis(report_language)
            trimmed = False
            llm_calls += 0
        else:
            synthesis, synth_calls, trimmed = await run_synthesis(synth_input, semaphore=summary_sem)
            llm_calls += synth_calls

        await _emit(report_id, "synthesis_done", {"trimmed": trimmed})

        payload = assemble_payload(
            report_language=report_language,
            synthesis=synthesis,
            nlp_results=nlp_results,
            sql_results=sql_results,
            counters={
                "answer_count": sum(n.valid_count for n in nlp_results),
                "text_questions": len(text_questions),
                "sql_questions": len(sql_results),
                "llm_calls": llm_calls,
            },
            date_from=date_from.date() if date_from is not None else None,
            date_to=date_to.date() if date_to is not None else None,
            submissions_limit=submissions_limit,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        await repository.mark_done(report_id, payload, llm_calls=llm_calls, duration_ms=duration_ms)
        await _emit(report_id, "done", {"reportId": report_id, "status": "done"})
    except Exception as exc:  # noqa: BLE001
        logger.exception("analytics report %s failed", report_id)
        try:
            await repository.mark_failed(report_id, str(exc))
        except Exception:
            pass
        await _emit(report_id, "error", {"message": str(exc)})
        await _emit(report_id, "done", {"reportId": report_id, "status": "failed"})
    finally:
        await job_registry.close(report_id)
        job_registry.schedule_cleanup(report_id)


async def trigger_report(
    survey_number: str,
    requested_language: LanguageRequest,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    submissions_limit: int | None = None,
) -> dict:
    """Resolve language → cache lookup → schedule task if needed.

    ``date_from`` / ``date_to`` are inclusive YYYY-MM-DD bounds. ``date_to``
    is interpreted as end-of-day. ``submissions_limit`` (if set) caps the
    pipeline to the N most-recent submissions in scope. All three flow into
    the cache key and every downstream data scan.

    Returns a dict suitable for the POST endpoint response.
    """
    # Validate survey existence (raises ValueError if missing/deleted).
    await resolve_survey(survey_number)

    df_dt, dt_dt = _to_window(date_from, date_to)

    submission_ids: list[str] | None = None
    if submissions_limit is not None:
        submission_ids = await get_recent_submission_ids(
            survey_number,
            limit=submissions_limit,
            date_from=df_dt,
            date_to=dt_dt,
        )

    if requested_language == "auto":
        report_language = await _probe_language(
            survey_number,
            date_from=df_dt,
            date_to=dt_dt,
            submission_ids=submission_ids,
        )
    else:
        report_language = requested_language  # type: ignore[assignment]

    h = await compute_input_hash(
        survey_number,
        report_language,
        date_from=df_dt,
        date_to=dt_dt,
        submissions_limit=submissions_limit,
        submission_ids=submission_ids,
    )

    cached = await repository.find_done_by_hash(h.sha256)
    if cached is not None:
        return {
            "reportId": cached["id"],
            "status": cached["status"],
            "cached": True,
            "reportLanguage": cached["report_language"],
        }

    report_id = await repository.create_pending(
        survey_number=survey_number,
        report_language=report_language,
        input_hash=h.sha256,
        max_answer_id=h.max_answer_id,
        answer_count=h.answer_count,
        date_from=date_from,
        date_to=date_to,
        submissions_limit=submissions_limit,
    )

    queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=512)
    job_registry.reserve(report_id, queue)
    task = asyncio.create_task(
        _run_pipeline(
            report_id, survey_number, report_language,
            date_from=df_dt, date_to=dt_dt,
            submissions_limit=submissions_limit,
            submission_ids=submission_ids,
        ),
        name=f"analytics-report-{report_id}",
    )
    job_registry.attach_task(report_id, task)

    return {
        "reportId": report_id,
        "status": "pending",
        "cached": False,
        "reportLanguage": report_language,
    }
