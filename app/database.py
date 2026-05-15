from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Settings, get_settings

SCHEMA_VERSION = 2


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
                    extension TEXT NOT NULL DEFAULT '',
                    file_mtime TEXT NOT NULL DEFAULT '',
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
            self._migrate(conn)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def _migrate(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(review_items)").fetchall()}
        if "extension" not in cols:
            conn.execute("ALTER TABLE review_items ADD COLUMN extension TEXT NOT NULL DEFAULT ''")
        if "file_mtime" not in cols:
            conn.execute("ALTER TABLE review_items ADD COLUMN file_mtime TEXT NOT NULL DEFAULT ''")

    def create_job(self, name: str, scan_path: str, notes: str = "") -> dict[str, Any]:
        self.init()
        now = utc_now_iso()
        job = {
            "job_id": uuid4().hex,
            "name": name,
            "scan_path": scan_path,
            "status": "pending",
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

    def update_job_status(self, job_id: str, status: str, total_items: int | None = None) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            if total_items is not None:
                conn.execute(
                    "UPDATE review_jobs SET status = ?, total_items = ?, updated_at = ? WHERE job_id = ?",
                    (status, total_items, now, job_id),
                )
            else:
                conn.execute(
                    "UPDATE review_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                    (status, now, job_id),
                )

    def insert_items(self, job_id: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        now = utc_now_iso()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO review_items(
                    item_id, job_id, original_path, folder_path, file_name,
                    file_size, extension, file_mtime, review_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                [
                    (
                        uuid4().hex,
                        job_id,
                        item["original_path"],
                        item["folder_path"],
                        item["file_name"],
                        item["file_size"],
                        item["extension"],
                        item["file_mtime"],
                        now,
                        now,
                    )
                    for item in items
                ],
            )

    def replace_items(self, job_id: str, items: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute("DELETE FROM review_items WHERE job_id = ?", (job_id,))
            if items:
                conn.executemany(
                    """
                    INSERT INTO review_items(
                        item_id, job_id, original_path, folder_path, file_name,
                        file_size, extension, file_mtime, review_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    [
                        (
                            uuid4().hex,
                            job_id,
                            item["original_path"],
                            item["folder_path"],
                            item["file_name"],
                            item["file_size"],
                            item["extension"],
                            item["file_mtime"],
                            now,
                            now,
                        )
                        for item in items
                    ],
                )

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

    def delete_job(self, job_id: str) -> bool:
        with self.connect() as conn:
            conn.execute("DELETE FROM review_items WHERE job_id = ?", (job_id,))
            cur = conn.execute("DELETE FROM review_jobs WHERE job_id = ?", (job_id,))
        return cur.rowcount > 0

    def count_items_by_status(self, job_id: str, review_status: str, folder_prefix: str | None = None) -> int:
        with self.connect() as conn:
            if folder_prefix:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM review_items WHERE job_id = ? AND review_status = ? AND folder_path LIKE ?",
                    (job_id, review_status, folder_prefix + "%"),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM review_items WHERE job_id = ? AND review_status = ?",
                    (job_id, review_status),
                ).fetchone()
        return row["cnt"] if row else 0

    def list_items_by_status(self, job_id: str, review_status: str, folder_prefix: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if folder_prefix:
                rows = conn.execute(
                    "SELECT * FROM review_items WHERE job_id = ? AND review_status = ? AND folder_path LIKE ?",
                    (job_id, review_status, folder_prefix + "%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_items WHERE job_id = ? AND review_status = ?",
                    (job_id, review_status),
                ).fetchall()
        return [dict(row) for row in rows]

    def remove_items(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        with self.connect() as conn:
            for item_id in item_ids:
                old = conn.execute(
                    "SELECT review_status, job_id FROM review_items WHERE item_id = ?", (item_id,)
                ).fetchone()
                if old and old["review_status"] != "pending":
                    conn.execute(
                        "UPDATE review_jobs SET reviewed_items = MAX(0, reviewed_items - 1), total_items = MAX(0, total_items - 1) WHERE job_id = ?",
                        (old["job_id"],),
                    )
                elif old:
                    conn.execute(
                        "UPDATE review_jobs SET total_items = MAX(0, total_items - 1) WHERE job_id = ?",
                        (old["job_id"],),
                    )
                conn.execute("DELETE FROM review_items WHERE item_id = ?", (item_id,))

    def list_items(self, job_id: str, folder_prefix: str | None = None) -> list[dict[str, Any]]:
        self.init()
        with self.connect() as conn:
            if folder_prefix is None:
                rows = conn.execute(
                    "SELECT * FROM review_items WHERE job_id = ? ORDER BY file_name, item_id",
                    (job_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_items WHERE job_id = ? AND folder_path = ? ORDER BY file_name, item_id",
                    (job_id, folder_prefix),
                ).fetchall()
        return [dict(row) for row in rows]

    def directory_stats(self, job_id: str, scan_root: str) -> list[dict[str, Any]]:
        """Get subdirectory statistics for a given root within a job."""
        self.init()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT folder_path, review_status FROM review_items WHERE job_id = ?",
                (job_id,),
            ).fetchall()

        scan_root_normalized = scan_root.rstrip("/")
        subdirs: dict[str, dict[str, int]] = {}

        for row in rows:
            folder = row["folder_path"]
            if not folder.startswith(scan_root_normalized):
                continue
            relative = folder[len(scan_root_normalized):]
            if relative and not relative.startswith("/"):
                continue
            relative = relative.lstrip("/")

            if not relative:
                continue

            top_dir = relative.split("/")[0]
            if top_dir not in subdirs:
                subdirs[top_dir] = {"total": 0, "pending": 0, "reviewed": 0, "direct": 0}
            subdirs[top_dir]["total"] += 1
            if row["review_status"] == "pending":
                subdirs[top_dir]["pending"] += 1
            else:
                subdirs[top_dir]["reviewed"] += 1

            parts = relative.split("/")
            if len(parts) == 1:
                subdirs[top_dir]["direct"] += 1

        result = []
        for name, stats in sorted(subdirs.items()):
            result.append({"name": name, **stats})
        return result

    def schema_info(self) -> dict[str, Any]:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        return {
            "path": str(self.path),
            "schema_version": int(row["value"]) if row else SCHEMA_VERSION,
        }

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        self.init()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM review_items WHERE item_id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def update_item(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        if not updates:
            return self.get_item(item_id)
        now = utc_now_iso()
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id]
        with self.connect() as conn:
            if "review_status" in updates:
                old = conn.execute(
                    "SELECT review_status, job_id FROM review_items WHERE item_id = ?", (item_id,)
                ).fetchone()
                if old:
                    old_status = old["review_status"]
                    new_status = updates["review_status"]
                    if old_status == "pending" and new_status != "pending":
                        conn.execute(
                            "UPDATE review_jobs SET reviewed_items = reviewed_items + 1, updated_at = ? WHERE job_id = ?",
                            (now, old["job_id"]),
                        )
                    elif old_status != "pending" and new_status == "pending":
                        conn.execute(
                            "UPDATE review_jobs SET reviewed_items = MAX(0, reviewed_items - 1), updated_at = ? WHERE job_id = ?",
                            (now, old["job_id"]),
                        )
            conn.execute(
                f"UPDATE review_items SET {set_clause} WHERE item_id = ?",
                values,
            )
        return self.get_item(item_id)


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def path_is_under(candidate: Path, root: Path) -> bool:
    try:
        candidate_resolved = candidate.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        candidate_resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return True
