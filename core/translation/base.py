from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranslationResult:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    latency_ms: int
    warnings: list[str]


class TranslationProvider(Protocol):
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
    ) -> TranslationResult: ...

