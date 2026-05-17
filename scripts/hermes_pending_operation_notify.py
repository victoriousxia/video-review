#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path("/nas/docker/video-review")
sys.path.insert(0, str(REPO))

from scripts.hermes_operation_state import ApprovalStore

OPERATIONS_DIR = REPO / "data" / "operations"
APPROVAL_SCRIPT = REPO / "scripts" / "hermes_operation_approval.py"
MAX_MESSAGE_CHARS = 3500
DEFAULT_TARGETS = ("telegram", "weixin")


def fingerprint(path: Path) -> str:
    stat = path.stat()
    h = hashlib.sha256()
    h.update(path.name.encode("utf-8"))
    h.update(str(stat.st_mtime_ns).encode("utf-8"))
    h.update(str(stat.st_size).encode("utf-8"))
    return h.hexdigest()


def approval_prompt(operations_dir: Path, operation_id: str, platform: str) -> str:
    result = subprocess.run(
        [
            "python3",
            str(APPROVAL_SCRIPT),
            "--operations-dir",
            str(operations_dir),
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


def notification_already_sent(entry: dict[str, Any], target: str, fp: str) -> bool:
    for note in entry.get("notifications", {}).get(target, []):
        if note.get("fingerprint") == fp:
            return True
    return False


def record_notification_with_fingerprint(
    store: ApprovalStore,
    operation_id: str,
    *,
    target: str,
    fingerprint_value: str,
) -> None:
    store.record_notification(operation_id, platform=target, chat_id=target, session_key=target)
    state = store.load()
    entry = state["operations"][operation_id]
    notes = entry.setdefault("notifications", {}).setdefault(target, [])
    if notes:
        notes[-1]["fingerprint"] = fingerprint_value
    store.save(state)


def notify_operation(
    operation_id: str,
    *,
    operations_dir: Path = OPERATIONS_DIR,
    targets: tuple[str, ...] = DEFAULT_TARGETS,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    operation_file = operations_dir / "pending" / f"{operation_id}.json"
    if not operation_file.exists():
        raise FileNotFoundError(operation_file)
    fp = fingerprint(operation_file)
    store = ApprovalStore(operations_dir / ".hermes-approvals.json")
    entry = store.upsert_operation(operation_id)
    sent: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}

    for target in targets:
        if not force and notification_already_sent(entry, target, fp):
            skipped.append(target)
            continue
        try:
            platform = "telegram" if target.startswith("telegram") else "weixin"
            prompt = approval_prompt(operations_dir, operation_id, platform)
            message = (
                "发现 video-review 待审批删除请求\n\n"
                f"{prompt}\n\n"
                "说明：回复/选择 1=扔垃圾桶，2=立刻删除（二次确认），3=取消。"
            )
            if not dry_run:
                send_message(target, message)
            record_notification_with_fingerprint(store, operation_id, target=target, fingerprint_value=fp)
            sent.append(target)
        except Exception as exc:  # noqa: BLE001 - CLI reports per-target failures.
            errors[target] = str(exc)
    return {"operation_id": operation_id, "sent": sent, "skipped": skipped, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Immediately notify Hermes channels for a video-review pending operation")
    parser.add_argument("operation_id")
    parser.add_argument("--operations-dir", type=Path, default=OPERATIONS_DIR)
    parser.add_argument("--target", action="append", choices=["telegram", "weixin"], help="Can be repeated; default sends both")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = notify_operation(
        args.operation_id,
        operations_dir=args.operations_dir,
        targets=tuple(args.target or DEFAULT_TARGETS),
        force=args.force,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
