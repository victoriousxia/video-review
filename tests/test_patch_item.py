from pathlib import Path

from fastapi.testclient import TestClient

import app.main as app_main
from app.config import Settings
from app.database import get_database


def _setup(tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    (media / "video.mp4").write_bytes(b"\x00" * 1024)

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
        json={"name": "Patch Test", "scan_path": str(media)},
    )
    job_id = create_resp.json()["job_id"]
    scan_resp = client.post(f"/api/v1/jobs/{job_id}/scan")
    item_id = scan_resp.json()["items"][0]["item_id"]

    return client, job_id, item_id


def test_patch_item_updates_review_status(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={"review_status": "keep"},
    )

    assert resp.status_code == 200
    assert resp.json()["review_status"] == "keep"


def test_patch_item_updates_user_action(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={"user_action": "move_later"},
    )

    assert resp.status_code == 200
    assert resp.json()["user_action"] == "move_later"


def test_patch_item_updates_user_notes(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={"user_notes": "good quality, keep it"},
    )

    assert resp.status_code == 200
    assert resp.json()["user_notes"] == "good quality, keep it"


def test_patch_item_updates_multiple_fields(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={
            "review_status": "delete_later",
            "user_action": "delete_later",
            "user_notes": "duplicate file",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "delete_later"
    assert data["user_action"] == "delete_later"
    assert data["user_notes"] == "duplicate file"


def test_patch_item_rejects_invalid_status(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={"review_status": "invalid_status"},
    )

    assert resp.status_code == 422


def test_patch_item_returns_404_for_missing_item(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    resp = client.patch(
        "/api/v1/items/nonexistent123",
        json={"review_status": "keep"},
    )

    assert resp.status_code == 404


def test_patch_item_persists_changes(tmp_path, monkeypatch):
    client, job_id, item_id = _setup(tmp_path, monkeypatch)

    client.patch(
        f"/api/v1/items/{item_id}",
        json={"review_status": "ignore", "user_notes": "not interesting"},
    )

    detail = client.get(f"/api/v1/jobs/{job_id}")
    items = detail.json()["items"]
    item = next(i for i in items if i["item_id"] == item_id)
    assert item["review_status"] == "ignore"
    assert item["user_notes"] == "not interesting"
