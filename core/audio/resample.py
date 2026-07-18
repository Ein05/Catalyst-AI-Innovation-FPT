from __future__ import annotations

import numpy as np
from scipy import signal


def pcm16le_to_float32(audio: bytes) -> np.ndarray:
    if not audio:
        return np.array([], dtype=np.float32)
    return np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0


def float32_to_pcm16le(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def mono_mix(samples: np.ndarray, channels: int) -> np.ndarray:
    if channels <= 1:
        return samples
    usable = samples[: (len(samples) // channels) * channels]
    return usable.reshape(-1, channels).mean(axis=1)


def resample_audio(samples: np.ndarray, source_rate: int, target_rate: int = 16000) -> np.ndarray:
    if source_rate == target_rate:
        return samples.astype(np.float32, copy=False)
    expected_len = round(len(samples) * target_rate / source_rate)
    return signal.resample_poly(samples, target_rate, source_rate)[:expected_len].astype(np.float32)


def preprocess_pcm16(
    audio: bytes,
    sample_rate: int,
    channels: int,
    target_rate: int = 16000,
    high_pass_hz: int = 80,
) -> np.ndarray:
    samples = mono_mix(pcm16le_to_float32(audio), channels)
    samples = resample_audio(samples, sample_rate, target_rate)
    return high_pass_filter(samples, target_rate, high_pass_hz)


def high_pass_filter(samples: np.ndarray, sample_rate: int, cutoff_hz: int = 80) -> np.ndarray:
    if len(samples) == 0 or cutoff_hz <= 0:
        return samples
    sos = signal.butter(2, cutoff_hz, btype="highpass", fs=sample_rate, output="sos")
    return signal.sosfilt(sos, samples).astype(np.float32)

