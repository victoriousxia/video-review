from pathlib import Path

from fastapi.testclient import TestClient

import app.main as app_main
from app.config import Settings
from app.database import get_database


def _setup(tmp_path, monkeypatch):
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
    return media, TestClient(app_main.app)


def test_post_jobs_form_creates_job_and_redirects(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)

    resp = client.post(
        "/jobs",
        data={"name": "Form Job", "scan_path": str(media), "notes": "from form"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/jobs/")

    job_id = resp.headers["location"].split("/jobs/")[1]
    detail = client.get(f"/api/v1/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["job"]["name"] == "Form Job"
    assert detail.json()["job"]["notes"] == "from form"


def test_post_jobs_form_with_scan_now_triggers_scan(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)
    (media / "video.mp4").write_bytes(b"\x00" * 1024)

    resp = client.post(
        "/jobs",
        data={"name": "Scan Now", "scan_path": str(media), "scan_now": "true"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    job_id = resp.headers["location"].split("/jobs/")[1]
    detail = client.get(f"/api/v1/jobs/{job_id}")
    assert detail.json()["job"]["status"] == "ready"
    assert detail.json()["job"]["total_items"] == 1


def test_post_jobs_form_rejects_invalid_path(tmp_path, monkeypatch):
    _media, client = _setup(tmp_path, monkeypatch)

    resp = client.post(
        "/jobs",
        data={"name": "Bad", "scan_path": "/etc/passwd"},
        follow_redirects=False,
    )

    assert resp.status_code == 400


def test_post_jobs_form_rejects_empty_name(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)

    resp = client.post(
        "/jobs",
        data={"name": "", "scan_path": str(media)},
        follow_redirects=False,
    )

    assert resp.status_code == 400


def test_job_detail_page_shows_scan_button_for_pending(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "Pending Job", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "开始扫描" in page.text


def test_job_detail_page_shows_rescan_button_for_ready(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "Ready Job", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]
    get_database().update_job_status(job_id, "ready", total_items=0)

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "重新扫描" in page.text


def test_job_detail_page_shows_rescan_button_for_failed(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "Failed Job", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]
    get_database().update_job_status(job_id, "failed")

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "重新扫描" in page.text


def test_post_job_scan_from_web_redirects(tmp_path, monkeypatch):
    media, client = _setup(tmp_path, monkeypatch)
    (media / "clip.mkv").write_bytes(b"\x00" * 512)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "Web Scan", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]

    resp = client.post(f"/jobs/{job_id}/scan", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/jobs/{job_id}"


def test_index_page_shows_create_form(tmp_path, monkeypatch):
    _media, client = _setup(tmp_path, monkeypatch)

    page = client.get("/")
    assert page.status_code == 200
    assert 'name="scan_path"' in page.text
    assert 'name="name"' in page.text


def test_index_page_shows_create_form(tmp_path, monkeypatch):
    _media, client = _setup(tmp_path, monkeypatch)

    page = client.get("/")
    assert page.status_code == 200
    assert 'name="scan_path"' in page.text
    assert 'name="name"' in page.text
