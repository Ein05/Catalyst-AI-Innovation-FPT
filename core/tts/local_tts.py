from __future__ import annotations


class LocalTTSProvider:
    async def synthesize(self, text: str, language: str) -> bytes:
        del text, language
        return b""

