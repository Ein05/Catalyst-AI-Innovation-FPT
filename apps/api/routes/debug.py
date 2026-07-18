from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/debug")
async def debug(request: Request) -> dict:
    app_state = request.app.state
    manager = app_state.manager
    metrics = app_state.metrics
    return {
        "backend": "meeting-translator-api",
        "model_loaded": False,
        "queue_depth": {
            session_id: {
                "audio": manager.audio_queues[session_id].qsize(),
                "asr": manager.asr_queues[session_id].depth(),
                "translation": manager.translation_queues[session_id].depth(),
            }
            for session_id in manager.sessions
        },
        "sessions": list(manager.sessions.keys()),
        "metrics": metrics.snapshot(),
        "last_error": getattr(app_state, "last_error", None),
    }

