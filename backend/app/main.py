import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analytics, chat, surveys

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Mark stuck analytics reports from a prior process run as failed so the
    # frontend doesn't see them stay in "pending"/"running" forever.
    try:
        from app.services.analytics.repository import fail_orphans

        n = await fail_orphans(settings.analytics_orphan_timeout_minutes)
        if n:
            logger.info("marked %d orphaned analytics reports as failed", n)
    except Exception as exc:  # noqa: BLE001 — don't block startup on cleanup
        logger.warning("orphan cleanup skipped: %s", exc)
    yield


app = FastAPI(title="Survey AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(surveys.router)
app.include_router(chat.router)
app.include_router(analytics.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
