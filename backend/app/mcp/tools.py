"""
Curated read-only MCP tools scoped to a single survey.

Every tool:
  1. Resolves survey_number → survey.id (guarantees scope).
  2. Uses that id for all subsequent queries so no cross-survey data leaks.
  3. Raises ValueError when the survey is not found (caller turns this into an error event).
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ro_session
from app.models.survey import (
    QuestionDropdown,
    QuestionOption,
    Survey,
    SurveyAnswer,
    SurveyAnswerOption,
    SurveyQuestion,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _resolve_survey(db: AsyncSession, survey_number: str) -> int:
    """Return survey.id or raise ValueError."""
    row = await db.execute(
        select(Survey.id).where(
            Survey.survey_number == survey_number,
            Survey.is_deleted == False,  # noqa: E712
        )
    )
    sid = row.scalar_one_or_none()
    if sid is None:
        raise ValueError(f"Survey '{survey_number}' not found")
    return sid


async def _assert_question_in_survey(
    db: AsyncSession, survey_id: int, question_id: int
) -> None:
    row = await db.execute(
        select(SurveyQuestion.id).where(
            SurveyQuestion.id == question_id,
            SurveyQuestion.survey_id == survey_id,
        )
    )
    if row.scalar_one_or_none() is None:
        raise ValueError(f"Question {question_id} does not belong to this survey")


def _date_conditions(col: Any, date_from: str | None, date_to: str | None) -> list:
    conds = []
    if date_from:
        conds.append(col >= date_from)
    if date_to:
        conds.append(col <= date_to)
    return conds


async def _extract_keywords_llm(answers: list[str], language: str) -> list[dict]:
    """Use GPT OSS to extract meaningful keywords from free-text answers (via LangChain)."""
    from langchain_core.messages import HumanMessage

    from app.agent.llm import get_keyword_extraction_model

    sample_text = "\n".join(answers[:120])
    lang_hint = "Arabic" if language == "ar" else "English"

    prompt = (
        f"You are a text analysis expert. Extract the top 20 meaningful keywords or key phrases "
        f"from these {lang_hint} survey text answers.\n\n"
        "Rules:\n"
        "- Omit: dates, times, standalone numbers, numeric IDs, phone numbers, emails, URLs\n"
        "- Keep named entities as full phrases (e.g. 'الملك سلمان', 'King Salman', 'customer service')\n"
        "- Estimate the frequency (count) of each keyword across all answers\n"
        "- Respond with ONLY a valid JSON array, no explanation:\n"
        '[{"keyword": "phrase", "count": N}, ...]\n\n'
        f"Survey answers:\n{sample_text}"
    )

    model = get_keyword_extraction_model()
    response = await model.ainvoke([HumanMessage(content=prompt)])

    content = response.content or "[]"
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        data = json.loads(match.group())
        return [
            {"token": str(item["keyword"]), "count": int(item.get("count", 1))}
            for item in data
            if isinstance(item, dict) and item.get("keyword")
        ]
    return []


def _simple_keyword_fallback(answers: list[str], language: str) -> list[dict]:
    """Naive tokenizer with date/number/ID filtering as fallback."""
    stop_en = {
        "the", "a", "an", "is", "it", "in", "of", "and", "to", "i", "we",
        "was", "for", "on", "are", "as", "at", "be", "this", "that", "with",
        "by", "from", "or", "but", "not", "have", "had", "has", "he", "she",
    }
    stop_ar = {
        "في", "من", "على", "إلى", "هذا", "هذه", "التي", "الذي", "أن", "كان",
        "كانت", "مع", "عن", "هو", "هي", "لا", "لم", "قد", "كل", "أو", "لكن",
    }
    stopwords = stop_ar if language == "ar" else stop_en
    skip = re.compile(r"^\d+$|^\d{1,4}[-/]\d{1,2}([-/]\d{1,4})?$|^\d{1,2}:\d{2}")

    # Use \w+ without \b so Arabic Unicode words are captured correctly
    # (\b relies on ASCII word-boundary rules and misses Arabic characters)
    all_tokens: list[str] = []
    for text_val in answers:
        tokens = re.findall(r"\w+", text_val, flags=re.UNICODE)
        for t in tokens:
            tl = t.lower()
            if len(tl) > 2 and tl not in stopwords and not skip.match(tl):
                all_tokens.append(tl)

    return [
        {"token": tok, "count": cnt}
        for tok, cnt in Counter(all_tokens).most_common(15)
    ]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

async def get_survey_meta(survey_number: str) -> dict[str, Any]:
    """Return subject, description, status and aggregate counts for the survey."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)

        survey_row = (
            await db.execute(
                select(
                    Survey.subject,
                    Survey.subject_ar,
                    Survey.description,
                    Survey.description_ar,
                    Survey.status,
                ).where(Survey.id == sid)
            )
        ).one()

        q_count = (
            await db.execute(
                select(func.count(SurveyQuestion.id)).where(SurveyQuestion.survey_id == sid)
            )
        ).scalar_one()

        sub_count = (
            await db.execute(
                select(func.count(func.distinct(SurveyAnswer.submission_id))).where(
                    SurveyAnswer.survey_question_id.in_(
                        select(SurveyQuestion.id).where(SurveyQuestion.survey_id == sid)
                    )
                )
            )
        ).scalar_one()

        return {
            "surveyNumber": survey_number,
            "subject": survey_row.subject,
            "subjectAr": survey_row.subject_ar,
            "description": survey_row.description,
            "descriptionAr": survey_row.description_ar,
            "status": survey_row.status,
            "totalQuestions": q_count,
            "totalSubmissions": sub_count,
        }


async def list_questions(survey_number: str) -> list[dict[str, Any]]:
    """Return ordered list of questions for the survey."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        rows = (
            await db.execute(
                select(SurveyQuestion).where(SurveyQuestion.survey_id == sid).order_by(SurveyQuestion.order_by)
            )
        ).scalars().all()

        return [
            {
                "questionId": r.id,
                "type": r.question_type,
                "questionEn": r.question_en,
                "questionAr": r.question_ar,
                "isRequired": r.is_required,
                "orderBy": r.order_by,
            }
            for r in rows
        ]


async def aggregate_choice_question(
    survey_number: str,
    question_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return option label + count + percent for MULTIPLE_CHOICE or DROPDOWN questions."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        q_row = (
            await db.execute(select(SurveyQuestion).where(SurveyQuestion.id == question_id))
        ).scalar_one()

        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)

        if q_row.question_type == "DROPDOWN":
            options = (
                await db.execute(
                    select(QuestionDropdown).where(QuestionDropdown.question_id == question_id)
                )
            ).scalars().all()
            answer_rows = (
                await db.execute(
                    select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt")).where(
                        SurveyAnswer.survey_question_id == question_id,
                        SurveyAnswer.answer.isnot(None),
                        *date_conds,
                    ).group_by(SurveyAnswer.answer)
                )
            ).all()
            count_map: dict[str, int] = {r.answer: r.cnt for r in answer_rows}
            total = sum(count_map.values()) or 1
            return [
                {
                    "optionId": opt.id,
                    "labelEn": opt.dropdown_text_en,
                    "labelAr": opt.dropdown_text_ar,
                    "count": count_map.get(opt.dropdown_text_en, 0),
                    "percent": round(count_map.get(opt.dropdown_text_en, 0) / total * 100, 1),
                }
                for opt in options
            ]
        else:
            # MULTIPLE_CHOICE: subquery counts selections filtered by date
            count_sub = (
                select(
                    SurveyAnswerOption.option_id,
                    func.count(SurveyAnswerOption.id).label("cnt"),
                )
                .join(SurveyAnswer, SurveyAnswer.id == SurveyAnswerOption.survey_answer_id)
                .where(SurveyAnswer.survey_question_id == question_id, *date_conds)
                .group_by(SurveyAnswerOption.option_id)
                .subquery()
            )

            rows = (
                await db.execute(
                    select(
                        QuestionOption.id,
                        QuestionOption.option_text_en,
                        QuestionOption.option_text_ar,
                        func.coalesce(count_sub.c.cnt, 0).label("cnt"),
                    )
                    .outerjoin(count_sub, count_sub.c.option_id == QuestionOption.id)
                    .where(QuestionOption.question_id == question_id)
                    .order_by(QuestionOption.order_by)
                )
            ).all()
            total = sum(r.cnt for r in rows) or 1
            return [
                {
                    "optionId": r.id,
                    "labelEn": r.option_text_en,
                    "labelAr": r.option_text_ar,
                    "count": r.cnt,
                    "percent": round(r.cnt / total * 100, 1),
                }
                for r in rows
            ]


async def aggregate_yes_no(
    survey_number: str,
    question_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return yes/no counts for a YES_NO question."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)
        rows = (
            await db.execute(
                select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt"))
                .where(SurveyAnswer.survey_question_id == question_id, *date_conds)
                .group_by(SurveyAnswer.answer)
            )
        ).all()

        counts: dict[str, int] = {r.answer.upper(): r.cnt for r in rows if r.answer}
        total = sum(counts.values()) or 1
        yes = counts.get("YES", 0)
        no = counts.get("NO", 0)
        return {
            "yes": yes,
            "no": no,
            "yesPercent": round(yes / total * 100, 1),
            "noPercent": round(no / total * 100, 1),
            "total": total,
        }


async def aggregate_emoji(
    survey_number: str,
    question_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return emoji → count histogram for an EMOJIS question."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)
        rows = (
            await db.execute(
                select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt"))
                .where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *date_conds,
                )
                .group_by(SurveyAnswer.answer)
                .order_by(text("cnt DESC"))
            )
        ).all()

        total = sum(r.cnt for r in rows) or 1
        return [
            {"emoji": r.answer, "count": r.cnt, "percent": round(r.cnt / total * 100, 1)}
            for r in rows
        ]


async def list_text_answers(
    survey_number: str,
    question_id: int,
    limit: int = 20,
    offset: int = 0,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return paged raw text answers for a TEXT_INPUT question."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        limit = min(limit, 100)
        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)
        rows = (
            await db.execute(
                select(SurveyAnswer.answer)
                .where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *date_conds,
                )
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()

        total = (
            await db.execute(
                select(func.count(SurveyAnswer.id)).where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *date_conds,
                )
            )
        ).scalar_one()

        return {"answers": list(rows), "total": total, "limit": limit, "offset": offset}


async def summarize_text_answers(
    survey_number: str,
    question_id: int,
    language: str = "en",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return top keywords (via GPT OSS) for a TEXT_INPUT question."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)
        rows = (
            await db.execute(
                select(SurveyAnswer.answer).where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *date_conds,
                )
            )
        ).scalars().all()

    answers = [a for a in rows if a and a.strip()]
    if not answers:
        return {"topTokens": [], "totalAnswers": 0}

    try:
        top_tokens = await _extract_keywords_llm(answers, language)
    except Exception:
        logger.warning("GPT OSS keyword extraction failed, using fallback", exc_info=True)
        top_tokens = _simple_keyword_fallback(answers, language)

    return {"topTokens": top_tokens, "totalAnswers": len(answers)}


async def list_file_answers(survey_number: str, question_id: int) -> list[str]:
    """Return file URLs for a FILE_UPLOAD question."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)
        await _assert_question_in_survey(db, sid, question_id)

        rows = (
            await db.execute(
                select(SurveyAnswer.file_url).where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.file_url.isnot(None),
                )
            )
        ).scalars().all()

        return [url for url in rows if url]


async def submission_timeline(
    survey_number: str,
    bucket: str = "day",
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Return submission counts per day or hour."""
    async with ro_session() as db:
        sid = await _resolve_survey(db, survey_number)

        question_ids_sub = select(SurveyQuestion.id).where(SurveyQuestion.survey_id == sid)
        date_conds = _date_conditions(SurveyAnswer.created_date, date_from, date_to)

        if bucket == "hour":
            date_expr = func.date_format(SurveyAnswer.created_date, "%Y-%m-%d %H:00")
        else:
            date_expr = func.date(SurveyAnswer.created_date)

        rows = (
            await db.execute(
                select(
                    date_expr.label("bucket"),
                    func.count(func.distinct(SurveyAnswer.submission_id)).label("submissions"),
                )
                .where(SurveyAnswer.survey_question_id.in_(question_ids_sub), *date_conds)
                .group_by("bucket")
                .order_by("bucket")
            )
        ).all()

        return [{"bucket": str(r.bucket), "submissions": r.submissions} for r in rows]


# ---------------------------------------------------------------------------
# Dispatch table used by the agent
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Any] = {
    "get_survey_meta": get_survey_meta,
    "list_questions": list_questions,
    "aggregate_choice_question": aggregate_choice_question,
    "aggregate_yes_no": aggregate_yes_no,
    "aggregate_emoji": aggregate_emoji,
    "list_text_answers": list_text_answers,
    "summarize_text_answers": summarize_text_answers,
    "list_file_answers": list_file_answers,
    "submission_timeline": submission_timeline,
}

# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas (sent to Qwen3)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_survey_meta",
            "description": "Get survey metadata: subject, description, status, total questions and submissions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string", "description": "The survey number (e.g. SMP2025-001)"},
                },
                "required": ["survey_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_questions",
            "description": "List all questions in the survey with their types and labels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                },
                "required": ["survey_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_choice_question",
            "description": "Get option counts and percentages for a MULTIPLE_CHOICE or DROPDOWN question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer", "description": "The question ID from list_questions"},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_yes_no",
            "description": "Get yes/no counts for a YES_NO question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer"},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_emoji",
            "description": "Get emoji answer histogram for an EMOJIS question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer"},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_text_answers",
            "description": "Get paginated raw text answers for a TEXT_INPUT question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_text_answers",
            "description": "Get top keywords for a TEXT_INPUT question (powered by LLM).",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer"},
                    "language": {"type": "string", "enum": ["en", "ar"], "default": "en"},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_file_answers",
            "description": "Get file URLs uploaded for a FILE_UPLOAD question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "question_id": {"type": "integer"},
                },
                "required": ["survey_number", "question_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submission_timeline",
            "description": "Get submission count over time grouped by day or hour.",
            "parameters": {
                "type": "object",
                "properties": {
                    "survey_number": {"type": "string"},
                    "bucket": {"type": "string", "enum": ["day", "hour"], "default": "day"},
                },
                "required": ["survey_number"],
            },
        },
    },
]
