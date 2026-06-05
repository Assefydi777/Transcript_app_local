from __future__ import annotations

import shutil
import time
from typing import Annotated

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from store.db import get_session
from store.models import Job
from summarize.ollama_client import health_check

router = APIRouter(prefix="/status", tags=["status"])
STARTED_AT = time.monotonic()


@router.get("")
async def status(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, object]:
    counts = {
        state: (await session.execute(select(func.count()).select_from(Job).where(Job.status == state))).scalar_one()
        for state in ["pending", "transcribing", "failed"]
    }
    r = redis.Redis.from_url(get_settings().redis_url)
    usage = shutil.disk_usage(get_settings().data_dir)
    return {
        "queue": counts,
        "worker_alive": bool(r.get("worker:heartbeat")),
        "ollama_reachable": await health_check(),
        "disk": {"used": usage.used, "total": usage.total, "percent": round(usage.used / usage.total * 100, 2)},
        "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
    }

