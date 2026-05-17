import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.operations import build_operation_request, derive_source_root, write_operation_request


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def job_with_items(client, tmp_path, monkeypatch):
    """Create a job and insert items marked as delete_later."""
    from app.config import get_settings
    from app.database import get_database

    settings = get_settings()
    download_root = tmp_path / "media" / "download"
    download_root.mkdir(parents=True)
    monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(download_root))

    get_settings.cache_clear()
    get_database.cache_clear()

    import app.main
    new_settings = get_settings()
    monkeypatch.setattr(app.main, "settings", new_settings)

    scan_dir = download_root / "TestShow"
    scan_dir.mkdir()
    video_file = scan_dir / "episode01.mkv"
    video_file.write_bytes(b"x" * 1024)

    resp = client.post("/api/v1/jobs", json={
        "name": "Test cleanup",
        "scan_path": str(scan_dir),
    })
    assert resp.status_code == 201
    job = resp.json()

    db = get_database()
    db.insert_items(job["job_id"], [{
        "original_path": str(video_file),
        "folder_path": str(scan_dir),
        "file_name": "episode01.mkv",
        "file_size": 1024,
        "extension": ".mkv",
        "file_mtime": "2026-01-01T00:00:00",
    }])

    items = db.list_items(job["job_id"])
    item_id = items[0]["item_id"]
    db.update_item(item_id, {"review_status": "delete_later"})

    return {
        "job": job,
        "item_id": item_id,
        "video_file": video_file,
        "scan_dir": scan_dir,
        "download_root": download_root,
    }


class TestDeleteFilesEndpoint:
    def test_creates_operation_request_without_deleting_file(self, client, job_with_items, tmp_path):
        ctx = job_with_items
        job_id = ctx["job"]["job_id"]

        resp = client.post(f"/api/v1/jobs/{job_id}/delete-files")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending_approval"
        assert body["operation_type"] == "move_to_trash"
        assert body["item_count"] == 1
        assert "operation_id" in body
        assert "operation_file" in body
        assert ctx["video_file"].exists(), "media file must NOT be deleted"

    def test_operation_json_written_to_pending_dir(self, client, job_with_items, tmp_path):
        ctx = job_with_items
        job_id = ctx["job"]["job_id"]

        resp = client.post(f"/api/v1/jobs/{job_id}/delete-files")
        body = resp.json()

        op_file = Path(body["operation_file"])
        assert op_file.exists()
        assert op_file.parent.name == "pending"
        assert op_file.suffix == ".json"

    def test_operation_json_has_all_required_fields(self, client, job_with_items):
        ctx = job_with_items
        job_id = ctx["job"]["job_id"]

        resp = client.post(f"/api/v1/jobs/{job_id}/delete-files")
        op_file = Path(resp.json()["operation_file"])
        data = json.loads(op_file.read_text())

        assert data["schema_version"] == 1
        assert data["operation_id"].startswith("op_")
        assert data["operation_type"] == "move_to_trash"
        assert data["status"] == "pending_approval"
        assert data["created_by"] == "video-review"
        assert "created_at" in data

        assert data["job"]["job_id"] == job_id
        assert data["job"]["name"] == "Test cleanup"
        assert "scan_path" in data["job"]
        assert "current_dir" in data["job"]

        assert data["summary"]["item_count"] == 1
        assert data["summary"]["total_size_bytes"] == 1024

        assert "download" in data["path_mappings"]
        assert "library" in data["path_mappings"]
        assert "container_root" in data["path_mappings"]["download"]
        assert "hermes_root" in data["path_mappings"]["download"]
        assert "container_root" in data["path_mappings"]["library"]
        assert "hermes_root" in data["path_mappings"]["library"]

        assert data["approval"]["required"] is True
        assert data["approval"]["executor"] == "hermes"

        item = data["items"][0]
        assert "item_id" in item
        assert item["file_name"] == "episode01.mkv"
        assert item["source_root"] in ("download", "library")
        assert item["relative_path"] == "TestShow/episode01.mkv"
        assert "container_path" in item
        assert item["size_bytes"] == 1024
        assert item["requested_action"] == "move_to_trash"

    def test_items_not_removed_from_database(self, client, job_with_items):
        ctx = job_with_items
        job_id = ctx["job"]["job_id"]

        client.post(f"/api/v1/jobs/{job_id}/delete-files")

        from app.database import get_database
        db = get_database()
        items = db.list_items(job_id)
        assert len(items) == 1
        assert items[0]["item_id"] == ctx["item_id"]

    def test_no_items_returns_400(self, client, tmp_path, monkeypatch):
        from app.config import get_settings
        from app.database import get_database

        settings = get_settings()
        download_root = tmp_path / "media" / "download"
        download_root.mkdir(parents=True)
        monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(download_root))
        get_settings.cache_clear()
        get_database.cache_clear()

        import app.main
        new_settings = get_settings()
        monkeypatch.setattr(app.main, "settings", new_settings)

        scan_dir = download_root / "Empty"
        scan_dir.mkdir()

        resp = client.post("/api/v1/jobs", json={
            "name": "Empty job",
            "scan_path": str(scan_dir),
        })
        job_id = resp.json()["job_id"]

        resp = client.post(f"/api/v1/jobs/{job_id}/delete-files")
        assert resp.status_code == 400
        assert "no items" in resp.json()["detail"]


class TestDeriveSourceRoot:
    def test_download_path(self, tmp_path):
        download = tmp_path / "download"
        library = tmp_path / "library"
        download.mkdir()
        library.mkdir()
        video = download / "show" / "ep.mkv"
        video.parent.mkdir()
        video.touch()

        key, rel = derive_source_root(video, download, library)
        assert key == "download"
        assert rel == "show/ep.mkv"

    def test_library_path(self, tmp_path):
        download = tmp_path / "download"
        library = tmp_path / "library"
        download.mkdir()
        library.mkdir()
        video = library / "movies" / "film.mp4"
        video.parent.mkdir()
        video.touch()

        key, rel = derive_source_root(video, download, library)
        assert key == "library"
        assert rel == "movies/film.mp4"

    def test_outside_root_raises(self, tmp_path):
        download = tmp_path / "download"
        library = tmp_path / "library"
        download.mkdir()
        library.mkdir()
        outside = tmp_path / "etc" / "passwd"
        outside.parent.mkdir()
        outside.touch()

        with pytest.raises(ValueError, match="not under"):
            derive_source_root(outside, download, library)


class TestBuildOperationRequest:
    def test_skips_items_outside_roots(self, tmp_path, monkeypatch):
        from app.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("VIDEO_REVIEW_DOWNLOAD_ROOT", str(tmp_path / "download"))
        monkeypatch.setenv("VIDEO_REVIEW_LIBRARY_ROOT", str(tmp_path / "library"))
        get_settings.cache_clear()
        settings = get_settings()

        (tmp_path / "download").mkdir()
        (tmp_path / "library").mkdir()

        job = {"job_id": "abc123", "name": "test", "scan_path": "/media/download/x"}
        items = [
            {
                "item_id": "good1",
                "original_path": str(tmp_path / "download" / "x" / "file.mkv"),
                "file_name": "file.mkv",
                "file_size": 500,
            },
            {
                "item_id": "bad1",
                "original_path": "/etc/passwd",
                "file_name": "passwd",
                "file_size": 100,
            },
        ]

        (tmp_path / "download" / "x").mkdir(parents=True)
        (tmp_path / "download" / "x" / "file.mkv").touch()

        request, skipped = build_operation_request(job, items, settings)

        assert len(request["items"]) == 1
        assert request["items"][0]["item_id"] == "good1"
        assert skipped == ["bad1"]

        get_settings.cache_clear()


class TestInfoEndpoint:
    def test_capabilities_include_operation_request_flags(self, client):
        resp = client.get("/api/v1/info")
        body = resp.json()

        assert body["capabilities"]["media_mutation"] is False
        assert body["capabilities"]["file_operation_requests"] is True
        assert body["capabilities"]["hermes_approval_required"] is True
        assert body["capabilities"]["trash_plan"] is True
        assert body["capabilities"]["trash_execute"] is False

    def test_safety_flags_match_review_only_architecture(self, client):
        resp = client.get("/api/v1/info")
        body = resp.json()

        assert body["safety"]["review_only"] is True
        assert body["safety"]["moves_files"] is False
        assert body["safety"]["deletes_files"] is False
        assert body["safety"]["creates_operation_requests"] is True
        assert body["safety"]["executor"] == "hermes"
        assert body["safety"]["approval_required"] is True


class TestAtomicWrite:
    def test_no_tmp_file_left_behind(self, tmp_path):
        request = {
            "operation_id": "op_test_123",
            "schema_version": 1,
        }
        pending = tmp_path / "pending"
        pending.mkdir()

        write_operation_request(request, pending)

        files = list(pending.iterdir())
        assert len(files) == 1
        assert files[0].name == "op_test_123.json"
        assert not (pending / "op_test_123.json.tmp").exists()
