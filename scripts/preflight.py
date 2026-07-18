from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import sys
from pathlib import Path


def main() -> int:
    checks = [
        ("Python version", sys.version_info >= (3, 11), "Install Python 3.11 or newer."),
        ("ASR package", has_module("faster_whisper"), "Run pip install -e ."),
        ("VAD package", has_module("silero_vad") or has_module("torch"), "Run pip install -e ."),
        ("Translation API/local", bool(os.getenv("ANTHROPIC_API_KEY")) or has_module("transformers"), "Set ANTHROPIC_API_KEY or run with --profile offline after installing local model deps."),
        ("Web port 8000", port_available(8000), "Stop the process using port 8000 or change the API port."),
        ("Disk space", shutil.disk_usage(Path.cwd()).free > 2 * 1024**3, "Free at least 2GB for logs/models."),
    ]
    failed = False
    for name, ok, action in checks:
        status = "OK" if ok else "ERROR"
        print(f"{status}: {name}")
        if not ok:
            print(f"ACTION: {action}")
            failed = True
    return 1 if failed else 0


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    raise SystemExit(main())

