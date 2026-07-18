from __future__ import annotations

from core.config import Config
from core.session.state import SessionState


def resolve_language_direction(
    state: SessionState,
    detected_language: str,
    config: Config,
) -> tuple[str, str]:
    if state.mode == "manual_vi" or state.mode == "seat_a":
        source = "vi"
    elif state.mode == "manual_en" or state.mode == "seat_b":
        source = "en"
    else:
        source = detected_language if detected_language in config.languages else "vi"
    available = list(config.languages.keys())
    targets = [lang for lang in available if lang != source]
    target = targets[0] if targets else source
    return (
        config.languages[source].translation_code,
        config.languages[target].translation_code,
    )

