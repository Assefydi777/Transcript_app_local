from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
import redis
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from rq import Queue
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from store.db import get_session
from store.models import Job
from worker.job_runner import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_dict(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "progress": job.progress,
        "duration": job.duration,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.post("/upload")
async def upload_job(file: Annotated[UploadFile, File()], session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    if not (file.content_type or "").startswith(("audio/", "video/")):
        raise HTTPException(status_code=400, detail="Upload must be an audio or video file")
    settings = get_settings()
    job_id = uuid.uuid4().hex
    safe_name = Path(file.filename or "upload").name
    target = settings.data_dir / "incoming" / f"{job_id}-{safe_name}"
    async with aiofiles.open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)
    session.add(Job(id=job_id, filename=safe_name, source_path=str(target), status="pending", progress=0))
    await session.commit()
    queue = Queue("transcripts", connection=redis.Redis.from_url(settings.redis_url))
    queue.enqueue(process_job, job_id, str(target), job_id=job_id, job_timeout=settings.job_timeout_seconds)
    return {"job_id": job_id, "status": "pending"}


@router.get("")
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    query: Select[tuple[Job]] = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    count_query = select(func.count()).select_from(Job)
    if status and status != "all":
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    jobs = (await session.execute(query)).scalars().all()
    total = (await session.execute(count_query)).scalar_one()
    counts = {
        state: (await session.execute(select(func.count()).select_from(Job).where(Job.status == state))).scalar_one()
        for state in ["pending", "running", "preprocessing", "transcribing", "summarizing", "done", "failed"]
    }
    return {"jobs": [_job_dict(job) for job in jobs], "total": total, "counts": counts}


@router.get("/{job_id}")
async def get_job(job_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, object]:
    job = (
        await session.execute(
            select(Job).options(selectinload(Job.transcript), selectinload(Job.summary)).where(Job.id == job_id)
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    data = _job_dict(job)
    data["transcript"] = {"text": job.transcript.text, "segments": job.transcript.segments} if job.transcript else None
    data["summary"] = (
        {
            "tldr": job.summary.tldr,
            "bullets": job.summary.bullets,
            "action_items": job.summary.action_items,
            "keywords": job.summary.keywords,
            "topics": job.summary.topics,
        }
        if job.summary
        else None
    )
    return data


@router.delete("/{job_id}")
async def delete_job(job_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        Queue("transcripts", connection=redis.Redis.from_url(get_settings().redis_url)).remove(job_id)
    except Exception:
        pass
    source = Path(job.source_path)
    if source.exists():
        source.unlink()
    shutil.rmtree(get_settings().output_dir / job_id, ignore_errors=True)
    await session.delete(job)
    await session.commit()
    return {"status": "deleted"}


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> StreamingResponse:
    async def events() -> object:
        last = ""
        while True:
            job = await session.get(Job, job_id)
            if not job:
                yield "event: error\ndata: not found\n\n"
                break
            payload = f"{job.status}:{job.progress}:{job.error or ''}"
            if payload != last:
                yield f"event: progress\ndata: {{\"status\":\"{job.status}\",\"progress\":{job.progress}}}\n\n"
                last = payload
            if job.status in {"done", "failed"}:
                break
            await asyncio.sleep(2)

    return StreamingResponse(events(), media_type="text/event-stream")
