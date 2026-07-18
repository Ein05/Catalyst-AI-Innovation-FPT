from __future__ import annotations

from collections import defaultdict, deque
from statistics import median
from typing import DefaultDict


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: DefaultDict[str, int] = defaultdict(int)
        self.series: DefaultDict[str, deque[float]] = defaultdict(lambda: deque(maxlen=500))

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def observe(self, name: str, value: float) -> None:
        self.series[name].append(value)

    def snapshot(self) -> dict:
        return {
            "counters": dict(self.counters),
            "latency": {
                name: {"p50": _percentile(values, 50), "p95": _percentile(values, 95)}
                for name, values in self.series.items()
            },
        }


def _percentile(values: deque[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    if percentile == 50:
        return float(median(ordered))
    return float(ordered[index])

