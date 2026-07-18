from __future__ import annotations

import re
from dataclasses import dataclass, field


ENTITY_PATTERNS = {
    "currencies": re.compile(r"\b(?:SGD|USD|VND|EUR|JPY|GBP)\b", re.IGNORECASE),
    "numbers": re.compile(r"\b\d+(?:[.,]\d+)?(?:\s?(?:million|trieu|triệu|billion|%))?\b", re.IGNORECASE),
    "dates": re.compile(
        r"\b(?:Q[1-4]|(?:\d{1,2}\s)?(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December|thang\s\d{1,2}|tháng\s\d{1,2}|thu\s\w+|thứ\s\w+))\b",
        re.IGNORECASE,
    ),
    "entities": re.compile(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)+\b"),
}


@dataclass
class ProtectedText:
    text: str
    entities: dict[str, list[str]] = field(default_factory=dict)
    placeholders: dict[str, str] = field(default_factory=dict)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_entities(text: str) -> dict[str, list[str]]:
    normalized = normalize_whitespace(text)
    found: dict[str, list[str]] = {key: [] for key in ENTITY_PATTERNS}
    spans: list[tuple[int, int]] = []
    for kind, pattern in ENTITY_PATTERNS.items():
        for match in pattern.finditer(normalized):
            value = match.group(0)
            if any(match.start() < end and match.end() > start for start, end in spans):
                continue
            found[kind].append(value)
            spans.append((match.start(), match.end()))
    return found


def protect_entities(text: str) -> ProtectedText:
    normalized = normalize_whitespace(text)
    replacements: list[tuple[int, int, str, str]] = []
    counts = {"numbers": 0, "dates": 0, "currencies": 0, "entities": 0}
    prefixes = {"numbers": "NUM", "dates": "DATE", "currencies": "CUR", "entities": "TERM"}
    occupied: list[tuple[int, int]] = []
    entities = {key: [] for key in ENTITY_PATTERNS}
    for kind, pattern in ENTITY_PATTERNS.items():
        for match in pattern.finditer(normalized):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            counts[kind] += 1
            placeholder = f"<{prefixes[kind]}_{counts[kind]}>"
            value = match.group(0)
            replacements.append((match.start(), match.end(), placeholder, value))
            occupied.append((match.start(), match.end()))
            entities[kind].append(value)
    protected = normalized
    placeholders: dict[str, str] = {}
    for start, end, placeholder, value in sorted(replacements, reverse=True):
        protected = protected[:start] + placeholder + protected[end:]
        placeholders[placeholder] = value
    return ProtectedText(protected, entities, placeholders)


def restore_entities(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for placeholder, value in placeholders.items():
        restored = restored.replace(placeholder, value)
    return restored

