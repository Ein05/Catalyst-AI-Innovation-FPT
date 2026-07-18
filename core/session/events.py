from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, Field


EventName: TypeAlias = Literal[
    "audio.received",
    "speech.started",
    "asr.partial",
    "asr.final",
    "translation.started",
    "translation.completed",
    "translation.failed",
    "utterance.corrected",
    "session.status",
    "error",
]


class ClientMessage(BaseModel):
    type: str
    session_id: str | None = None


class AudioChunkMeta(ClientMessage):
    type: Literal["audio.chunk_meta"]
    session_id: str
    sequence: int
    timestamp_ms: int
    sample_rate: int = 16000
    channels: int = 1
    byte_length: int


class SessionStart(ClientMessage):
    type: Literal["session.start"]
    session_id: str
    mode: Literal["auto", "manual_vi", "manual_en", "seat_a", "seat_b"] = "auto"


class ServerEvent(BaseModel):
    registry: ClassVar[dict[str, type["ServerEvent"]]] = {}

    event: EventName
    session_id: str
    utterance_id: str | None = None
    revision: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

    def serialize(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def deserialize(cls, data: dict[str, Any] | str) -> "ServerEvent":
        if isinstance(data, str):
            return cls.model_validate_json(data)
        event_name = data.get("event")
        model = cls.registry.get(event_name, cls)
        return model.model_validate(data)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        event_name = getattr(cls, "EVENT", None)
        if event_name:
            ServerEvent.registry[event_name] = cls


class AudioReceivedEvent(ServerEvent):
    EVENT: ClassVar[str] = "audio.received"
    event: Literal["audio.received"] = "audio.received"


class SpeechStartedEvent(ServerEvent):
    EVENT: ClassVar[str] = "speech.started"
    event: Literal["speech.started"] = "speech.started"


class ASRPartialEvent(ServerEvent):
    EVENT: ClassVar[str] = "asr.partial"
    event: Literal["asr.partial"] = "asr.partial"


class ASRFinalEvent(ServerEvent):
    EVENT: ClassVar[str] = "asr.final"
    event: Literal["asr.final"] = "asr.final"


class TranslationStartedEvent(ServerEvent):
    EVENT: ClassVar[str] = "translation.started"
    event: Literal["translation.started"] = "translation.started"


class TranslationCompletedEvent(ServerEvent):
    EVENT: ClassVar[str] = "translation.completed"
    event: Literal["translation.completed"] = "translation.completed"


class TranslationFailedEvent(ServerEvent):
    EVENT: ClassVar[str] = "translation.failed"
    event: Literal["translation.failed"] = "translation.failed"


class UtteranceCorrectedEvent(ServerEvent):
    EVENT: ClassVar[str] = "utterance.corrected"
    event: Literal["utterance.corrected"] = "utterance.corrected"


class SessionStatusEvent(ServerEvent):
    EVENT: ClassVar[str] = "session.status"
    event: Literal["session.status"] = "session.status"


class ErrorEvent(ServerEvent):
    EVENT: ClassVar[str] = "error"
    event: Literal["error"] = "error"


EVENT_MODELS: tuple[type[ServerEvent], ...] = (
    AudioReceivedEvent,
    SpeechStartedEvent,
    ASRPartialEvent,
    ASRFinalEvent,
    TranslationStartedEvent,
    TranslationCompletedEvent,
    TranslationFailedEvent,
    UtteranceCorrectedEvent,
    SessionStatusEvent,
    ErrorEvent,
)


def make_asr_payload(
    utterance_id: str,
    speaker_id: str,
    language: str,
    language_confidence: float | None,
    text: str,
    is_final: bool,
    start_ms: int,
    end_ms: int,
    asr_latency_ms: int,
) -> dict[str, Any]:
    return {
        "utterance_id": utterance_id,
        "speaker_id": speaker_id,
        "language": language,
        "language_confidence": language_confidence,
        "partial_text": "" if is_final else text,
        "final_text": text if is_final else "",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "asr_latency_ms": asr_latency_ms,
    }
