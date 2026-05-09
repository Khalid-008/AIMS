"""Summarization: per-question narrative paragraph in the report's chosen language.

Trims input to top 10 topics / top 5 entities before prompting.
"""
from __future__ import annotations

import asyncio
import json
import logging

from app.services.analytics.prompts import SUMMARIZATION_TEMPLATE, lang_full
from app.services.analytics.schemas import QuestionNlpResult

logger = logging.getLogger(__name__)


async def run_summarization(
    nlp: QuestionNlpResult,
    *,
    report_language: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, int]:
    """Returns (summary_paragraph, llm_calls_made)."""
    if nlp.valid_count == 0:
        return "", 0

    top_topics = [
        {"category": t.category, "subtopic": t.subtopic, "count": t.count, "sentiment": t.dominant_sentiment}
        for t in nlp.top_topics[:10]
    ]
    top_entities = [
        {"name": e.name, "type": e.type, "count": e.count}
        for e in nlp.top_entities[:5]
    ]
    partial_warning = (
        "Note: more than half of the LLM batches for this question failed; treat the figures as indicative."
        if nlp.partial
        else ""
    )

    prompt = SUMMARIZATION_TEMPLATE.format(
        target_lang_full=lang_full(report_language),
        question_text=nlp.question_text or "(no text)",
        valid_count=nlp.valid_count,
        sarcastic_count=nlp.sarcastic_count,
        sentiment_distribution_json=json.dumps(nlp.sentiment_distribution, ensure_ascii=False),
        top_topics_json=json.dumps(top_topics, ensure_ascii=False),
        top_entities_json=json.dumps(top_entities, ensure_ascii=False),
        partial_warning=partial_warning,
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agent.llm import get_keyword_extraction_model

    system = (
        "You are a survey analyst. Output a single paragraph in the requested language, "
        "no markdown, no headings, no JSON. Never include personal names, phone numbers, emails, or IDs."
    )
    base_model = get_keyword_extraction_model()
    model = base_model.bind(max_tokens=800, temperature=0.2)

    try:
        async with semaphore:
            response = await model.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=prompt)]
            )
        content = response.content if isinstance(response.content, str) else str(response.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("summarization failed for question %s: %s", nlp.question_id, exc)
        return "", 1

    # Strip incidental markdown fences if the model added them.
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
    return cleaned, 1
