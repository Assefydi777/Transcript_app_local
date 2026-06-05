from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiofiles

from config import get_settings


def _stamp(seconds: float, sep: str = ",") -> str:
    millis = int((seconds - int(seconds)) * 1000)
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


async def write_outputs(job_id: str, segments: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, str]:
    output_dir = get_settings().output_dir / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    text = "\n".join(str(s.get("text", "")).strip() for s in segments)
    paths = {
        "json": output_dir / "transcript.json",
        "srt": output_dir / "transcript.srt",
        "vtt": output_dir / "transcript.vtt",
        "md": output_dir / "summary.md",
    }
    async with aiofiles.open(paths["json"], "w") as f:
        await f.write(json.dumps({"job_id": job_id, "segments": segments, "summary": summary}, indent=2))
    async with aiofiles.open(paths["srt"], "w") as f:
        for idx, segment in enumerate(segments, 1):
            await f.write(f"{idx}\n{_stamp(float(segment['start']))} --> {_stamp(float(segment['end']))}\n{segment['text'].strip()}\n\n")
    async with aiofiles.open(paths["vtt"], "w") as f:
        await f.write("WEBVTT\n\n")
        for segment in segments:
            await f.write(f"{_stamp(float(segment['start']), '.')} --> {_stamp(float(segment['end']), '.')}\n{segment['text'].strip()}\n\n")
    async with aiofiles.open(paths["md"], "w") as f:
        await f.write(f"# Summary\n\n{summary.get('tldr', '')}\n\n## Bullets\n")
        for bullet in summary.get("bullets", []):
            await f.write(f"- {bullet}\n")
        await f.write("\n## Action Items\n")
        for item in summary.get("action_items", []):
            await f.write(f"- [ ] {item}\n")
        await f.write("\n## Transcript\n\n")
        await f.write(text)
    return {key: str(path) for key, path in paths.items()}

