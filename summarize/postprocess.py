from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ParsedSummary:
    tldr: str
    bullets: list[str]
    action_items: list[str]
    keywords: list[str]
    topics: list[str]
    raw_response: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def _list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip("-* 0123456789.\t") for line in value.splitlines() if line.strip()]
    return []


def parse_summary(raw: str) -> ParsedSummary:
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
        return ParsedSummary(
            tldr=str(data.get("tldr", "")).strip(),
            bullets=_list(data.get("bullets", [])),
            action_items=_list(data.get("action_items", [])),
            keywords=_list(data.get("keywords", [])),
            topics=_list(data.get("topics", [])),
            raw_response=raw,
        )
    except json.JSONDecodeError:
        pass
    sections = {"bullets": [], "action_items": [], "keywords": [], "topics": []}
    tldr_match = re.search(r"(?:TL;?DR|Summary)\s*:?\s*(.+?)(?:\n\s*(?:Bullets|Action|Keywords|Topics)|$)", cleaned, re.I | re.S)
    for key, pattern in {
        "bullets": r"Bullets?\s*:?\s*(.+?)(?:\n\s*(?:Action|Keywords|Topics)|$)",
        "action_items": r"Action(?: Items?)?\s*:?\s*(.+?)(?:\n\s*(?:Keywords|Topics)|$)",
        "keywords": r"Keywords?\s*:?\s*(.+?)(?:\n\s*Topics|$)",
        "topics": r"Topics?\s*:?\s*(.+)$",
    }.items():
        match = re.search(pattern, cleaned, re.I | re.S)
        if match:
            sections[key] = _list(match.group(1))
    return ParsedSummary(
        tldr=(tldr_match.group(1).strip() if tldr_match else cleaned[:500]),
        bullets=sections["bullets"],
        action_items=sections["action_items"],
        keywords=sections["keywords"],
        topics=sections["topics"],
        raw_response=raw,
    )

