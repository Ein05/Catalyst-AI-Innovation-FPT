from __future__ import annotations

from core.asr.base import TranscriptionResult


class MockASRProvider:
    async def transcribe(
        self, audio: bytes, sample_rate: int, language_hint: str | None = None
    ) -> TranscriptionResult:
        del audio, sample_rate
        language = language_hint or "vi"
        text = "Chung toi dat muc tieu doanh thu 2.5 trieu SGD trong Q4"
        if language == "en":
            text = "We cannot deliver before Friday."
        return TranscriptionResult(
            text=text,
            language=language,
            confidence=0.91,
            is_final=True,
            start_ms=0,
            end_ms=1000,
        )

