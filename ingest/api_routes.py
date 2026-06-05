from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
import httpx
import redis
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from rq import Queue

from config import get_settings
from store.db import SessionLocal
from store.models import Job
from worker.job_runner import process_job

router = APIRouter()


class UrlIngestRequest(BaseModel):
    url: HttpUrl


async def create_job_for_path(path: Path) -> str:
    settings = get_settings()
    job_id = uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(Job(id=job_id, filename=path.name, source_path=str(path), status="pending", progress=0))
        await session.commit()
    queue = Queue("transcripts", connection=redis.Redis.from_url(settings.redis_url))
    queue.enqueue(process_job, job_id, str(path), job_id=job_id)
    return job_id


@router.post("/ingest-url")
async def ingest_url(payload: UrlIngestRequest) -> dict[str, str]:
    settings = get_settings()
    job_id = uuid.uuid4().hex
    target = settings.data_dir / "incoming" / f"{job_id}-{Path(str(payload.url.path)).name or 'download'}"
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(str(payload.url))
            response.raise_for_status()
        async with aiofiles.open(target, "wb") as f:
            await f.write(response.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}") from exc
    queued_id = await create_job_for_path(target)
    return {"job_id": queued_id, "status": "pending"}


@router.post("/upload")
async def upload(file: UploadFile = File()) -> dict[str, str]:
    if not (file.content_type or "").startswith(("audio/", "video/")):
        raise HTTPException(status_code=400, detail="Upload must be an audio or video file")
    settings = get_settings()
    job_id = uuid.uuid4().hex
    target = settings.data_dir / "incoming" / f"{job_id}-{Path(file.filename or 'upload').name}"
    async with aiofiles.open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)
    queued_id = await create_job_for_path(target)
    return {"job_id": queued_id, "status": "pending"}
