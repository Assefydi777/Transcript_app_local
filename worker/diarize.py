from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from config import get_settings

log = structlog.get_logger()
_pipeline: Any | None = None


async def _get_pipeline() -> Any:
    global _pipeline
    settings = get_settings()
    if _pipeline is not None:
        return _pipeline
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is required for diarization")

    def load() -> Any:
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=settings.hf_token)
        return pipeline

    _pipeline = await asyncio.to_thread(load)
    return _pipeline


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


async def diarize_segments(audio_path: Path, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.enable_diarization:
        return segments
    pipeline = await _get_pipeline()

    def run() -> list[tuple[float, float, str]]:
        diarization = pipeline(str(audio_path))
        turns: list[tuple[float, float, str]] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append((float(turn.start), float(turn.end), str(speaker)))
        return turns

    try:
        turns = await asyncio.to_thread(run)
    except Exception as exc:
        log.warning("diarization_failed", error=str(exc))
        return segments
    mapped: list[dict[str, Any]] = []
    for segment in segments:
        best_label = None
        best_overlap = 0.0
        for start, end, label in turns:
            score = _overlap(float(segment["start"]), float(segment["end"]), start, end)
            if score > best_overlap:
                best_overlap = score
                best_label = label
        updated = dict(segment)
        if best_label:
            updated["speaker"] = best_label
            updated["text"] = f"{best_label}: {updated['text']}"
        mapped.append(updated)
    return mapped

