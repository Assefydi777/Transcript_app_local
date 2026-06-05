from __future__ import annotations

import pytest

from summarize import ollama_client
from summarize.postprocess import parse_summary
from summarize.prompt_builder import build_prompt_plan


def segments(words: int) -> list[dict[str, object]]:
    text = " ".join(f"word{i}" for i in range(words))
    return [{"start": 0.0, "end": 60.0, "text": text}]


def test_prompt_builder_single_pass() -> None:
    plan = build_prompt_plan(segments(500), max_tokens=3000)
    assert plan.map_reduce is False
    assert len(plan.prompts) == 1
    assert "strict JSON" in plan.prompts[0]


def test_prompt_builder_map_reduce() -> None:
    plan = build_prompt_plan(segments(5000), max_tokens=1000)
    assert plan.map_reduce is True
    assert len(plan.prompts) > 1
    assert plan.reduce_prompt is not None


@pytest.mark.asyncio
async def test_mocked_ollama_and_postprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(_prompt: str, model: str | None = None) -> str:
        return '{"tldr":"short","bullets":["one"],"action_items":["do"],"keywords":["k"],"topics":["t"]}'

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    parsed = parse_summary(await ollama_client.generate("x"))
    assert parsed.tldr == "short"
    assert parsed.action_items == ["do"]


def test_postprocess_fallback() -> None:
    parsed = parse_summary("TLDR: Something happened\nBullets:\n- A point\nAction Items:\n- Follow up")
    assert "Something" in parsed.tldr
    assert parsed.bullets == ["A point"]
    assert parsed.action_items == ["Follow up"]

