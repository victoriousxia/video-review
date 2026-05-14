import sqlite3
from pathlib import Path

from app.config import Settings
from app.database import Database


def test_migrate_adds_missing_columns_to_old_schema(tmp_path):
    """Old v1 databases missing extension/file_mtime columns get them added on init."""
    db_path = tmp_path / "data" / "video_review.db"
    db_path.parent.mkdir(parents=True)

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1');

        CREATE TABLE review_jobs (
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

        CREATE TABLE review_items (
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
    conn.close()

    settings = Settings(VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"))
    db = Database(settings)
    db.init()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(review_items)").fetchall()]
    conn.close()

    assert "extension" in cols
    assert "file_mtime" in cols


def test_migrate_old_schema_allows_scan_insert(tmp_path):
    """After migration, inserting items with extension/file_mtime succeeds."""
    db_path = tmp_path / "data" / "video_review.db"
    db_path.parent.mkdir(parents=True)

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1');

        CREATE TABLE review_jobs (
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

        CREATE TABLE review_items (
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
    conn.close()

    settings = Settings(VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"))
    db = Database(settings)
    db.init()

    job = db.create_job(name="test", scan_path="/media/download/test")
    db.insert_items(job["job_id"], [
        {
            "original_path": "/media/download/test/movie.mp4",
            "folder_path": "/media/download/test",
            "file_name": "movie.mp4",
            "file_size": 1024,
            "extension": ".mp4",
            "file_mtime": "2025-01-01T00:00:00+00:00",
        }
    ])

    items = db.list_items(job["job_id"])
    assert len(items) == 1
    assert items[0]["extension"] == ".mp4"
    assert items[0]["file_mtime"] == "2025-01-01T00:00:00+00:00"


def test_replace_items_removes_old_items_before_insert(tmp_path):
    """replace_items deletes existing items for a job then inserts new ones."""
    settings = Settings(VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"))
    db = Database(settings)
    db.init()

    job = db.create_job(name="rescan", scan_path="/media/download/rescan")
    job_id = job["job_id"]

    db.insert_items(job_id, [
        {
            "original_path": "/media/download/rescan/old.mp4",
            "folder_path": "/media/download/rescan",
            "file_name": "old.mp4",
            "file_size": 100,
            "extension": ".mp4",
            "file_mtime": "2025-01-01T00:00:00+00:00",
        }
    ])
    assert len(db.list_items(job_id)) == 1

    db.replace_items(job_id, [
        {
            "original_path": "/media/download/rescan/new1.mkv",
            "folder_path": "/media/download/rescan",
            "file_name": "new1.mkv",
            "file_size": 200,
            "extension": ".mkv",
            "file_mtime": "2025-02-01T00:00:00+00:00",
        },
        {
            "original_path": "/media/download/rescan/new2.avi",
            "folder_path": "/media/download/rescan",
            "file_name": "new2.avi",
            "file_size": 300,
            "extension": ".avi",
            "file_mtime": "2025-02-01T00:00:00+00:00",
        },
    ])

    items = db.list_items(job_id)
    assert len(items) == 2
    names = {i["file_name"] for i in items}
    assert names == {"new1.mkv", "new2.avi"}


def test_replace_items_with_empty_list_clears_items(tmp_path):
    """replace_items with empty list removes all items for the job."""
    settings = Settings(VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"))
    db = Database(settings)
    db.init()

    job = db.create_job(name="clear", scan_path="/media/download/clear")
    job_id = job["job_id"]

    db.insert_items(job_id, [
        {
            "original_path": "/media/download/clear/x.mp4",
            "folder_path": "/media/download/clear",
            "file_name": "x.mp4",
            "file_size": 50,
            "extension": ".mp4",
            "file_mtime": "2025-01-01T00:00:00+00:00",
        }
    ])

    db.replace_items(job_id, [])
    assert db.list_items(job_id) == []
