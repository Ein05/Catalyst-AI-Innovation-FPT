from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


GLOSSARY_DIR = Path(__file__).resolve().parents[2] / "data" / "glossary"


@dataclass
class GlossaryEntry:
    source: str
    target: str
    direction: str
    case_sensitive: bool = False
    category: str = "general"
    priority: int = 0


class GlossaryStore:
    def __init__(self, root: Path = GLOSSARY_DIR) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, session_id: str) -> list[GlossaryEntry]:
        path = self.root / f"{session_id}.json"
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            return [GlossaryEntry(**entry) for entry in json.load(handle)]

    def save(self, session_id: str, entries: list[GlossaryEntry]) -> None:
        path = self.root / f"{session_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump([asdict(entry) for entry in entries], handle, ensure_ascii=False, indent=2)

    def update(self, session_id: str, entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
        current = self.load(session_id)
        current.extend(entries)
        self.save(session_id, current)
        return current


def match_glossary(text: str, entries: list[GlossaryEntry], direction: str) -> dict[str, str]:
    candidates = [entry for entry in entries if entry.direction == direction]
    candidates.sort(key=lambda item: (len(item.source.split()), item.priority), reverse=True)
    matches: dict[str, str] = {}
    occupied: list[tuple[int, int]] = []
    for entry in candidates:
        haystack = text if entry.case_sensitive else text.lower()
        needle = entry.source if entry.case_sensitive else entry.source.lower()
        start = haystack.find(needle)
        while start >= 0:
            end = start + len(needle)
            if not any(start < used_end and end > used_start for used_start, used_end in occupied):
                matches[entry.source] = entry.target
                occupied.append((start, end))
                break
            start = haystack.find(needle, start + 1)
    return matches

