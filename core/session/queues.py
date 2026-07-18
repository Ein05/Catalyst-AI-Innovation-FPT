from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class JobPriority(IntEnum):
    FINAL_ASR = 1
    FINAL_TRANSLATION = 2
    PARTIAL_ASR = 3
    TTS = 4
    SUMMARY = 5


@dataclass(order=True)
class QueueJob:
    priority: int
    sequence: int
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
    is_final: bool = field(default=False, compare=False)


class BoundedPriorityQueue:
    def __init__(self, max_items: int) -> None:
        self.max_items = max_items
        self._queue: asyncio.PriorityQueue[QueueJob] = asyncio.PriorityQueue(max_items)
        self.dropped_partial_count = 0
        self._sequence = 0

    def depth(self) -> int:
        return self._queue.qsize()

    async def put(self, priority: JobPriority, kind: str, payload: dict[str, Any], is_final: bool) -> bool:
        self._sequence += 1
        job = QueueJob(int(priority), self._sequence, kind, payload, is_final)
        if self._queue.full():
            if is_final:
                await self._drop_one_partial()
            else:
                self.dropped_partial_count += 1
                return False
        await self._queue.put(job)
        return True

    async def get(self) -> QueueJob:
        return await self._queue.get()

    async def _drop_one_partial(self) -> None:
        kept: list[QueueJob] = []
        dropped = False
        while not self._queue.empty():
            job = self._queue.get_nowait()
            if not dropped and not job.is_final:
                self.dropped_partial_count += 1
                dropped = True
                continue
            kept.append(job)
        for job in kept:
            await self._queue.put(job)
        if not dropped:
            await self._queue.get()

