from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from store.db import get_session

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    if not q.strip():
        return {"results": [], "total": 0}
    result = await session.execute(
        text(
            "SELECT job_id, snippet(transcript_fts, 1, '<mark>', '</mark>', '...', 12) AS snippet "
            "FROM transcript_fts WHERE transcript_fts MATCH :q LIMIT :limit"
        ),
        {"q": q, "limit": limit},
    )
    rows = [{"job_id": row.job_id, "snippet": row.snippet} for row in result]
    return {"results": rows, "total": len(rows)}
