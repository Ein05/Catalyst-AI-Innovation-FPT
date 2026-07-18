from __future__ import annotations

from core.config import load_config


def test_load_profiles(monkeypatch):
    monkeypatch.delenv("APP_PROFILE", raising=False)
    assert load_config("default").audio.sample_rate == 16000
    assert load_config("demo").profile == "demo"
    assert load_config("offline").translation.provider == "local"


def test_env_profile_override(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "offline")
    assert load_config().privacy.mode == "local_only"


def test_env_nested_override(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "demo")
    monkeypatch.setenv("APP_TRANSLATION__TIMEOUT_MS", "1234")
    assert load_config().translation.timeout_ms == 1234

