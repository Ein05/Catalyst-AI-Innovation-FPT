from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes.debug import router as debug_router
from apps.api.websocket import WebSocketEndpoint
from core.config import load_config
from core.observability.logging import configure_logging
from core.observability.metrics import MetricsRegistry
from core.session.manager import SessionManager
from core.session.storage import SessionStorage
from core.translation.service import TranslationService


def create_app() -> FastAPI:
    configure_logging()
    config = load_config()
    app = FastAPI(title="Real-Time Vietnamese-English Meeting Translator API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.config = config
    app.state.manager = SessionManager(config)
    app.state.storage = SessionStorage(config.privacy)
    app.state.metrics = MetricsRegistry()
    app.state.translation_service = TranslationService(config)
    app.include_router(debug_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "profile": config.profile}

    async def _handle_websocket(websocket: WebSocket) -> None:
        endpoint = WebSocketEndpoint(app.state.manager, app.state.storage, app.state.translation_service)
        await endpoint.handle(websocket)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await _handle_websocket(websocket)

    @app.websocket("/ws/ws")
    async def websocket_endpoint_compat(websocket: WebSocket) -> None:
        await _handle_websocket(websocket)

    return app


app = create_app()


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
