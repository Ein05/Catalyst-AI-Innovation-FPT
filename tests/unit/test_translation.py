from __future__ import annotations

import pytest

from core.config import load_config
from core.translation.glossary import GlossaryEntry, match_glossary
from core.translation.normalization import protect_entities, restore_entities
from core.translation.service import TranslationService
from core.translation.stable_prefix import stable_prefix
from core.translation.validator import validate_translation


def test_protect_restore_entities():
    source = "Chung toi dat muc tieu doanh thu 2.5 trieu SGD trong Q4 voi AI Singapore"
    protected = protect_entities(source)
    assert "<NUM_1>" in protected.text
    assert "<CUR_1>" in protected.text
    restored = restore_entities("Revenue is <CUR_1> <NUM_1> in <DATE_1> for <TERM_1>.", protected.placeholders)
    assert "SGD" in restored
    assert "2.5 trieu" in restored
    assert "Q4" in restored


def test_validator_flags_negation_lost():
    result = validate_translation(
        "We cannot deliver before Friday.",
        "Chung toi co the giao truoc thu Sau.",
        {"numbers": [], "dates": [], "currencies": [], "entities": []},
    )
    assert "possible negation lost" in result.warnings


def test_glossary_longest_priority():
    entries = [
        GlossaryEntry("bien ban", "minutes", "vi-en", priority=1),
        GlossaryEntry("bien ban ghi nho", "memorandum of understanding", "vi-en", priority=10),
    ]
    assert match_glossary("ky bien ban ghi nho", entries, "vi-en") == {
        "bien ban ghi nho": "memorandum of understanding"
    }


def test_stable_prefix():
    stable, unstable = stable_prefix(
        "Chung toi se giao hang vao",
        "Chung toi se giao hang vao thu sau",
    )
    assert stable == "Chung toi se giao hang vao"
    assert unstable == "thu sau"


@pytest.mark.asyncio
async def test_translation_service_local_fallback():
    service = TranslationService(load_config("offline"))
    result = await service.translate_with_guardrails(
        "Chung toi dat muc tieu doanh thu 2.5 trieu SGD trong Q4",
        "vi",
        "en",
    )
    assert "SGD" in result.translated_text
    assert "Q4" in result.translated_text

