from __future__ import annotations

import math
import shutil
import wave
from pathlib import Path

import pytest

from worker.preprocess import convert_to_wav, split_chunks, wav_is_16k_mono


def make_wav(path: Path, seconds: int, rate: int = 44100, channels: int = 2) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i in range(rate * seconds):
            value = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
            frame = value.to_bytes(2, "little", signed=True) * channels
            wav.writeframes(frame)


pytestmark = pytest.mark.asyncio


async def test_ffmpeg_conversion_outputs_16k_mono(tmp_path: Path) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    source = tmp_path / "source.wav"
    output = tmp_path / "out.wav"
    make_wav(source, 10)
    await convert_to_wav(source, output)
    assert await wav_is_16k_mono(output)


async def test_chunk_splitting_for_90_second_file(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    make_wav(source, 90, rate=16000, channels=1)
    chunks = await split_chunks(source, tmp_path / "chunks", max_chunk_seconds=30, overlap_seconds=1)
    assert len(chunks) >= 3
    assert chunks[0].start == 0
    assert chunks[-1].end <= 90

