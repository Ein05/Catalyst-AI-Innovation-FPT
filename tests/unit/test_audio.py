from __future__ import annotations

import numpy as np

from core.audio.resample import high_pass_filter, resample_audio


def test_resample_length_44100_to_16000():
    samples = np.zeros(44100, dtype=np.float32)
    out = resample_audio(samples, 44100, 16000)
    assert abs(len(out) - 16000) <= 1


def test_high_pass_reduces_low_frequency():
    rate = 16000
    t = np.arange(rate, dtype=np.float32) / rate
    low = np.sin(2 * np.pi * 30 * t).astype(np.float32)
    filtered = high_pass_filter(low, rate, 80)
    assert float(np.sqrt(np.mean(filtered**2))) < float(np.sqrt(np.mean(low**2))) * 0.65

