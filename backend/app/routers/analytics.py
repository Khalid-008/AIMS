"""Analytics-report endpoints.

Three routes under ``/api/surveys/{survey_number}/analytics-report``:
- ``POST .``                : trigger or return-cached
- ``GET  ./{id}``           : final result fetch
- ``GET  ./{id}/stream``    : SSE progress stream
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.analytics import job_registry, repository
from app.services.analytics.orchestrator import trigger_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/surveys", tags=["analytics"])


class StartReportRequest(BaseModel):
    language: Literal["ar", "en", "auto"] = "auto"
    dateFrom: str | None = Field(default=None)
    dateTo: str | None = Field(default=None)
    submissionsLimit: int | None = Field(default=None, gt=0)


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field}: expected YYYY-MM-DD, got '{value}'",
        ) from exc


def _stream_url(survey_number: str, report_id: int) -> str:
    return f"/api/surveys/{survey_number}/analytics-report/{report_id}/stream"


def _result_url(survey_number: str, report_id: int) -> str:
    return f"/api/surveys/{survey_number}/analytics-report/{report_id}"


@router.post("/{survey_number}/analytics-report")
async def start_report(survey_number: str, body: StartReportRequest) -> dict:
    date_from = _parse_date(body.dateFrom, "dateFrom")
    date_to = _parse_date(body.dateTo, "dateTo")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dateFrom must be on or before dateTo",
        )
    try:
        result = await trigger_report(
            survey_number,
            body.language,
            date_from=date_from,
            date_to=date_to,
            submissions_limit=body.submissionsLimit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    rid = result["reportId"]
    return {
        **result,
        "streamUrl": _stream_url(survey_number, rid),
        "resultUrl": _result_url(survey_number, rid),
    }


@router.get("/{survey_number}/analytics-report")
async def list_reports(survey_number: str, limit: int = 20) -> list[dict]:
    rows = await repository.list_by_survey(survey_number, limit=limit)
    return [
        {
            "reportId": row["id"],
            "surveyNumber": row["survey_number"],
            "status": row["status"],
            "reportLanguage": row["report_language"],
            "dateFrom": row["date_from"].isoformat() if row["date_from"] else None,
            "dateTo": row["date_to"].isoformat() if row["date_to"] else None,
            "submissionsLimit": row.get("submissions_limit"),
            "answerCount": row["answer_count"],
            "llmCalls": row["llm_calls"],
            "durationMs": row["duration_ms"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


@router.get("/{survey_number}/analytics-report/{report_id}")
async def get_report(survey_number: str, report_id: int) -> dict:
    row = await repository.find_by_id(report_id)
    if row is None or row["survey_number"] != survey_number:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    base = {
        "reportId": row["id"],
        "surveyNumber": row["survey_number"],
        "status": row["status"],
        "reportLanguage": row["report_language"],
        "dateFrom": row["date_from"].isoformat() if row["date_from"] else None,
        "dateTo": row["date_to"].isoformat() if row["date_to"] else None,
        "submissionsLimit": row.get("submissions_limit"),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "durationMs": row["duration_ms"],
        "llmCalls": row["llm_calls"],
    }

    if row["status"] == "done":
        return {**base, "payload": row["payload"]}
    if row["status"] == "empty":
        msg = (row["payload"] or {}).get("message") or {}
        return {**base, "message": msg}
    if row["status"] == "failed":
        return {**base, "error": row["error_message"]}
    # pending / running
    return {**base, "streamUrl": _stream_url(survey_number, report_id)}


@router.get("/{survey_number}/analytics-report/{report_id}/stream")
async def stream_report(survey_number: str, report_id: int):
    row = await repository.find_by_id(report_id)
    if row is None or row["survey_number"] != survey_number:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    async def event_stream():
        try:
            handle = job_registry.get(report_id)
            # Replay any prior history (events emitted before the consumer attached)
            if handle is not None:
                for ev in list(handle.history):
                    data = ev.get("data", {})
                    yield f"event: {ev['event']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                # Live tail
                while True:
                    item = await handle.queue.get()
                    if item is None:
                        break
                    data = item.get("data", {})
                    yield f"event: {item['event']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                return

            # No live handle — terminal state reached or already cleaned up
            if row["status"] == "done":
                yield f"event: done\ndata: {json.dumps({'reportId': report_id, 'status': 'done', 'cached': True}, ensure_ascii=False)}\n\n"
            elif row["status"] == "empty":
                yield f"event: done\ndata: {json.dumps({'reportId': report_id, 'status': 'empty'}, ensure_ascii=False)}\n\n"
            elif row["status"] == "failed":
                yield f"event: error\ndata: {json.dumps({'message': row['error_message'] or 'failed'}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'reportId': report_id, 'status': 'failed'}, ensure_ascii=False)}\n\n"
            else:
                # pending/running but no handle — likely lost across server restart
                yield f"event: error\ndata: {json.dumps({'message': 'job not running on this server'}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'reportId': report_id, 'status': row['status']}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("analytics stream error: %s", exc, exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(exc))}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
