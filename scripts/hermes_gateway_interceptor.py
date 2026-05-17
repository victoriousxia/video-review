#!/usr/bin/env python3
"""Hermes gateway interceptor for video-review approval replies.

This module intercepts Telegram/WeChat text messages before they reach the
normal LLM dispatch. If the message matches a video-review approval pattern,
it calls resolve-reply and returns the result to send back to the user.

Usage from Hermes gateway (import):

    from hermes_gateway_interceptor import try_intercept

    result = try_intercept(
        platform="telegram",
        chat_id="12345",
        text="1",
        thread_id=None,
        reply_to_message_id=None,
    )
    if result["handled"]:
        send_reply(result["message"])
        return  # skip LLM dispatch
    # else: continue normal Hermes flow

Usage from Hermes gateway (subprocess):

    python3 /nas/docker/video-review/scripts/hermes_gateway_interceptor.py \
      --platform telegram --chat-id 12345 --text "1"

    Returns JSON: {"handled": true/false, "message": "..."} on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OPERATIONS_DIR = Path("/nas/docker/video-review/data/operations")
RESOLVE_SCRIPT = SCRIPT_DIR / "hermes_operation_approval.py"

CHOICE_RE = re.compile(r"^\s*([123])(?:\s+\S+)?\s*$")
CONFIRM_RE = re.compile(r"^\s*DELETE_PERMANENTLY\s+\S+", re.IGNORECASE)


def looks_like_approval_reply(text: str) -> bool:
    """Quick check: could this text be a video-review approval reply?

    Returns True for: 1, 2, 3, 1 VR-XXXX, 2 VR-XXXX, 3 VR-XXXX,
    DELETE_PERMANENTLY <operation_id>.

    This is intentionally loose — the actual resolve-reply does the real
    matching against active approvals. This just avoids calling the resolver
    for obviously unrelated messages like "hello" or long sentences.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if CHOICE_RE.match(stripped):
        return True
    if CONFIRM_RE.match(stripped):
        return True
    return False


def try_intercept(
    *,
    platform: str,
    chat_id: str,
    text: str,
    thread_id: str | None = None,
    reply_to_message_id: str | None = None,
    operations_dir: Path | None = None,
    use_subprocess: bool = False,
) -> dict[str, Any]:
    """Attempt to intercept a message as a video-review approval reply.

    Returns:
        {"handled": False} if the message is not a video-review approval reply.
        {"handled": True, "message": "..."} if handled — send message back to user.
        {"handled": True, "ambiguous": True, "message": "..."} if ambiguous.
    """
    if not looks_like_approval_reply(text):
        return {"handled": False}

    ops_dir = operations_dir or DEFAULT_OPERATIONS_DIR

    if use_subprocess:
        return _resolve_via_subprocess(
            ops_dir, platform=platform, chat_id=chat_id,
            thread_id=thread_id, text=text,
            reply_to_message_id=reply_to_message_id,
        )

    return _resolve_via_import(
        ops_dir, platform=platform, chat_id=chat_id,
        thread_id=thread_id, text=text,
        reply_to_message_id=reply_to_message_id,
    )


def _resolve_via_import(
    operations_dir: Path,
    *,
    platform: str,
    chat_id: str,
    thread_id: str | None,
    text: str,
    reply_to_message_id: str | None,
) -> dict[str, Any]:
    """Call resolve_reply directly via Python import."""
    sys.path.insert(0, str(SCRIPT_DIR.parent))
    from scripts.hermes_operation_approval import resolve_reply

    result = resolve_reply(
        operations_dir,
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )
    return result


def _resolve_via_subprocess(
    operations_dir: Path,
    *,
    platform: str,
    chat_id: str,
    thread_id: str | None,
    text: str,
    reply_to_message_id: str | None,
) -> dict[str, Any]:
    """Call resolve-reply via subprocess (for cross-container isolation)."""
    cmd = [
        sys.executable, str(RESOLVE_SCRIPT),
        "--operations-dir", str(operations_dir),
        "resolve-reply",
        "--platform", platform,
        "--chat-id", chat_id,
        "--text", text,
    ]
    if thread_id:
        cmd.extend(["--thread-id", thread_id])
    if reply_to_message_id:
        cmd.extend(["--reply-to-message-id", reply_to_message_id])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"handled": False}

    if proc.returncode != 0:
        return {"handled": False}

    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"handled": False}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Intercept Telegram/WeChat messages for video-review approval"
    )
    parser.add_argument("--platform", required=True, choices=["telegram", "weixin"])
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--thread-id")
    parser.add_argument("--text", required=True)
    parser.add_argument("--reply-to-message-id")
    parser.add_argument("--operations-dir", type=Path, default=DEFAULT_OPERATIONS_DIR)
    parser.add_argument("--subprocess", action="store_true",
                        help="Use subprocess to call resolve-reply instead of direct import")
    args = parser.parse_args()

    result = try_intercept(
        platform=args.platform,
        chat_id=args.chat_id,
        text=args.text,
        thread_id=args.thread_id,
        reply_to_message_id=args.reply_to_message_id,
        operations_dir=args.operations_dir,
        use_subprocess=getattr(args, "subprocess", False),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
