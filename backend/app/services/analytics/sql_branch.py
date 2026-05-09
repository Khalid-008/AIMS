"""SQL branch: parallel structured aggregations.

Reuses dashboard-style aggregations for YES_NO / DROPDOWN / EMOJIS, and adds
a multi-select-aware version of MULTIPLE_CHOICE that uses
``COUNT(DISTINCT submission_id)`` as the percent denominator.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text

from app.db import ro_session
from app.mcp.tools import (
    aggregate_emoji,
    aggregate_yes_no,
)
from app.models.survey import (
    QuestionOption,
    SurveyAnswer,
    SurveyAnswerOption,
)
from app.services.analytics.data_loader import QuestionMeta
from app.services.analytics.schemas import QuestionSqlResult

logger = logging.getLogger(__name__)

_SQL_TYPES = {"MULTIPLE_CHOICE", "YES_NO", "DROPDOWN", "EMOJIS"}


def _date_conds(date_from: datetime | None, date_to: datetime | None) -> list[Any]:
    conds: list[Any] = []
    if date_from is not None:
        conds.append(SurveyAnswer.created_date >= date_from)
    if date_to is not None:
        conds.append(SurveyAnswer.created_date <= date_to)
    return conds


def _submission_conds(submission_ids: list[str] | None) -> list[Any]:
    if submission_ids is None:
        return []
    if not submission_ids:
        return [SurveyAnswer.submission_id.is_(None) & (SurveyAnswer.submission_id.isnot(None))]
    return [SurveyAnswer.submission_id.in_(submission_ids)]


def _iso_or_none(d: datetime | None) -> str | None:
    return d.isoformat() if d is not None else None


async def _aggregate_yes_no_filtered(
    question_id: int,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    submission_ids: list[str],
) -> dict:
    """Inline yes/no aggregator with submission_id allow-list support."""
    async with ro_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt"))
                .where(
                    SurveyAnswer.survey_question_id == question_id,
                    *_date_conds(date_from, date_to),
                    *_submission_conds(submission_ids),
                )
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


async def _aggregate_emoji_filtered(
    question_id: int,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    submission_ids: list[str],
) -> list[dict]:
    """Inline emoji aggregator with submission_id allow-list support."""
    async with ro_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt"))
                .where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *_date_conds(date_from, date_to),
                    *_submission_conds(submission_ids),
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


async def _aggregate_multiple_choice_multiselect(
    survey_number: str,
    question_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> dict:
    """Multi-select-aware MC aggregation.

    Returns option counts plus two percentages:
    - ``percent``        : option count / total selections (legacy denominator)
    - ``submissionPercent``: option count / distinct submissions (the correct one)
    """
    date_conds = _date_conds(date_from, date_to)
    sub_conds = _submission_conds(submission_ids)
    async with ro_session() as db:
        count_sub = (
            select(
                SurveyAnswerOption.option_id,
                func.count(SurveyAnswerOption.id).label("cnt"),
            )
            .join(SurveyAnswer, SurveyAnswer.id == SurveyAnswerOption.survey_answer_id)
            .where(SurveyAnswer.survey_question_id == question_id, *date_conds, *sub_conds)
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

        distinct_subs = (
            await db.execute(
                select(func.count(func.distinct(SurveyAnswer.submission_id))).where(
                    SurveyAnswer.survey_question_id == question_id,
                    *date_conds,
                    *sub_conds,
                )
            )
        ).scalar_one() or 0
    distinct_subs = int(distinct_subs)
    total_selections = sum(r.cnt for r in rows) or 1
    options = []
    for r in rows:
        options.append(
            {
                "optionId": int(r.id),
                "labelEn": r.option_text_en,
                "labelAr": r.option_text_ar,
                "count": int(r.cnt),
                "percent": round(int(r.cnt) / total_selections * 100, 1),
                "submissionPercent": (
                    round(int(r.cnt) / distinct_subs * 100, 1) if distinct_subs else 0.0
                ),
            }
        )
    return {
        "options": options,
        "totalSelections": total_selections,
        "distinctSubmissions": distinct_subs,
    }


async def _aggregate_dropdown(
    survey_number: str,
    question_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> dict:
    """DROPDOWN: simple text-based group-by, single-select."""
    date_conds = _date_conds(date_from, date_to)
    sub_conds = _submission_conds(submission_ids)
    async with ro_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnswer.answer, func.count(SurveyAnswer.id).label("cnt"))
                .where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    *date_conds,
                    *sub_conds,
                )
                .group_by(SurveyAnswer.answer)
            )
        ).all()
    counts = [{"label": r.answer, "count": int(r.cnt)} for r in rows]
    total = sum(c["count"] for c in counts) or 1
    for c in counts:
        c["percent"] = round(c["count"] / total * 100, 1)
    counts.sort(key=lambda c: c["count"], reverse=True)
    return {"options": counts, "total": total}


async def _aggregate_one(
    survey_number: str,
    q: QuestionMeta,
    semaphore: asyncio.Semaphore,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> QuestionSqlResult | None:
    if q.type not in _SQL_TYPES:
        return None

    question_text = q.question_ar or q.question_en or ""
    df_str = _iso_or_none(date_from)
    dt_str = _iso_or_none(date_to)

    async with semaphore:
        try:
            if q.type == "MULTIPLE_CHOICE":
                results = await _aggregate_multiple_choice_multiselect(
                    survey_number, q.question_id,
                    date_from=date_from, date_to=date_to,
                    submission_ids=submission_ids,
                )
            elif q.type == "YES_NO":
                if submission_ids is not None:
                    results = await _aggregate_yes_no_filtered(
                        q.question_id,
                        date_from=date_from, date_to=date_to,
                        submission_ids=submission_ids,
                    )
                else:
                    results = await aggregate_yes_no(
                        survey_number, q.question_id, date_from=df_str, date_to=dt_str
                    )
            elif q.type == "EMOJIS":
                if submission_ids is not None:
                    results = {
                        "options": await _aggregate_emoji_filtered(
                            q.question_id,
                            date_from=date_from, date_to=date_to,
                            submission_ids=submission_ids,
                        )
                    }
                else:
                    results = {
                        "options": await aggregate_emoji(
                            survey_number, q.question_id, date_from=df_str, date_to=dt_str
                        )
                    }
            elif q.type == "DROPDOWN":
                results = await _aggregate_dropdown(
                    survey_number, q.question_id,
                    date_from=date_from, date_to=date_to,
                    submission_ids=submission_ids,
                )
            else:
                return None
        except Exception as exc:  # noqa: BLE001 — per-question failure shouldn't kill the branch
            logger.warning("SQL aggregation failed for question %s: %s", q.question_id, exc)
            results = {"error": str(exc)}

    return QuestionSqlResult(
        question_id=q.question_id,
        question_text=question_text,
        type=q.type,  # type: ignore[arg-type]
        results=results,
    )


async def run_sql_branch(
    survey_number: str,
    questions: list[QuestionMeta],
    *,
    semaphore: asyncio.Semaphore,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> list[QuestionSqlResult]:
    coros = [
        _aggregate_one(
            survey_number, q, semaphore,
            date_from=date_from, date_to=date_to,
            submission_ids=submission_ids,
        )
        for q in questions
        if q.type in _SQL_TYPES
    ]
    results = await asyncio.gather(*coros)
    return [r for r in results if r is not None]
