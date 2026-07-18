from __future__ import annotations

from dataclasses import dataclass

from core.translation.normalization import extract_entities


VI_NEGATIONS = ("khong", "không", "chua", "chưa", "khong the", "không thể")
EN_NEGATIONS = ("not", "cannot", "do not", "have not", "can't", "won't")


@dataclass
class ValidationResult:
    warnings: list[str]
    severe: bool = False


def validate_translation(source: str, translation: str, entities: dict[str, list[str]] | None = None) -> ValidationResult:
    warnings: list[str] = []
    source_entities = entities or extract_entities(source)
    lower_translation = translation.lower()
    for values in source_entities.values():
        for value in values:
            if value.lower() not in lower_translation:
                warnings.append(f"missing entity: {value}")
    source_lower = source.lower()
    source_has_negation = any(token in source_lower for token in VI_NEGATIONS + EN_NEGATIONS)
    target_has_negation = any(token in lower_translation for token in VI_NEGATIONS + EN_NEGATIONS)
    if source_has_negation and not target_has_negation:
        warnings.append("possible negation lost")
    source_words = max(1, len(source.split()))
    if len(translation.split()) / source_words > 1.8:
        warnings.append("possible added content")
    return ValidationResult(warnings=warnings, severe=any(w.startswith("missing entity") for w in warnings))

