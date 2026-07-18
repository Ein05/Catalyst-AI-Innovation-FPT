from __future__ import annotations

import subprocess
import sys


def main() -> int:
    print("Starting backend at http://127.0.0.1:8000")
    return subprocess.call([sys.executable, "-m", "apps.api.main"])


if __name__ == "__main__":
    raise SystemExit(main())

