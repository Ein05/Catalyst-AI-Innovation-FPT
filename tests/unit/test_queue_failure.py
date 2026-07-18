from __future__ import annotations

import pytest

from core.session.queues import BoundedPriorityQueue, JobPriority
from core.translation.service import CircuitBreaker


@pytest.mark.asyncio
async def test_queue_drops_partial_but_accepts_final():
    queue = BoundedPriorityQueue(1)
    assert await queue.put(JobPriority.PARTIAL_ASR, "asr", {"id": "p1"}, is_final=False)
    assert not await queue.put(JobPriority.PARTIAL_ASR, "asr", {"id": "p2"}, is_final=False)
    assert await queue.put(JobPriority.FINAL_ASR, "asr", {"id": "f1"}, is_final=True)
    job = await queue.get()
    assert job.payload["id"] == "f1"


def test_circuit_breaker_opens_after_three_failures():
    breaker = CircuitBreaker()
    assert breaker.allow_primary()
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.allow_primary()

