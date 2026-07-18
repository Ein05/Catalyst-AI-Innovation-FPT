from __future__ import annotations

import pytest

from core.session.events import EVENT_MODELS, ServerEvent


@pytest.mark.parametrize("model", EVENT_MODELS)
def test_event_round_trip(model):
    event = model(session_id="meeting-001", utterance_id="utt-102", revision=4, payload={"ok": True})
    serialized = event.serialize()
    restored = ServerEvent.deserialize(serialized)
    assert restored.event == event.event
    assert restored.revision == 4
    assert restored.payload == {"ok": True}

