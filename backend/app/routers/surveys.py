import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.db import get_ro_session
from app.models.survey import Survey
from app.services.dashboard import build_dashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/surveys", tags=["surveys"])

EXTERNAL_API_BASE = "http://8.213.40.239:32252/api/ms/survey"
EXTERNAL_API_TOKEN = (
    "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzYUBjaGFubmVsczEuY29tLnNhIiwiUm9sZSI6IlN1cGVy"
    "IEFkbWluIiwiRnVsbE5hbWVBciI6Itij2LHZiNmJINin2YTYudmK2LPZiSIsIkZ1bGxOYW1lRW4iOiJBcndh"
    "IEFsaXNzYSIsImlzRmlyc3RUaW1lIjpmYWxzZSwiVHlwZSI6IkVNUExPWUVFIiwiaWF0IjoxNzc1NDgxOTg0"
    "LCJleHAiOjE3NzU0ODM3ODR9.TnEgKVU7ePC-nr4mSUHiIoN7G5-4bR8ao1muFlPc9kM"
)


@router.get("")
async def list_surveys() -> list[dict]:
    """Fetch all surveys from the external API (handles pagination)."""
    all_surveys: list[dict] = []
    page_number = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.post(
                f"{EXTERNAL_API_BASE}/all",
                json={"request": {"pageNumber": page_number, "pageSize": 10, "searchText": ""}},
                headers={"Content-Type": "application/json", "Authorization": EXTERNAL_API_TOKEN},
            )
            if resp.status_code != 200:
                logger.error(
                    "External API returned %s for page %d: %s",
                    resp.status_code, page_number, resp.text[:500],
                )
                resp.raise_for_status()
            data = resp.json().get("response", {})
            content = data.get("content", [])
            logger.debug("Fetched page %d: %d surveys", page_number, len(content))
            all_surveys.extend(content)

            if data.get("last", False):
                break
            page_number += 1

    return all_surveys


@router.get("/{survey_number}/dashboard")
async def dashboard(
    survey_number: str,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_ro_session),
) -> dict:
    row = await db.execute(
        select(Survey.id, Survey.is_deleted).where(
            Survey.survey_number == survey_number,
        )
    )
    result = row.one_or_none()
    if result is None:
        logger.warning("Dashboard 404: survey '%s' not found in local DB", survey_number)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Survey '{survey_number}' not found in local database")
    if result.is_deleted:
        logger.warning("Dashboard 404: survey '%s' exists but is marked deleted", survey_number)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Survey '{survey_number}' has been deleted")

    return await build_dashboard(survey_number, date_from=date_from, date_to=date_to)