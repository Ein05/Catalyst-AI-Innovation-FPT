from __future__ import annotations

import pytest

from core.config import load_config
from core.session.manager import SessionManager
from core.session.state import UtteranceStatus


def test_session_transition_order():
    manager = SessionManager(load_config("offline"))
    state = manager.start_session("meeting-001")
    utt = state.new_utterance()
    for status in (
        UtteranceStatus.RECORDING,
        UtteranceStatus.TRANSCRIBING,
        UtteranceStatus.TRANSCRIPT_FINAL,
        UtteranceStatus.TRANSLATING,
        UtteranceStatus.COMPLETED,
    ):
        manager.transition_utterance("meeting-001", utt.utterance_id, status)
    assert utt.status is UtteranceStatus.COMPLETED


def test_bad_transition_rejected():
    manager = SessionManager(load_config("offline"))
    state = manager.start_session("meeting-001")
    utt = state.new_utterance()
    with pytest.raises(ValueError, match="invalid transition"):
        manager.transition_utterance("meeting-001", utt.utterance_id, UtteranceStatus.COMPLETED)

