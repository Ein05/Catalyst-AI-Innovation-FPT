from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import PrivacyConfig
from core.session.events import ServerEvent


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "sessions"


class SessionStorage:
    def __init__(self, privacy: PrivacyConfig, root: Path = DATA_DIR) -> None:
        self.privacy = privacy
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "sessions.sqlite3"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, created_at TEXT, mode TEXT)"
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                utterance_id TEXT,
                source_text TEXT,
                translated_text TEXT,
                created_at TEXT
                )"""
            )

    def create_session(self, session_id: str, mode: str) -> None:
        if self.privacy.mode == "ephemeral" and not self.privacy.store_transcript:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions(session_id, created_at, mode) VALUES (?, ?, ?)",
                (session_id, datetime.now(timezone.utc).isoformat(), mode),
            )

    def save_transcript(
        self, session_id: str, utterance_id: str, source_text: str, translated_text: str
    ) -> None:
        if not self.privacy.store_transcript:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO transcripts(session_id, utterance_id, source_text, translated_text, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (session_id, utterance_id, source_text, translated_text, datetime.now(timezone.utc).isoformat()),
            )

    def append_event(self, event: ServerEvent) -> None:
        path = self.root / f"{event.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.serialize(), ensure_ascii=False) + "\n")

    def clear_session(self, session_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM transcripts WHERE session_id = ?", (session_id,))
        for suffix in (".jsonl", ".wav"):
            path = self.root / f"{session_id}{suffix}"
            if path.exists():
                path.unlink()

    def export_json(self, session_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT utterance_id, source_text, translated_text, created_at FROM transcripts WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        return {
            "session_id": session_id,
            "transcripts": [
                {
                    "utterance_id": row[0],
                    "source_text": row[1],
                    "translated_text": row[2],
                    "created_at": row[3],
                }
                for row in rows
            ],
        }
