from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from config import get_settings
from worker.preprocess import AudioChunk

log = structlog.get_logger()
_model: Any | None = None
_model_key: tuple[str, str, str] | None = None


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return False


async def get_model(device: str | None = None, compute_type: str | None = None) -> Any:
    global _model, _model_key
    settings = get_settings()
    selected_device = device or settings.whisper_device
    if selected_device == "auto":
        selected_device = "cuda" if _cuda_available() else "cpu"
    selected_compute = compute_type or ("float16" if selected_device == "cuda" else "int8")
    key = (settings.whisper_model, selected_device, selected_compute)
    if _model is not None and _model_key == key:
        return _model

    def load() -> Any:
        from faster_whisper import WhisperModel

        return WhisperModel(settings.whisper_model, device=selected_device, compute_type=selected_compute)

    _model = await asyncio.to_thread(load)
    _model_key = key
    return _model


async def transcribe_chunk(chunk: AudioChunk) -> tuple[list[dict[str, Any]], str | None]:
    settings = get_settings()
    model = await get_model()

    def run() -> tuple[list[dict[str, Any]], str | None]:
        segments_iter, info = model.transcribe(
            str(chunk.path),
            beam_size=5,
            word_timestamps=True,
            language=settings.whisper_language,
        )
        segments: list[dict[str, Any]] = []
        for segment in segments_iter:
            words = [
                {"word": w.word, "start": (w.start or 0) + chunk.start, "end": (w.end or 0) + chunk.start, "probability": w.probability}
                for w in (segment.words or [])
            ]
            confidence = sum(float(w.get("probability") or 0) for w in words) / max(len(words), 1)
            segments.append(
                {
                    "text": segment.text.strip(),
                    "start": float(segment.start) + chunk.start,
                    "end": float(segment.end) + chunk.start,
                    "words": words,
                    "confidence": confidence,
                }
            )
        return segments, getattr(info, "language", None)

    try:
        return await asyncio.to_thread(run)
    except RuntimeError as exc:
        if "CUDA" not in str(exc).upper() and "OUT OF MEMORY" not in str(exc).upper():
            raise
        log.warning("cuda_oom_falling_back_to_cpu", error=str(exc))
        await get_model(device="cpu", compute_type="int8")
        return await asyncio.to_thread(run)


async def transcribe_chunks(chunks: list[AudioChunk]) -> tuple[list[dict[str, Any]], str | None]:
    all_segments: list[dict[str, Any]] = []
    language: str | None = None
    for chunk in chunks:
        segments, detected_language = await transcribe_chunk(chunk)
        all_segments.extend(segments)
        language = language or detected_language
    return all_segments, language

