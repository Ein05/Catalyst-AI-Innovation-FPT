from __future__ import annotations

import json
import logging
import sys
from typing import Any


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")


def log_event(level: str, event: str, **fields: Any) -> None:
    logging.getLogger("meeting_translator").log(
        getattr(logging, level.upper(), logging.INFO),
        json.dumps({"level": level.upper(), "event": event, **fields}, ensure_ascii=False),
    )

