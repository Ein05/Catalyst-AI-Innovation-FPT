from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


class AudioConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    high_pass_hz: int = 80
    noise_suppression: bool = False


class VADConfig(BaseModel):
    provider: str = "silero"
    frame_ms: int = 32
    speech_threshold: float = 0.55
    min_speech_ms: int = 180
    min_silence_ms: int = 450
    speech_pad_ms: int = 180
    max_turn_seconds: int = 15


class ASRConfig(BaseModel):
    provider: str = "faster_whisper"
    model: str = "medium"
    device: str = "auto"
    compute_type: str = "auto"
    partial_interval_ms: int = 700
    hardware_profiles: dict[str, dict[str, str]] = Field(default_factory=dict)


class TranslationConfig(BaseModel):
    provider: str = "llm_api"
    model: str = "claude-sonnet-4-6"
    timeout_ms: int = 2500
    fallback: str = "local"
    local_model: str = "VietAI/envit5-translation"


class QueueConfig(BaseModel):
    audio_max_items: int = 200
    asr_max_items: int = 10
    translation_max_items: int = 20


class TimeoutConfig(BaseModel):
    partial_asr_ms: int = 1500
    final_asr_ms: int = 4000
    translation_ms: int = 3000
    tts_ms: int = 5000


class PrivacyConfig(BaseModel):
    mode: str = "ephemeral"
    store_audio: bool = False
    store_transcript: bool = False
    retention_days: int | None = None


class LanguageConfig(BaseModel):
    display_name: str
    asr_code: str
    translation_code: str


class Config(BaseModel):
    profile: str = "demo"
    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    queues: QueueConfig = Field(default_factory=QueueConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    languages: dict[str, LanguageConfig]


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(profile: str | None = None) -> Config:
    selected = os.getenv("APP_PROFILE") or profile or "default"
    data = _read_yaml(CONFIG_DIR / "default.yaml")
    if selected != "default":
        overlay_path = CONFIG_DIR / f"{selected}.yaml"
        if overlay_path.exists():
            data = _deep_merge(data, _read_yaml(overlay_path))
    for env_name, value in os.environ.items():
        if not env_name.startswith("APP_") or env_name == "APP_PROFILE":
            continue
        path = env_name[4:].lower().split("__")
        cursor: dict[str, Any] = data
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = _coerce_env_value(value)
    data["profile"] = selected if selected != "default" else data.get("profile", "default")
    return Config.model_validate(data)


def _coerce_env_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value

