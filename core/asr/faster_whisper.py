from __future__ import annotations

import asyncio

from core.asr.base import TranscriptionResult
from core.config import ASRConfig


class FasterWhisperProvider:
    def __init__(self, config: ASRConfig) -> None:
        self.config = config
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore

            device = "auto" if self.config.device == "auto" else self.config.device
            compute_type = "default" if self.config.compute_type == "auto" else self.config.compute_type
            self._model = WhisperModel(self.config.model, device=device, compute_type=compute_type)
        return self._model

    async def transcribe(
        self, audio: bytes, sample_rate: int, language_hint: str | None = None
    ) -> TranscriptionResult:
        return await asyncio.to_thread(self._transcribe_sync, audio, sample_rate, language_hint)

    def _transcribe_sync(
        self, audio: bytes, sample_rate: int, language_hint: str | None
    ) -> TranscriptionResult:
        import numpy as np

        samples = np.frombuffer(audio, dtype="<i2").astype("float32") / 32768.0
        model = self._load_model()
        segments, info = model.transcribe(samples, language=language_hint, vad_filter=False)
        text_parts: list[str] = []
        start_ms = 0
        end_ms = int(len(samples) / sample_rate * 1000)
        for segment in segments:
            text_parts.append(segment.text.strip())
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
        return TranscriptionResult(
            text=" ".join(part for part in text_parts if part),
            language=getattr(info, "language", language_hint or "unknown"),
            confidence=getattr(info, "language_probability", None),
            is_final=True,
            start_ms=start_ms,
            end_ms=end_ms,
        )

