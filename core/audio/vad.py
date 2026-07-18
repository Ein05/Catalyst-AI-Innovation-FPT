from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from core.config import VADConfig


class VADModel(Protocol):
    def speech_probability(self, frame: np.ndarray, sample_rate: int) -> float: ...


class EnergyVADModel:
    def speech_probability(self, frame: np.ndarray, sample_rate: int) -> float:
        del sample_rate
        if len(frame) == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(frame))))
        return min(1.0, rms / 0.08)


class SileroVADModel:
    def __init__(self) -> None:
        try:
            from silero_vad import load_silero_vad  # type: ignore

            self.model = load_silero_vad()
        except Exception as exc:  # pragma: no cover - depends on local model cache.
            raise RuntimeError("Silero VAD is unavailable; install/cache silero-vad first") from exc

    def speech_probability(self, frame: np.ndarray, sample_rate: int) -> float:
        import torch

        tensor = torch.from_numpy(frame.astype(np.float32))
        return float(self.model(tensor, sample_rate).item())


@dataclass
class VADResult:
    speech_started: bool = False
    speech_ended: bool = False
    force_commit: bool = False
    start_ms: int | None = None
    end_ms: int | None = None
    speech_ms: int = 0
    silence_ms: int = 0
    probability: float = 0.0


class VADStateMachine:
    def __init__(
        self, config: VADConfig, sample_rate: int = 16000, model: VADModel | None = None
    ) -> None:
        self.config = config
        self.sample_rate = sample_rate
        self.model = model or EnergyVADModel()
        self.in_speech = False
        self.total_ms = 0
        self.speech_ms = 0
        self.silence_ms = 0
        self.candidate_speech_ms = 0
        self.start_ms: int | None = None
        self.frame_samples = int(sample_rate * config.frame_ms / 1000)
        self.pre_roll: deque[np.ndarray] = deque(
            maxlen=max(1, round(config.speech_pad_ms / config.frame_ms))
        )

    def accept_frame(self, frame: np.ndarray) -> VADResult:
        prob = self.model.speech_probability(frame, self.sample_rate)
        is_speech = prob >= self.config.speech_threshold
        result = VADResult(probability=prob)
        if is_speech:
            self.candidate_speech_ms += self.config.frame_ms
            self.silence_ms = 0
            if not self.in_speech and self.candidate_speech_ms >= self.config.min_speech_ms:
                self.in_speech = True
                self.start_ms = max(0, self.total_ms - self.candidate_speech_ms - self.config.speech_pad_ms)
                result.speech_started = True
                result.start_ms = self.start_ms
            if self.in_speech:
                self.speech_ms += self.config.frame_ms
        else:
            self.candidate_speech_ms = 0
            if self.in_speech:
                self.silence_ms += self.config.frame_ms
                if self.silence_ms >= self.config.min_silence_ms:
                    end_ms = self.total_ms + self.config.speech_pad_ms
                    result.speech_ended = True
                    result.end_ms = end_ms
                    self._reset_after_turn()
            self.pre_roll.append(frame)
        if self.in_speech and self.speech_ms >= self.config.max_turn_seconds * 1000:
            result.force_commit = True
            result.end_ms = self.total_ms
            self._reset_after_turn()
        self.total_ms += self.config.frame_ms
        result.speech_ms = self.speech_ms
        result.silence_ms = self.silence_ms
        return result

    def _reset_after_turn(self) -> None:
        self.in_speech = False
        self.speech_ms = 0
        self.silence_ms = 0
        self.candidate_speech_ms = 0
        self.start_ms = None

