from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Read-only engine (survey tables)
_ro_engine = create_async_engine(settings.ro_dsn, pool_pre_ping=True, echo=False)
_ro_session_factory = async_sessionmaker(_ro_engine, expire_on_commit=False)

# Read-write engine (ai_chat_* tables)
_rw_engine = create_async_engine(settings.rw_dsn, pool_pre_ping=True, echo=False)
_rw_session_factory = async_sessionmaker(_rw_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_ro_session() -> AsyncGenerator[AsyncSession, None]:
    async with _ro_session_factory() as session:
        yield session


async def get_rw_session() -> AsyncGenerator[AsyncSession, None]:
    async with _rw_session_factory() as session:
        yield session


@asynccontextmanager
async def ro_session() -> AsyncGenerator[AsyncSession, None]:
    async with _ro_session_factory() as session:
        yield session


@asynccontextmanager
async def rw_session() -> AsyncGenerator[AsyncSession, None]:
    async with _rw_session_factory() as session:
        yield session
