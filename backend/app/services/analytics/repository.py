"""Persistence layer for survey_analytics_report (RW)."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, select, update

from app.db import rw_session
from app.models.analytics import SurveyAnalyticsReport
from app.services.analytics.schemas import ReportPayload


def _row_to_dict(row: SurveyAnalyticsReport) -> dict[str, Any]:
    return {
        "id": row.id,
        "survey_number": row.survey_number,
        "report_language": row.report_language,
        "date_from": row.date_from,
        "date_to": row.date_to,
        "submissions_limit": row.submissions_limit,
        "input_hash": row.input_hash,
        "max_answer_id": row.max_answer_id,
        "answer_count": row.answer_count,
        "status": row.status,
        "payload": json.loads(row.payload_json) if row.payload_json else None,
        "error_message": row.error_message,
        "llm_calls": row.llm_calls,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _row_to_meta_dict(row: SurveyAnalyticsReport) -> dict[str, Any]:
    return {
        "id": row.id,
        "survey_number": row.survey_number,
        "report_language": row.report_language,
        "date_from": row.date_from,
        "date_to": row.date_to,
        "submissions_limit": row.submissions_limit,
        "answer_count": row.answer_count,
        "status": row.status,
        "llm_calls": row.llm_calls,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at,
    }


async def find_done_by_hash(input_hash: str) -> dict[str, Any] | None:
    """Return the most recent done row for this hash, or None."""
    async with rw_session() as db:
        row = (
            await db.execute(
                select(SurveyAnalyticsReport)
                .where(
                    SurveyAnalyticsReport.input_hash == input_hash,
                    SurveyAnalyticsReport.status.in_(["done", "empty"]),
                )
                .order_by(desc(SurveyAnalyticsReport.id))
                .limit(1)
            )
        ).scalar_one_or_none()
        return _row_to_dict(row) if row else None


async def find_by_id(report_id: int) -> dict[str, Any] | None:
    async with rw_session() as db:
        row = (
            await db.execute(
                select(SurveyAnalyticsReport).where(SurveyAnalyticsReport.id == report_id)
            )
        ).scalar_one_or_none()
        return _row_to_dict(row) if row else None


async def create_pending(
    *,
    survey_number: str,
    report_language: str,
    input_hash: str,
    max_answer_id: int,
    answer_count: int,
    date_from: date | None = None,
    date_to: date | None = None,
    submissions_limit: int | None = None,
) -> int:
    async with rw_session() as db:
        now = datetime.utcnow()
        row = SurveyAnalyticsReport(
            survey_number=survey_number,
            report_language=report_language,
            date_from=date_from,
            date_to=date_to,
            submissions_limit=submissions_limit,
            input_hash=input_hash,
            max_answer_id=max_answer_id,
            answer_count=answer_count,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return int(row.id)


async def mark_running(report_id: int) -> None:
    async with rw_session() as db:
        await db.execute(
            update(SurveyAnalyticsReport)
            .where(SurveyAnalyticsReport.id == report_id)
            .values(status="running", updated_at=datetime.utcnow())
        )
        await db.commit()


async def mark_done(report_id: int, payload: ReportPayload, *, llm_calls: int, duration_ms: int) -> None:
    async with rw_session() as db:
        await db.execute(
            update(SurveyAnalyticsReport)
            .where(SurveyAnalyticsReport.id == report_id)
            .values(
                status="done",
                payload_json=payload.model_dump_json(),
                llm_calls=llm_calls,
                duration_ms=duration_ms,
                updated_at=datetime.utcnow(),
            )
        )
        await db.commit()


async def mark_failed(report_id: int, error: str) -> None:
    async with rw_session() as db:
        await db.execute(
            update(SurveyAnalyticsReport)
            .where(SurveyAnalyticsReport.id == report_id)
            .values(
                status="failed",
                error_message=error[:8192],
                updated_at=datetime.utcnow(),
            )
        )
        await db.commit()


async def mark_empty(report_id: int, *, message_ar: str, message_en: str) -> None:
    async with rw_session() as db:
        await db.execute(
            update(SurveyAnalyticsReport)
            .where(SurveyAnalyticsReport.id == report_id)
            .values(
                status="empty",
                payload_json=json.dumps({"message": {"ar": message_ar, "en": message_en}}),
                updated_at=datetime.utcnow(),
            )
        )
        await db.commit()


async def list_by_survey(survey_number: str, limit: int = 20) -> list[dict[str, Any]]:
    async with rw_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnalyticsReport)
                .where(
                    SurveyAnalyticsReport.survey_number == survey_number,
                    SurveyAnalyticsReport.status.in_(["done", "empty", "pending", "running"]),
                )
                .order_by(desc(SurveyAnalyticsReport.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return [_row_to_meta_dict(row) for row in rows]


async def fail_orphans(older_than_minutes: int) -> int:
    """Mark long-running reports as failed (called from app startup)."""
    cutoff = datetime.utcnow().timestamp() - older_than_minutes * 60
    async with rw_session() as db:
        rows = (
            await db.execute(
                select(SurveyAnalyticsReport).where(
                    SurveyAnalyticsReport.status.in_(["pending", "running"])
                )
            )
        ).scalars().all()
        n = 0
        for row in rows:
            if row.updated_at and row.updated_at.timestamp() < cutoff:
                row.status = "failed"
                row.error_message = "interrupted by server restart"
                row.updated_at = datetime.utcnow()
                n += 1
        if n:
            await db.commit()
        return n
