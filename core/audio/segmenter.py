from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SegmentDecision:
    should_commit: bool
    reason: str | None = None


class TurnSegmenter:
    def __init__(self, silence_commit_ms: int = 450, max_segment_ms: int = 12000) -> None:
        self.silence_commit_ms = silence_commit_ms
        self.max_segment_ms = max_segment_ms
        self._stable_hits = 0
        self._last_stable = ""

    def observe(
        self,
        elapsed_ms: int,
        silence_ms: int = 0,
        transcript: str = "",
        stable_text: str = "",
        speaker_or_language_change: bool = False,
        manual_end_turn: bool = False,
    ) -> SegmentDecision:
        if manual_end_turn:
            return SegmentDecision(True, "manual_end_turn_action")
        if speaker_or_language_change:
            return SegmentDecision(True, "speaker_or_language_change")
        if silence_ms >= self.silence_commit_ms:
            return SegmentDecision(True, "silence")
        if elapsed_ms >= self.max_segment_ms:
            return SegmentDecision(True, "segment_duration")
        if stable_text and stable_text == self._last_stable:
            self._stable_hits += 1
        else:
            self._stable_hits = 1
            self._last_stable = stable_text
        if self._stable_hits >= 2 and transcript.rstrip().endswith((".", "?", "!")):
            return SegmentDecision(True, "punctuation_boundary")
        return SegmentDecision(False)

