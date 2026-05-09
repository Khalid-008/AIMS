"""RO data access for the analytics pipeline.

DB-pre-filtering of TEXT_INPUT answers: ``TRIM(answer) <> '' AND
CHAR_LENGTH(TRIM(answer)) >= 2``. The LLM still applies semantic ``is_valid``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.db import ro_session
from app.models.survey import Survey, SurveyAnswer, SurveyQuestion


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
        # Empty list means "no submissions in scope" — emit a never-true predicate
        # so callers that pass an explicit empty list get zero rows.
        return [SurveyAnswer.submission_id.is_(None) & (SurveyAnswer.submission_id.isnot(None))]
    return [SurveyAnswer.submission_id.in_(submission_ids)]


@dataclass
class QuestionMeta:
    question_id: int
    type: str
    question_en: str | None
    question_ar: str | None
    order_by: int | None


@dataclass
class TextAnswer:
    answer_id: int
    answer: str


async def resolve_survey(survey_number: str) -> tuple[int, str | None, str | None]:
    """Return (survey_id, subject_en, subject_ar) or raise ValueError if missing/deleted."""
    async with ro_session() as db:
        row = (
            await db.execute(
                select(Survey.id, Survey.subject, Survey.subject_ar).where(
                    Survey.survey_number == survey_number,
                    Survey.is_deleted == False,  # noqa: E712
                )
            )
        ).one_or_none()
        if row is None:
            raise ValueError(f"Survey '{survey_number}' not found")
        return int(row.id), row.subject, row.subject_ar


async def load_questions(survey_number: str) -> list[QuestionMeta]:
    async with ro_session() as db:
        sid = (
            await db.execute(
                select(Survey.id).where(
                    Survey.survey_number == survey_number,
                    Survey.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if sid is None:
            raise ValueError(f"Survey '{survey_number}' not found")

        rows = (
            await db.execute(
                select(SurveyQuestion)
                .where(SurveyQuestion.survey_id == sid)
                .order_by(SurveyQuestion.order_by)
            )
        ).scalars().all()
    return [
        QuestionMeta(
            question_id=r.id,
            type=r.question_type,
            question_en=r.question_en,
            question_ar=r.question_ar,
            order_by=r.order_by,
        )
        for r in rows
    ]


async def load_text_answers(
    question_id: int,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> list[TextAnswer]:
    """DB-pre-filtered: non-empty, length >= 2 (after trimming). Optional date window
    and optional submission_id allow-list."""
    async with ro_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnswer.id, SurveyAnswer.answer).where(
                    SurveyAnswer.survey_question_id == question_id,
                    SurveyAnswer.answer.isnot(None),
                    func.char_length(func.trim(SurveyAnswer.answer)) >= 2,
                    *_date_conds(date_from, date_to),
                    *_submission_conds(submission_ids),
                )
            )
        ).all()
    out: list[TextAnswer] = []
    for r in rows:
        ans = (r.answer or "").strip()
        if len(ans) >= 2:
            out.append(TextAnswer(answer_id=int(r.id), answer=ans))
    return out


async def total_submission_count(
    survey_number: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> int:
    if submission_ids is not None:
        # Caller pre-resolved the in-scope submission set; size is exact.
        return len(submission_ids)
    async with ro_session() as db:
        sid = (
            await db.execute(
                select(Survey.id).where(
                    Survey.survey_number == survey_number,
                    Survey.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if sid is None:
            return 0
        return int(
            (
                await db.execute(
                    select(func.count(func.distinct(SurveyAnswer.submission_id))).where(
                        SurveyAnswer.survey_question_id.in_(
                            select(SurveyQuestion.id).where(SurveyQuestion.survey_id == sid)
                        ),
                        *_date_conds(date_from, date_to),
                    )
                )
            ).scalar_one()
        )


async def sample_text_for_language_probe(
    survey_number: str,
    limit: int = 50,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submission_ids: list[str] | None = None,
) -> list[str]:
    """Pull up to ``limit`` non-empty text-input answer snippets for language detection."""
    async with ro_session() as db:
        sid = (
            await db.execute(
                select(Survey.id).where(
                    Survey.survey_number == survey_number,
                    Survey.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if sid is None:
            return []
        text_q_ids = select(SurveyQuestion.id).where(
            SurveyQuestion.survey_id == sid,
            SurveyQuestion.question_type == "TEXT_INPUT",
        )
        rows = (
            await db.execute(
                select(SurveyAnswer.answer)
                .where(
                    SurveyAnswer.survey_question_id.in_(text_q_ids),
                    SurveyAnswer.answer.isnot(None),
                    func.char_length(func.trim(SurveyAnswer.answer)) >= 2,
                    *_date_conds(date_from, date_to),
                    *_submission_conds(submission_ids),
                )
                .limit(limit)
            )
        ).scalars().all()
    return [str(a).strip() for a in rows if a]


async def get_recent_submission_ids(
    survey_number: str,
    *,
    limit: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[str]:
    """Return the ``limit`` most-recent submission_ids for ``survey_number``.

    Recency is measured by ``MAX(SurveyAnswer.created_date)`` per submission_id —
    i.e. the most recent answer's timestamp within that submission. Falls back to
    fewer than ``limit`` ids if the survey has fewer in-scope submissions.
    """
    async with ro_session() as db:
        sid = (
            await db.execute(
                select(Survey.id).where(
                    Survey.survey_number == survey_number,
                    Survey.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if sid is None:
            return []
        question_ids = select(SurveyQuestion.id).where(SurveyQuestion.survey_id == sid)
        rows = (
            await db.execute(
                select(
                    SurveyAnswer.submission_id,
                    func.max(SurveyAnswer.created_date).label("last_seen"),
                )
                .where(
                    SurveyAnswer.survey_question_id.in_(question_ids),
                    SurveyAnswer.submission_id.isnot(None),
                    *_date_conds(date_from, date_to),
                )
                .group_by(SurveyAnswer.submission_id)
                .order_by(func.max(SurveyAnswer.created_date).desc())
                .limit(limit)
            )
        ).all()
    return [str(r.submission_id) for r in rows]
