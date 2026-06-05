from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from worker import transcribe
from worker.preprocess import AudioChunk


pytestmark = pytest.mark.asyncio


class FakeSegment:
    text = "hello world"
    start = 0.0
    end = 1.0
    words = [SimpleNamespace(word="hello", start=0.0, end=0.5, probability=0.9)]


class FakeModel:
    def transcribe(self, *_args, **_kwargs):
        return iter([FakeSegment()]), SimpleNamespace(language="en")


async def test_transcribe_returns_segments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_get_model(*_args, **_kwargs) -> FakeModel:
        return FakeModel()

    monkeypatch.setattr(transcribe, "get_model", fake_get_model)
    chunk = AudioChunk(path=tmp_path / "x.wav", start=3.0, end=4.0)
    segments, language = await transcribe.transcribe_chunk(chunk)
    assert language == "en"
    assert {"text", "start", "end", "words", "confidence"} <= set(segments[0])
    assert segments[0]["start"] == 3.0


async def test_cpu_fallback_device_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcribe, "_cuda_available", lambda: False)
    assert transcribe._cuda_available() is False
