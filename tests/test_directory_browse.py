from pathlib import Path

from fastapi.testclient import TestClient

import app.main as app_main
from app.config import Settings
from app.database import get_database


def _setup_with_scan(tmp_path, monkeypatch):
    """Create a media tree, set up settings, create a job, and scan it."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "root_video.mp4").write_bytes(b"\x00" * 1024)
    sub1 = media / "Movies"
    sub1.mkdir()
    (sub1 / "movie_a.mkv").write_bytes(b"\x00" * 2048)
    (sub1 / "movie_b.mp4").write_bytes(b"\x00" * 3072)
    sub2 = media / "Series"
    sub2.mkdir()
    (sub2 / "ep01.mp4").write_bytes(b"\x00" * 512)
    sub2_nested = sub2 / "Season1"
    sub2_nested.mkdir()
    (sub2_nested / "ep02.mkv").write_bytes(b"\x00" * 768)

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

    client = TestClient(app_main.app)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"name": "Dir Test", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]
    client.post(f"/api/v1/jobs/{job_id}/scan")

    return media, client, job_id


def test_job_detail_root_shows_directory_dashboard(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert "Movies" in resp.text
    assert "Series" in resp.text
    assert "root_video.mp4" in resp.text


def test_job_detail_with_dir_shows_subdirectory_files(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=Movies")
    assert resp.status_code == 200
    assert "movie_a.mkv" in resp.text
    assert "movie_b.mp4" in resp.text
    assert "root_video.mp4" not in resp.text


def test_job_detail_nested_dir(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=Series/Season1")
    assert resp.status_code == 200
    assert "ep02.mkv" in resp.text
    assert "ep01.mp4" not in resp.text


def test_job_detail_dir_shows_subdirectory_stats(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=Series")
    assert resp.status_code == 200
    assert "Season1" in resp.text
    assert "ep01.mp4" in resp.text


def test_job_detail_rejects_absolute_dir(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=/etc/passwd")
    assert resp.status_code == 400


def test_job_detail_rejects_dotdot_dir(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=../../../etc")
    assert resp.status_code == 400


def test_job_detail_rejects_dotdot_in_middle(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/jobs/{job_id}?dir=Movies/../../../etc")
    assert resp.status_code == 400


def test_api_job_detail_with_dir_filters_items(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/api/v1/jobs/{job_id}?dir=Movies")
    assert resp.status_code == 200
    data = resp.json()
    names = {item["file_name"] for item in data["items"]}
    assert names == {"movie_a.mkv", "movie_b.mp4"}


def test_api_job_detail_without_dir_returns_all(tmp_path, monkeypatch):
    media, client, job_id = _setup_with_scan(tmp_path, monkeypatch)

    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 5
