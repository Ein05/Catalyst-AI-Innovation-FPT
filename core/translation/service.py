from __future__ import annotations

import asyncio
import time
from collections import deque

from core.config import Config
from core.translation.base import TranslationProvider, TranslationResult
from core.translation.glossary import GlossaryEntry, match_glossary
from core.translation.llm_api import LLMAPITranslationProvider
from core.translation.local_model import LocalModelTranslationProvider
from core.translation.normalization import protect_entities, restore_entities
from core.translation.validator import validate_translation


class CircuitBreaker:
    def __init__(self, threshold: int = 3, window_seconds: int = 30, cooldown_seconds: int = 60) -> None:
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.failures: deque[float] = deque()
        self.opened_at: float | None = None

    def allow_primary(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.failures.clear()
            return True
        return False

    def record_failure(self) -> None:
        now = time.monotonic()
        self.failures.append(now)
        while self.failures and now - self.failures[0] > self.window_seconds:
            self.failures.popleft()
        if len(self.failures) >= self.threshold:
            self.opened_at = now


class TranslationService:
    def __init__(
        self,
        config: Config,
        primary: TranslationProvider | None = None,
        fallback: TranslationProvider | None = None,
    ) -> None:
        self.config = config
        self.primary = primary or (
            LLMAPITranslationProvider(config.translation)
            if config.translation.provider == "llm_api"
            else LocalModelTranslationProvider(config.translation)
        )
        self.fallback = fallback or LocalModelTranslationProvider(config.translation)
        self.circuit_breaker = CircuitBreaker()
        self.retry_count = 0

    async def translate_with_guardrails(
        self,
        text: str,
        source_language: str,
        target_language: str,
        glossary_entries: list[GlossaryEntry] | None = None,
    ) -> TranslationResult:
        if not text.strip():
            return TranslationResult(text, "", source_language, target_language, 0, [])
        direction = f"{source_language}-{target_language}"
        glossary = match_glossary(text, glossary_entries or [], direction)
        protected = protect_entities(text)
        provider = self.primary if self.circuit_breaker.allow_primary() else self.fallback
        try:
            result = await self._translate_once(provider, protected.text, source_language, target_language, glossary)
        except Exception:
            self.circuit_breaker.record_failure()
            await asyncio.sleep(0.3)
            self.retry_count += 1
            try:
                result = await self._translate_once(self.primary, protected.text, source_language, target_language, glossary)
            except Exception:
                self.circuit_breaker.record_failure()
                result = await self._translate_once(self.fallback, protected.text, source_language, target_language, glossary)
        restored = restore_entities(result.translated_text, protected.placeholders)
        validation = validate_translation(text, restored, protected.entities)
        warnings = [*result.warnings, *validation.warnings]
        if validation.severe:
            self.retry_count += 1
            retry_text = protected.text + "\nMUST include all numbers and names exactly."
            retry = await self._translate_once(self.fallback, retry_text, source_language, target_language, glossary)
            retry_restored = restore_entities(retry.translated_text, protected.placeholders)
            retry_validation = validate_translation(text, retry_restored, protected.entities)
            restored = retry_restored
            warnings = [*retry.warnings, *retry_validation.warnings]
        return TranslationResult(text, restored, source_language, target_language, result.latency_ms, warnings)

    async def _translate_once(
        self,
        provider: TranslationProvider,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str],
    ) -> TranslationResult:
        return await asyncio.wait_for(
            provider.translate(text, source_language, target_language, glossary),
            timeout=self.config.timeouts.translation_ms / 1000,
        )

