from pathlib import Path

import app.main as app_main
from app.config import Settings
from app.database import get_database
from fastapi.testclient import TestClient

app = app_main.app


def test_scan_job_scans_directory_and_creates_items(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    (media / "movie.mp4").write_bytes(b"\x00" * 2048)
    (media / "show.mkv").write_bytes(b"\x00" * 4096)
    (media / "readme.txt").write_text("not a video")

    new_settings = Settings(
        VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"),
        VIDEO_REVIEW_DOWNLOAD_ROOT=str(media),
    )
    monkeypatch.setattr(app_main, "settings", new_settings)

    from app.config import get_settings

    get_settings.cache_clear()
    get_database.cache_clear()
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(media))

    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "scan test", "scan_path": str(media)},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["status"] == "pending"

    scan_resp = client.post(f"/api/v1/jobs/{job['job_id']}/scan")
    assert scan_resp.status_code == 200
    result = scan_resp.json()
    assert result["job"]["status"] == "ready"
    assert result["job"]["total_items"] == 2
    assert len(result["items"]) == 2

    names = {item["file_name"] for item in result["items"]}
    assert names == {"movie.mp4", "show.mkv"}

    for item in result["items"]:
        assert item["extension"] in (".mp4", ".mkv")
        assert item["file_size"] > 0
        assert item["file_mtime"]
        assert item["review_status"] == "pending"


def test_scan_job_returns_404_for_missing_job(tmp_path, monkeypatch):
    client = TestClient(app)
    resp = client.post("/api/v1/jobs/nonexistent123/scan")
    assert resp.status_code == 404


def test_scan_job_rejects_already_running_job(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()

    new_settings = Settings(
        VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"),
        VIDEO_REVIEW_DOWNLOAD_ROOT=str(media),
    )
    monkeypatch.setattr(app_main, "settings", new_settings)
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(media))

    from app.config import get_settings

    get_settings.cache_clear()
    get_database.cache_clear()

    client = TestClient(app)
    db = get_database()

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "running test", "scan_path": str(media)},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]
    db.update_job_status(job_id, "running")

    resp = client.post(f"/api/v1/jobs/{job_id}/scan")
    assert resp.status_code == 409


def test_scan_job_handles_nonexistent_scan_path(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    gone = media / "gone"

    new_settings = Settings(
        VIDEO_REVIEW_DATA_DIR=str(tmp_path / "data"),
        VIDEO_REVIEW_DOWNLOAD_ROOT=str(media),
    )
    monkeypatch.setattr(app_main, "settings", new_settings)
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(media))

    from app.config import get_settings

    get_settings.cache_clear()
    get_database.cache_clear()

    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "missing path", "scan_path": str(gone)},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    resp = client.post(f"/api/v1/jobs/{job_id}/scan")
    assert resp.status_code == 500
    assert "scan failed" in resp.json()["detail"]

    detail_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert detail_resp.json()["job"]["status"] == "failed"
