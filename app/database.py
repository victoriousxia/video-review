from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Settings, get_settings

SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, settings: Settings):
        self.path = settings.database_path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    scan_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_items INTEGER NOT NULL DEFAULT 0,
                    reviewed_items INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_items (
                    item_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES review_jobs(job_id) ON DELETE CASCADE,
                    original_path TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL,
                    resolution TEXT NOT NULL DEFAULT '',
                    codec TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    suggested_action TEXT NOT NULL DEFAULT 'needs_review',
                    user_action TEXT NOT NULL DEFAULT '',
                    user_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def create_job(self, name: str, scan_path: str, notes: str = "") -> dict[str, Any]:
        self.init()
        now = utc_now_iso()
        job = {
            "job_id": uuid4().hex,
            "name": name,
            "scan_path": scan_path,
            "status": "ready",
            "total_items": 0,
            "reviewed_items": 0,
            "notes": notes or "",
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO review_jobs(
                    job_id, name, scan_path, status, total_items, reviewed_items, notes, created_at, updated_at
                ) VALUES (
                    :job_id, :name, :scan_path, :status, :total_items, :reviewed_items, :notes, :created_at, :updated_at
                )
                """,
                job,
            )
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_jobs ORDER BY created_at DESC, job_id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM review_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_items(self, job_id: str) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items WHERE job_id = ? ORDER BY file_name, item_id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def schema_info(self) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        return {
            "path": str(self.path),
            "schema_version": int(row["value"]) if row else SCHEMA_VERSION,
        }


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def path_is_under(candidate: Path, root: Path) -> bool:
    candidate_text = str(candidate)
    root_text = str(root)
    return candidate_text == root_text or candidate_text.startswith(root_text.rstrip("/") + "/")
