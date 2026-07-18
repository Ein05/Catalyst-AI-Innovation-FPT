from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Awaitable

from core.config import Config
from core.session.events import AudioReceivedEvent, SessionStatusEvent, ServerEvent
from core.session.queues import BoundedPriorityQueue, JobPriority
from core.session.state import SessionMode, SessionState, UtteranceStatus


Publisher = Callable[[ServerEvent], Awaitable[None]]


class SessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.sessions: dict[str, SessionState] = {}
        self.audio_queues: dict[str, asyncio.Queue[dict]] = {}
        self.asr_queues: dict[str, BoundedPriorityQueue] = {}
        self.translation_queues: dict[str, BoundedPriorityQueue] = {}

    def start_session(self, session_id: str, mode: SessionMode = "auto") -> SessionState:
        state = SessionState(session_id=session_id, mode=mode, config_snapshot=self.config.model_dump())
        self.sessions[session_id] = state
        self.audio_queues[session_id] = asyncio.Queue(self.config.queues.audio_max_items)
        self.asr_queues[session_id] = BoundedPriorityQueue(self.config.queues.asr_max_items)
        self.translation_queues[session_id] = BoundedPriorityQueue(
            self.config.queues.translation_max_items
        )
        return state

    def end_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.audio_queues.pop(session_id, None)
        self.asr_queues.pop(session_id, None)
        self.translation_queues.pop(session_id, None)

    def get(self, session_id: str) -> SessionState:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown session_id {session_id}") from exc

    def set_mode(self, session_id: str, mode: SessionMode) -> SessionState:
        state = self.get(session_id)
        state.mode = mode
        return state

    async def receive_audio_chunk(
        self,
        session_id: str,
        meta: dict,
        audio: bytes,
        publisher: Publisher | None = None,
    ) -> bool:
        state = self.get(session_id)
        queue = self.audio_queues[session_id]
        if queue.full():
            if publisher:
                await publisher(
                    SessionStatusEvent(
                        session_id=session_id,
                        revision=state.bump_event_revision(),
                        payload={"message": "processing delayed", "queue": "audio"},
                    )
                )
            return False
        await queue.put({"meta": meta, "audio": audio})
        state.audio_sequence = max(state.audio_sequence, int(meta.get("sequence", 0)))
        if publisher:
            await publisher(
                AudioReceivedEvent(
                    session_id=session_id,
                    revision=state.bump_event_revision(),
                    payload={"sequence": state.audio_sequence, "byte_length": len(audio)},
                )
            )
        return True

    async def enqueue_asr(
        self, session_id: str, payload: dict, is_final: bool, publisher: Publisher | None = None
    ) -> bool:
        state = self.get(session_id)
        queue = self.asr_queues[session_id]
        priority = JobPriority.FINAL_ASR if is_final else JobPriority.PARTIAL_ASR
        accepted = await queue.put(priority, "asr", payload, is_final)
        if not accepted and publisher:
            await publisher(
                SessionStatusEvent(
                    session_id=session_id,
                    revision=state.bump_event_revision(),
                    payload={"message": "processing delayed", "queue": "asr"},
                )
            )
        return accepted

    def transition_utterance(
        self, session_id: str, utterance_id: str, status: UtteranceStatus, reason: str | None = None
    ) -> None:
        self.get(session_id).active_utterances[utterance_id].transition(status, reason)

