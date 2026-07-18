from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


@contextmanager
def span() -> Iterator[dict[str, int]]:
    started = perf_counter()
    data: dict[str, int] = {}
    try:
        yield data
    finally:
        data["duration_ms"] = int((perf_counter() - started) * 1000)

