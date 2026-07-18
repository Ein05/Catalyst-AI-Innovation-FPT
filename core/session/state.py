from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


SessionMode = Literal["auto", "manual_vi", "manual_en", "seat_a", "seat_b"]


class UtteranceStatus(str, Enum):
    CREATED = "created"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    TRANSCRIPT_FINAL = "transcript_final"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"


ALLOWED_TRANSITIONS = {
    UtteranceStatus.CREATED: {UtteranceStatus.RECORDING, UtteranceStatus.FAILED},
    UtteranceStatus.RECORDING: {UtteranceStatus.TRANSCRIBING, UtteranceStatus.FAILED},
    UtteranceStatus.TRANSCRIBING: {UtteranceStatus.TRANSCRIPT_FINAL, UtteranceStatus.FAILED},
    UtteranceStatus.TRANSCRIPT_FINAL: {UtteranceStatus.TRANSLATING, UtteranceStatus.FAILED},
    UtteranceStatus.TRANSLATING: {UtteranceStatus.COMPLETED, UtteranceStatus.FAILED},
    UtteranceStatus.COMPLETED: set(),
    UtteranceStatus.FAILED: set(),
}


@dataclass
class UtteranceState:
    utterance_id: str
    status: UtteranceStatus = UtteranceStatus.CREATED
    speaker_id: str = "speaker-a"
    language: str | None = None
    source_text: str = ""
    translated_text: str = ""
    revision: int = 0
    failure_reason: str | None = None

    def transition(self, new_status: UtteranceStatus, reason: str | None = None) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"invalid transition {self.status.value} -> {new_status.value}")
        self.status = new_status
        if new_status is UtteranceStatus.FAILED:
            self.failure_reason = reason or "unknown failure"
        self.revision += 1


@dataclass
class SessionState:
    session_id: str
    mode: SessionMode = "auto"
    current_speaker: str = "speaker-a"
    next_utterance_index: int = 1
    audio_sequence: int = 0
    event_revision: int = 0
    active_utterances: dict[str, UtteranceState] = field(default_factory=dict)
    glossary_version: int = 0
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    latest_revision_by_utterance: dict[str, int] = field(default_factory=dict)

    def new_utterance(self) -> UtteranceState:
        utterance_id = f"utt-{self.next_utterance_index:04d}"
        self.next_utterance_index += 1
        utterance = UtteranceState(utterance_id=utterance_id, speaker_id=self.current_speaker)
        self.active_utterances[utterance_id] = utterance
        self.latest_revision_by_utterance[utterance_id] = utterance.revision
        return utterance

    def bump_event_revision(self, utterance_id: str | None = None) -> int:
        self.event_revision += 1
        if utterance_id:
            self.latest_revision_by_utterance[utterance_id] = self.event_revision
        return self.event_revision

    def is_stale(self, utterance_id: str, revision: int) -> bool:
        return revision < self.latest_revision_by_utterance.get(utterance_id, -1)

