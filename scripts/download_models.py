from __future__ import annotations

from core.config import load_config


def main() -> int:
    config = load_config()
    print(f"ASR model target: {config.asr.model}")
    print(f"Local translation model target: {config.translation.local_model}")
    print("Model download is intentionally explicit; run provider CLIs or warm up once in deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

