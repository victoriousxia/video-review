#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path("/nas/docker/video-review")
OPERATIONS_DIR = REPO / "data" / "operations"
PENDING_DIR = OPERATIONS_DIR / "pending"
STATE_FILE = OPERATIONS_DIR / ".hermes-notified.json"
APPROVAL_SCRIPT = REPO / "scripts" / "hermes_operation_approval.py"
MAX_MESSAGE_CHARS = 3500


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"notified": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"notified": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def fingerprint(path: Path) -> str:
    stat = path.stat()
    h = hashlib.sha256()
    h.update(path.name.encode())
    h.update(str(stat.st_mtime_ns).encode())
    h.update(str(stat.st_size).encode())
    return h.hexdigest()


def approval_prompt(operation_id: str, platform: str) -> str:
    result = subprocess.run(
        [
            "python3",
            str(APPROVAL_SCRIPT),
            "--operations-dir",
            str(OPERATIONS_DIR),
            "prompt",
            operation_id,
            "--platform",
            platform,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    text = result.stdout.strip()
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[:MAX_MESSAGE_CHARS] + "\n... 内容过长，已截断。"
    return text


def send_message(target: str, message: str) -> None:
    code = (
        "from hermes_tools import send_message\n"
        f"send_message(action='send', target={target!r}, message={message!r})\n"
    )
    subprocess.run(["python3", "-c", code], check=True)


def main() -> int:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    notified = state.setdefault("notified", {})
    current_ids = set()
    new_count = 0

    for path in sorted(PENDING_DIR.glob("*.json")):
        operation_id = path.stem
        current_ids.add(operation_id)
        fp = fingerprint(path)
        if notified.get(operation_id) == fp:
            continue

        try:
            telegram_prompt = approval_prompt(operation_id, "weixin")
        except Exception as exc:
            print(f"failed to build approval prompt for {operation_id}: {exc}", file=sys.stderr)
            continue

        message = (
            "发现 video-review 待审批删除请求\n\n"
            f"{telegram_prompt}\n\n"
            "说明：回复/选择 1=扔垃圾桶，2=立刻删除（二次确认），3=取消。"
        )
        for target in ("telegram", "weixin"):
            try:
                send_message(target, message)
            except Exception as exc:
                print(f"failed to send {operation_id} to {target}: {exc}", file=sys.stderr)
        notified[operation_id] = fp
        new_count += 1

    for old_id in list(notified):
        if old_id not in current_ids:
            notified.pop(old_id, None)
    save_state(state)

    if new_count:
        print(f"sent {new_count} new video-review approval notification(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
