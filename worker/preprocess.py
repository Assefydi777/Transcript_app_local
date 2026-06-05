from __future__ import annotations

import asyncio
import json
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydub import AudioSegment, silence

from config import get_settings

log = structlog.get_logger()


@dataclass(slots=True)
class AudioInfo:
    duration: float
    format_name: str


@dataclass(slots=True)
class AudioChunk:
    path: Path
    start: float
    end: float


async def _run(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace"))
    return stdout.decode(errors="replace")


async def probe_audio(input_path: Path) -> AudioInfo:
    output = await _run(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name",
        "-of",
        "json",
        str(input_path),
    )
    payload = json.loads(output)
    fmt = payload.get("format", {})
    return AudioInfo(duration=float(fmt.get("duration") or 0), format_name=str(fmt.get("format_name") or "unknown"))


async def convert_to_wav(input_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    await _run(
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    )
    return output_path


async def strip_silence(input_wav: Path, output_wav: Path) -> Path:
    try:
        import torch  # type: ignore

        await asyncio.to_thread(torch.hub.load, "snakers4/silero-vad", "silero_vad", trust_repo=True, onnx=False)
    except Exception as exc:
        log.info("silero_vad_unavailable_using_pydub", error=str(exc))
    audio = await asyncio.to_thread(AudioSegment.from_wav, input_wav)
    ranges = await asyncio.to_thread(silence.detect_nonsilent, audio, min_silence_len=500, silence_thresh=audio.dBFS - 16)
    if not ranges:
        shutil.copyfile(input_wav, output_wav)
        return output_wav
    merged = AudioSegment.silent(duration=0, frame_rate=16000)
    for start_ms, end_ms in ranges:
        merged += audio[max(0, start_ms - 150) : min(len(audio), end_ms + 150)]
    await asyncio.to_thread(merged.export, output_wav, format="wav")
    return output_wav


async def split_chunks(input_wav: Path, chunk_dir: Path, max_chunk_seconds: int = 30, overlap_seconds: int = 1) -> list[AudioChunk]:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    audio = await asyncio.to_thread(AudioSegment.from_wav, input_wav)
    max_ms = max_chunk_seconds * 1000
    overlap_ms = overlap_seconds * 1000
    nonsilent = await asyncio.to_thread(silence.detect_nonsilent, audio, min_silence_len=400, silence_thresh=audio.dBFS - 16)
    boundaries = nonsilent or [[0, len(audio)]]
    chunks: list[AudioChunk] = []
    start_ms = boundaries[0][0]
    cursor = start_ms
    idx = 0
    while cursor < len(audio):
        target_end = min(cursor + max_ms, len(audio))
        candidates = [end for _, end in boundaries if cursor + 5000 <= end <= target_end]
        end_ms = candidates[-1] if candidates else target_end
        if end_ms <= cursor:
            end_ms = min(cursor + max_ms, len(audio))
        path = chunk_dir / f"chunk_{idx:04d}.wav"
        await asyncio.to_thread(audio[cursor:end_ms].export, path, format="wav")
        chunks.append(AudioChunk(path=path, start=cursor / 1000, end=end_ms / 1000))
        idx += 1
        if end_ms >= len(audio):
            break
        cursor = max(0, end_ms - overlap_ms)
    return chunks


async def preprocess_file(input_path: Path, job_id: str) -> tuple[AudioInfo, Path, list[AudioChunk]]:
    settings = get_settings()
    work_dir = settings.data_dir / "work" / job_id
    raw_wav = work_dir / "converted.wav"
    vad_wav = work_dir / "vad.wav"
    info = await probe_audio(input_path)
    await convert_to_wav(input_path, raw_wav)
    await strip_silence(raw_wav, vad_wav)
    chunks = await split_chunks(vad_wav, work_dir / "chunks", settings.chunk_seconds, settings.chunk_overlap_seconds)
    return info, vad_wav, chunks


async def wav_is_16k_mono(path: Path) -> bool:
    def check() -> bool:
        with wave.open(str(path), "rb") as wav:
            return wav.getframerate() == 16000 and wav.getnchannels() == 1

    return await asyncio.to_thread(check)

