#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATE_FILE = Path("/nas/docker/video-review/data/operations/.hermes-approvals.json")
TOKEN_RE = re.compile(r"\bVR-[A-Za-z0-9]{4,12}\b", re.IGNORECASE)
CHOICE_RE = re.compile(r"^\s*([123])(?:\s+([A-Za-z0-9_-]+))?\s*$")
CONFIRM_RE = re.compile(r"^\s*DELETE_PERMANENTLY\s+([A-Za-z0-9_.-]+)\s*$", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def operation_token(operation_id: str) -> str:
    digest = hashlib.sha1(operation_id.encode("utf-8")).hexdigest()[:4].upper()
    return f"VR-{digest}"


def parse_reply_text(text: str) -> dict[str, str | None]:
    raw = (text or "").strip()
    confirm = CONFIRM_RE.match(raw)
    if confirm:
        return {"choice": None, "token": None, "confirm_operation_id": confirm.group(1)}

    choice = CHOICE_RE.match(raw)
    if choice:
        token = choice.group(2)
        return {"choice": choice.group(1), "token": token.upper() if token else None, "confirm_operation_id": None}

    token_match = TOKEN_RE.search(raw)
    return {"choice": None, "token": token_match.group(0).upper() if token_match else None, "confirm_operation_id": None}


class ApprovalStore:
    def __init__(self, path: Path = DEFAULT_STATE_FILE):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "operations": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schema_version": 1, "operations": {}}
        data.setdefault("schema_version", 1)
        data.setdefault("operations", {})
        return data

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, operation_id: str) -> dict[str, Any] | None:
        return self.load().get("operations", {}).get(operation_id)

    def upsert_operation(self, operation_id: str, *, token: str | None = None, expires_hours: int = 72) -> dict[str, Any]:
        state = self.load()
        operations = state.setdefault("operations", {})
        now = utc_now()
        entry = operations.get(operation_id) or {
            "operation_id": operation_id,
            "created_at": iso(now),
            "notifications": {},
        }
        entry.setdefault("operation_id", operation_id)
        entry.setdefault("created_at", iso(now))
        entry.setdefault("notifications", {})
        entry["token"] = (token or entry.get("token") or operation_token(operation_id)).upper()
        entry["status"] = entry.get("status") if entry.get("status") in {"awaiting_choice", "awaiting_delete_confirmation"} else "awaiting_choice"
        entry["expires_at"] = entry.get("expires_at") or iso(now + timedelta(hours=expires_hours))
        operations[operation_id] = entry
        self.save(state)
        return entry

    def record_notification(
        self,
        operation_id: str,
        *,
        platform: str,
        chat_id: str,
        thread_id: str | None = None,
        message_id: str | None = None,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        state = self.load()
        operations = state.setdefault("operations", {})
        entry = operations.get(operation_id) or self.upsert_operation(operation_id)
        # Reload after upsert to avoid overwriting concurrent fields.
        state = self.load()
        entry = state["operations"][operation_id]
        notifications = entry.setdefault("notifications", {}).setdefault(platform, [])
        record = {
            "chat_id": str(chat_id),
            "thread_id": str(thread_id) if thread_id is not None else None,
            "message_id": str(message_id) if message_id is not None else None,
            "session_key": session_key,
            "sent_at": iso(utc_now()),
        }
        if not any(
            str(item.get("chat_id")) == record["chat_id"]
            and str(item.get("thread_id")) == str(record["thread_id"])
            and str(item.get("message_id")) == str(record["message_id"])
            for item in notifications
        ):
            notifications.append(record)
        self.save(state)
        return entry

    def mark_resolved(self, operation_id: str, result: dict[str, Any]) -> None:
        state = self.load()
        entry = state.setdefault("operations", {}).get(operation_id)
        if not entry:
            return
        entry["status"] = "resolved"
        entry["resolved_at"] = iso(utc_now())
        entry["result"] = result
        self.save(state)

    def mark_delete_confirmation_requested(self, operation_id: str) -> None:
        state = self.load()
        entry = state.setdefault("operations", {}).get(operation_id)
        if not entry:
            return
        entry["status"] = "awaiting_delete_confirmation"
        entry["delete_confirmation_requested_at"] = iso(utc_now())
        self.save(state)

    def active_entries(self) -> list[dict[str, Any]]:
        now = utc_now()
        entries: list[dict[str, Any]] = []
        for entry in self.load().get("operations", {}).values():
            if entry.get("status") not in {"awaiting_choice", "awaiting_delete_confirmation"}:
                continue
            expires = parse_iso(entry.get("expires_at"))
            if expires and expires < now:
                continue
            entries.append(entry)
        return entries

    def _entry_matches_channel(self, entry: dict[str, Any], platform: str, chat_id: str, thread_id: str | None) -> bool:
        for note in entry.get("notifications", {}).get(platform, []):
            if str(note.get("chat_id")) != str(chat_id):
                continue
            note_thread = note.get("thread_id")
            if thread_id is not None and note_thread is not None and str(note_thread) != str(thread_id):
                continue
            return True
        return False

    def _entry_matches_reply_to(self, entry: dict[str, Any], platform: str, reply_to_message_id: str | None) -> bool:
        if reply_to_message_id is None:
            return False
        for note in entry.get("notifications", {}).get(platform, []):
            if note.get("message_id") is not None and str(note.get("message_id")) == str(reply_to_message_id):
                return True
        return False

    def find_match(
        self,
        *,
        platform: str,
        chat_id: str,
        thread_id: str | None,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        parsed = parse_reply_text(text)
        choice = parsed["choice"]
        token = parsed["token"]
        confirm_operation_id = parsed["confirm_operation_id"]
        active = self.active_entries()

        if confirm_operation_id:
            for entry in active:
                if entry.get("operation_id") == confirm_operation_id and self._entry_matches_channel(entry, platform, chat_id, thread_id):
                    return {"status": "matched", "operation_id": entry["operation_id"], "choice": text.strip(), "entry": entry}
            return {"status": "no_match"}

        if choice not in {"1", "2", "3"}:
            return {"status": "no_match"}

        channel_entries = [e for e in active if self._entry_matches_channel(e, platform, chat_id, thread_id)]
        if token:
            for entry in channel_entries:
                if str(entry.get("token", "")).upper() == token.upper():
                    return {"status": "matched", "operation_id": entry["operation_id"], "choice": choice, "entry": entry}
            return {"status": "no_match"}

        reply_matches = [e for e in channel_entries if self._entry_matches_reply_to(e, platform, reply_to_message_id)]
        if len(reply_matches) == 1:
            entry = reply_matches[0]
            return {"status": "matched", "operation_id": entry["operation_id"], "choice": choice, "entry": entry}

        if len(channel_entries) == 1:
            entry = channel_entries[0]
            return {"status": "matched", "operation_id": entry["operation_id"], "choice": choice, "entry": entry}
        if len(channel_entries) > 1:
            return {
                "status": "ambiguous",
                "choice": choice,
                "candidates": [
                    {"operation_id": e["operation_id"], "token": e.get("token")} for e in channel_entries
                ],
            }
        return {"status": "no_match"}
