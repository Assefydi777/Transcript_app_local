from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from store.db import get_session
from store.models import Summary

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.get("/{job_id}")
async def get_summary(job_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, object]:
    summary = (await session.execute(select(Summary).where(Summary.job_id == job_id))).scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {
        "job_id": job_id,
        "tldr": summary.tldr,
        "bullets": summary.bullets,
        "action_items": summary.action_items,
        "keywords": summary.keywords,
        "topics": summary.topics,
    }

