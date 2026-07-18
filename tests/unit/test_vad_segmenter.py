from __future__ import annotations

import numpy as np

from core.audio.segmenter import TurnSegmenter
from core.audio.vad import VADStateMachine
from core.config import load_config


def test_vad_silence_speech_silence():
    config = load_config("offline").vad
    vad = VADStateMachine(config)
    silence = np.zeros(vad.frame_samples, dtype=np.float32)
    speech = np.ones(vad.frame_samples, dtype=np.float32) * 0.2
    events = []
    for frame in [silence] * 10 + [speech] * 10 + [silence] * 20:
        events.append(vad.accept_frame(frame))
    assert any(event.speech_started for event in events)
    assert any(event.speech_ended for event in events)


def test_segmenter_rules():
    segmenter = TurnSegmenter()
    assert segmenter.observe(1000, silence_ms=500).should_commit
    assert segmenter.observe(13000).reason == "segment_duration"
    assert segmenter.observe(100, manual_end_turn=True).reason == "manual_end_turn_action"

