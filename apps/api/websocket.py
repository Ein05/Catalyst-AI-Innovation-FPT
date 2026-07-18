from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from core.asr.mock import MockASRProvider
from core.session.events import (
    AudioChunkMeta,
    ASRFinalEvent,
    ErrorEvent,
    ServerEvent,
    SessionStart,
    SessionStatusEvent,
    TranslationCompletedEvent,
    TranslationStartedEvent,
    make_asr_payload,
)
from core.session.manager import SessionManager
from core.session.routing import resolve_language_direction
from core.session.storage import SessionStorage
from core.session.state import UtteranceStatus
from core.translation.service import TranslationService
from core.session.state import SessionMode


class WebSocketEndpoint:
    def __init__(
        self, manager: SessionManager, storage: SessionStorage, translation_service: TranslationService
    ) -> None:
        self.manager = manager
        self.storage = storage
        self.translation_service = translation_service
        self.asr = MockASRProvider()
        self._pending_meta: dict[str, AudioChunkMeta] = {}
        self._tasks: dict[str, Any] = {}

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()

        async def publish(event: ServerEvent) -> None:
            self.storage.append_event(event)
            await websocket.send_json(event.serialize())

        try:
            while True:
                message = await websocket.receive()
                if "text" in message and message["text"] is not None:
                    await self._handle_text(message["text"], publish)
                elif "bytes" in message and message["bytes"] is not None:
                    await self._handle_audio(message["bytes"], publish)
        except WebSocketDisconnect:
            return

    async def _handle_text(self, text: str, publish) -> None:
        try:
            data: dict[str, Any] = json.loads(text)
            msg_type = data.get("type")
            if msg_type == "session.start":
                msg = SessionStart.model_validate(data)
                state = self.manager.start_session(msg.session_id, msg.mode)
                self.storage.create_session(msg.session_id, msg.mode)
                self._tasks[msg.session_id] = asyncio.create_task(self._run_pipeline(msg.session_id, publish))
                await publish(
                    SessionStatusEvent(
                        session_id=msg.session_id,
                        revision=state.bump_event_revision(),
                        payload={"status": "started", "mode": msg.mode},
                    )
                )
            elif msg_type == "session.end":
                session_id = data["session_id"]
                self.manager.end_session(session_id)
                task = self._tasks.pop(session_id, None)
                if task:
                    task.cancel()
                await publish(SessionStatusEvent(session_id=session_id, payload={"status": "ended"}))
            elif msg_type == "session.set_mode":
                state = self.manager.set_mode(data["session_id"], data["mode"])
                await publish(
                    SessionStatusEvent(
                        session_id=state.session_id,
                        revision=state.bump_event_revision(),
                        payload={"status": "mode_changed", "mode": state.mode},
                    )
                )
            elif msg_type == "audio.chunk_meta":
                meta = AudioChunkMeta.model_validate(data)
                self._pending_meta[meta.session_id] = meta
            elif msg_type == "turn.end":
                state = self.manager.get(data["session_id"])
                await self.manager.enqueue_asr(
                    state.session_id,
                    {"manual_end_turn": True},
                    is_final=True,
                    publisher=publish,
                )
            else:
                raise ValueError(f"unsupported message type {msg_type}")
        except Exception as exc:
            session_id = data.get("session_id", "unknown") if "data" in locals() else "unknown"
            await publish(ErrorEvent(session_id=session_id, payload={"message": str(exc)}))

    async def _handle_audio(self, audio: bytes, publish) -> None:
        if not self._pending_meta:
            await publish(ErrorEvent(session_id="unknown", payload={"message": "audio metadata missing"}))
            return
        session_id, meta = next(iter(self._pending_meta.items()))
        self._pending_meta.pop(session_id, None)
        await self.manager.receive_audio_chunk(session_id, meta.model_dump(), audio, publish)

    async def _run_pipeline(self, session_id: str, publish) -> None:
        queue = self.manager.audio_queues[session_id]
        while session_id in self.manager.sessions:
            item = await queue.get()
            state = self.manager.get(session_id)
            utterance = state.new_utterance()
            utterance.transition(UtteranceStatus.RECORDING)
            utterance.transition(UtteranceStatus.TRANSCRIBING)
            started = time.perf_counter()
            result = await self.asr.transcribe(
                item["audio"],
                item["meta"].get("sample_rate", 16000),
                language_hint="en" if state.mode == "manual_en" else None,
            )
            utterance.language = result.language
            utterance.source_text = result.text
            utterance.transition(UtteranceStatus.TRANSCRIPT_FINAL)
            revision = state.bump_event_revision(utterance.utterance_id)
            await publish(
                ASRFinalEvent(
                    session_id=session_id,
                    utterance_id=utterance.utterance_id,
                    revision=revision,
                    payload=make_asr_payload(
                        utterance.utterance_id,
                        utterance.speaker_id,
                        result.language,
                        result.confidence,
                        result.text,
                        True,
                        result.start_ms,
                        result.end_ms,
                        int((time.perf_counter() - started) * 1000),
                    ),
                )
            )
            utterance.transition(UtteranceStatus.TRANSLATING)
            source_lang, target_lang = resolve_language_direction(state, result.language, self.manager.config)
            translation_revision = state.bump_event_revision(utterance.utterance_id)
            await publish(
                TranslationStartedEvent(
                    session_id=session_id,
                    utterance_id=utterance.utterance_id,
                    revision=translation_revision,
                    payload={"source_language": source_lang, "target_language": target_lang},
                )
            )
            translated = await self.translation_service.translate_with_guardrails(
                result.text, source_lang, target_lang
            )
            if state.is_stale(utterance.utterance_id, translation_revision):
                continue
            utterance.translated_text = translated.translated_text
            utterance.transition(UtteranceStatus.COMPLETED)
            self.storage.save_transcript(
                session_id, utterance.utterance_id, result.text, translated.translated_text
            )
            await publish(
                TranslationCompletedEvent(
                    session_id=session_id,
                    utterance_id=utterance.utterance_id,
                    revision=state.bump_event_revision(utterance.utterance_id),
                    payload={
                        "source": result.text,
                        "translation": translated.translated_text,
                        "latency_ms": translated.latency_ms,
                        "warnings": translated.warnings,
                    },
                )
            )
            await asyncio.sleep(0)
