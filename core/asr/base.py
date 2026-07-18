from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float | None
    is_final: bool
    start_ms: int
    end_ms: int


class ASRProvider(Protocol):
    async def transcribe(
        self, audio: bytes, sample_rate: int, language_hint: str | None = None
    ) -> TranscriptionResult: ...

