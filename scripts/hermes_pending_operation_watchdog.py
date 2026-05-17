#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path("/nas/docker/video-review")
OPERATIONS_DIR = REPO / "data" / "operations"
PENDING_DIR = OPERATIONS_DIR / "pending"
NOTIFY_SCRIPT = REPO / "scripts" / "hermes_pending_operation_notify.py"


def main() -> int:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    new_count = 0
    failures = 0
    for path in sorted(PENDING_DIR.glob("*.json")):
        operation_id = path.stem
        result = subprocess.run(
            ["python3", str(NOTIFY_SCRIPT), operation_id, "--operations-dir", str(OPERATIONS_DIR)],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            if '"sent": []' not in result.stdout:
                new_count += 1
        else:
            failures += 1
            print(result.stderr or result.stdout, file=sys.stderr)
    if new_count:
        print(f"sent {new_count} video-review approval notification(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
