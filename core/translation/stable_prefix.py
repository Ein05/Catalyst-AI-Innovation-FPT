from __future__ import annotations


def tokenize(text: str, language: str | None = None) -> list[str]:
    if language == "vi":
        try:
            from underthesea import word_tokenize

            return word_tokenize(text).split()
        except Exception:
            return text.split()
    return text.split()


def stable_prefix(previous: str, current: str, language: str | None = None) -> tuple[str, str]:
    prev_tokens = tokenize(previous, language)
    current_tokens = tokenize(current, language)
    index = 0
    while index < min(len(prev_tokens), len(current_tokens)):
        if prev_tokens[index] != current_tokens[index]:
            break
        index += 1
    return " ".join(current_tokens[:index]), " ".join(current_tokens[index:])

