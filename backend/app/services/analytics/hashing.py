"""Content-addressed input hash for analytics report caching.

The hash is over (survey_number, report_language, max_answer_id, answer_count).
A new answer in the survey changes the hash; same data + same language returns
a cached result.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.db import ro_session
from app.models.survey import Survey, SurveyAnswer, SurveyQuestion


@dataclass
class InputHash:
    sha256: str
    max_answer_id: int
    answer_count: int


async def compute_input_hash(
    survey_number: str,
    report_language: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    submissions_limit: int | None = None,
    submission_ids: list[str] | None = None,
) -> InputHash:
    """Hash inputs that determine the cached report identity.

    The optional ``date_from`` / ``date_to`` window and the optional
    ``submission_ids`` allow-list scope the ``max_answer_id`` and
    ``answer_count`` scans. The window bounds and ``submissions_limit``
    are mixed into the hash material so different (window, limit)
    tuples yield distinct cache rows.
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
            raise ValueError(f"Survey '{survey_number}' not found")

        question_ids = select(SurveyQuestion.id).where(SurveyQuestion.survey_id == sid)

        date_conds = []
        if date_from is not None:
            date_conds.append(SurveyAnswer.created_date >= date_from)
        if date_to is not None:
            date_conds.append(SurveyAnswer.created_date <= date_to)

        sub_conds: list = []
        if submission_ids is not None:
            if not submission_ids:
                # Empty allow-list → no rows, deterministic hash inputs.
                return InputHash(
                    sha256=hashlib.sha256(
                        f"{survey_number}|{report_language}|"
                        f"{date_from.isoformat() if date_from else ''}|"
                        f"{date_to.isoformat() if date_to else ''}|"
                        f"{submissions_limit if submissions_limit is not None else ''}|0|0".encode("utf-8")
                    ).hexdigest(),
                    max_answer_id=0,
                    answer_count=0,
                )
            sub_conds.append(SurveyAnswer.submission_id.in_(submission_ids))

        max_id = (
            await db.execute(
                select(func.coalesce(func.max(SurveyAnswer.id), 0)).where(
                    SurveyAnswer.survey_question_id.in_(question_ids),
                    *date_conds,
                    *sub_conds,
                )
            )
        ).scalar_one()

        count = (
            await db.execute(
                select(func.count(SurveyAnswer.id)).where(
                    SurveyAnswer.survey_question_id.in_(question_ids),
                    *date_conds,
                    *sub_conds,
                )
            )
        ).scalar_one()

    df = date_from.isoformat() if date_from is not None else ""
    dt = date_to.isoformat() if date_to is not None else ""
    lim = str(submissions_limit) if submissions_limit is not None else ""
    raw = f"{survey_number}|{report_language}|{df}|{dt}|{lim}|{int(max_id)}|{int(count)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return InputHash(sha256=digest, max_answer_id=int(max_id), answer_count=int(count))
