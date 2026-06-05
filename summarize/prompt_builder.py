from __future__ import annotations

from dataclasses import dataclass

from config import get_settings


@dataclass(slots=True)
class PromptPlan:
    prompts: list[str]
    reduce_prompt: str | None
    map_reduce: bool


def count_tokens(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text.split()) * 4 // 3)


def _template(transcript: str, speaker_aware: bool = False, partial: bool = False) -> str:
    speaker_line = "Preserve speaker-specific decisions and attribution when present." if speaker_aware else ""
    scope = "partial transcript chunk" if partial else "full transcript"
    return (
        f"You are summarizing a {scope}. {speaker_line}\n"
        "Return strict JSON only with keys: tldr, bullets, action_items, keywords, topics.\n"
        "Use concise, factual language. action_items must be concrete follow-ups.\n\n"
        f"Transcript:\n{transcript}"
    )


def _split_by_tokens(lines: list[str], max_tokens: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        line_tokens = count_tokens(line)
        if current and current_tokens + line_tokens > max_tokens:
            chunks.append("\n".join(current))
            current = []
            current_tokens = 0
        current.append(line)
        current_tokens += line_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


def build_prompt_plan(segments: list[dict[str, object]], max_tokens: int | None = None) -> PromptPlan:
    settings = get_settings()
    limit = max_tokens or settings.max_prompt_tokens
    speaker_aware = any("speaker" in segment for segment in segments)
    lines = [
        f"[{float(segment.get('start', 0)):0.1f}-{float(segment.get('end', 0)):0.1f}] {segment.get('text', '')}"
        for segment in segments
    ]
    transcript = "\n".join(lines)
    if count_tokens(transcript) <= limit:
        return PromptPlan(prompts=[_template(transcript, speaker_aware)], reduce_prompt=None, map_reduce=False)
    chunks = _split_by_tokens(lines, limit)
    prompts = [_template(chunk, speaker_aware=speaker_aware, partial=True) for chunk in chunks]
    reduce_prompt = (
        "Synthesize these chunk summaries into one strict JSON object with keys: "
        "tldr, bullets, action_items, keywords, topics. Deduplicate repeated points and keep only important items.\n\n"
        "{chunk_summaries}"
    )
    return PromptPlan(prompts=prompts, reduce_prompt=reduce_prompt, map_reduce=True)

