from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from store.db import get_session
from store.models import Transcript

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("/{job_id}")
async def get_transcript(job_id: str, session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, object]:
    transcript = (await session.execute(select(Transcript).where(Transcript.job_id == job_id))).scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"job_id": job_id, "text": transcript.text, "segments": transcript.segments, "language": transcript.language}


@router.get("/{job_id}/download")
async def download_transcript(job_id: str, format: str = Query(pattern="^(srt|vtt|json|md)$")) -> FileResponse:
    names = {"srt": "transcript.srt", "vtt": "transcript.vtt", "json": "transcript.json", "md": "summary.md"}
    path = get_settings().output_dir / job_id / names[format]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(Path(path), filename=names[format])

