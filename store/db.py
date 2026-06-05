from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings
from store.models import Base

settings = get_settings()
engine: AsyncEngine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(job_id UNINDEXED, content, summary)"))


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def close_db() -> None:
    await engine.dispose()


async def update_fts(session: AsyncSession, job_id: str, content: str, summary: str) -> None:
    await session.execute(text("DELETE FROM transcript_fts WHERE job_id = :job_id"), {"job_id": job_id})
    await session.execute(
        text("INSERT INTO transcript_fts(job_id, content, summary) VALUES (:job_id, :content, :summary)"),
        {"job_id": job_id, "content": content, "summary": summary},
    )

