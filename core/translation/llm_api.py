from __future__ import annotations

import os
import time

import httpx

from core.config import TranslationConfig
from core.translation.base import TranslationResult


PROMPT_TEMPLATE = """Translate the following business meeting utterance from {source_lang} to {target_lang}.
Requirements:
- Preserve meaning, intent, names, numbers, dates and commercial terms.
- Do not summarize.
- Do not explain.
- Do not add information.
- Produce only the translation.
- Use concise professional business language.

Glossary:
{glossary_entries_as_bullet_list}

Text:
{source_text}
"""


class LLMAPITranslationProvider:
    def __init__(self, config: TranslationConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        glossary: dict[str, str] | None = None,
    ) -> TranslationResult:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        glossary_lines = "\n".join(f"- {src} => {dst}" for src, dst in (glossary or {}).items()) or "- None"
        prompt = PROMPT_TEMPLATE.format(
            source_lang=source_language,
            target_lang=target_language,
            glossary_entries_as_bullet_list=glossary_lines,
            source_text=text,
        )
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.config.timeout_ms / 1000) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
        content = data.get("content", [])
        translated = "".join(part.get("text", "") for part in content if part.get("type") == "text").strip()
        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_language=source_language,
            target_language=target_language,
            latency_ms=int((time.perf_counter() - started) * 1000),
            warnings=[],
        )

