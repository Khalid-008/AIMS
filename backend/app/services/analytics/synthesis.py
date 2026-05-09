"""Final synthesis: a single LLM call merging SQL aggregates + NLP findings into
the executive report shape."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime

from app.config import settings
from app.services.analytics.llm_io import LlmJsonError, LlmTransportError, call_json
from app.services.analytics.prompts import SYNTHESIS_SYSTEM, SYNTHESIS_USER_TEMPLATE, lang_full
from app.services.analytics.schemas import (
    ReportPayload,
    SynthesisInput,
    SynthesisOutput,
)
from app.services.analytics.token_budget import (
    estimate_payload_tokens,
    trim_synthesis_input,
)

logger = logging.getLogger(__name__)


def _slim_for_prompt(payload: SynthesisInput) -> dict:
    """Drop example phrases and trim topics/entities to top 10/5 for the prompt."""
    nlp = []
    for n in payload.nlp:
        nlp.append(
            {
                "question_id": n.question_id,
                "question_text": n.question_text,
                "valid_count": n.valid_count,
                "sarcastic_count": n.sarcastic_count,
                "sentiment_distribution": n.sentiment_distribution,
                "narrative_summary": n.narrative_summary,
                "top_topics": [
                    {
                        "category": t.category,
                        "subtopic": t.subtopic,
                        "count": t.count,
                        "dominant_sentiment": t.dominant_sentiment,
                        "sentiment_breakdown": t.sentiment_breakdown,
                    }
                    for t in n.top_topics[:10]
                ],
                "top_entities": [
                    {"name": e.name, "type": e.type, "count": e.count}
                    for e in n.top_entities[:5]
                ],
                "partial": n.partial,
            }
        )
    sql = [
        {
            "question_id": s.question_id,
            "question_text": s.question_text,
            "type": s.type,
            "results": s.results,
        }
        for s in payload.sql
    ]
    return {"sql": sql, "nlp": nlp}


async def run_synthesis(
    payload: SynthesisInput,
    *,
    semaphore: asyncio.Semaphore,
) -> tuple[SynthesisOutput, int, bool]:
    """Returns (synthesis_output, llm_calls, was_trimmed)."""
    budget = settings.analytics_synthesis_token_budget
    estimated = estimate_payload_tokens(payload)
    trimmed_flag = estimated > budget
    if trimmed_flag:
        payload = trim_synthesis_input(payload, budget)

    slim = _slim_for_prompt(payload)
    prompt = SYNTHESIS_USER_TEMPLATE.format(
        survey_subject=payload.survey_subject or "",
        target_lang_full=lang_full(payload.report_language),
        sql_json=json.dumps(slim["sql"], ensure_ascii=False),
        nlp_json=json.dumps(slim["nlp"], ensure_ascii=False),
    )

    try:
        raw = await call_json(
            prompt,
            semaphore=semaphore,
            json_root="object",
            system_prompt=SYNTHESIS_SYSTEM,
            max_tokens=3000,
            temperature=0.2,
        )
    except (LlmJsonError, LlmTransportError) as exc:
        logger.error("synthesis LLM failed: %s", exc)
        raise

    out = SynthesisOutput.model_validate(raw)
    return out, 1, trimmed_flag


def empty_synthesis(report_language: str) -> SynthesisOutput:
    msg = (
        "لا توجد بيانات كافية لإصدار تقرير في هذا الوقت."
        if report_language == "ar"
        else "Not enough data to generate a report at this time."
    )
    return SynthesisOutput(
        executive_summary=msg,
        detailed_analysis=msg,
        key_metrics=[],
        recommendations=[],
    )


def assemble_payload(
    *,
    report_language: str,
    synthesis: SynthesisOutput,
    nlp_results: list,
    sql_results: list,
    counters: dict[str, int],
    date_from: date | None = None,
    date_to: date | None = None,
    submissions_limit: int | None = None,
) -> ReportPayload:
    return ReportPayload(
        report_language=report_language,  # type: ignore[arg-type]
        date_from=date_from,
        date_to=date_to,
        submissions_limit=submissions_limit,
        synthesis=synthesis,
        nlp=nlp_results,
        sql=sql_results,
        counters=counters,
        generated_at=datetime.utcnow(),
    )
