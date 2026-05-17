from fastapi.testclient import TestClient

from app.main import app


def test_healthz_returns_service_identity():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "video-review"
    assert "version" in body


def test_info_exposes_integration_mode_and_paths():
    client = TestClient(app)

    response = client.get("/api/v1/info")

    assert response.status_code == 200
    body = response.json()
    assert body["integration_mode"] == "generic-service-with-optional-hermes-orchestration"
    assert body["download_root"]
    assert body["library_root"]
    assert body["jobs_dir"]
    assert body["logs_dir"]
    assert body["capabilities"]["review_web"] is True
    assert body["capabilities"]["scan_jobs"] is True
    assert body["capabilities"]["screenshot_batches"] is False
    assert body["capabilities"]["media_mutation"] is True
    assert body["safety"]["review_only"] is False
    assert body["safety"]["moves_files"] is False
    assert body["safety"]["deletes_files"] is True
    assert body["safety"]["delete_confirmation"] == "browser-confirm-dialog"


def test_index_page_renders():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "video-review" in response.text
    assert "新建任务" in response.text


def test_index_page_renders_empty_jobs():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "还没有任务" in response.text


def test_can_create_and_read_review_job_via_api(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path))
    from app.config import get_settings
    from app.database import get_database

    get_settings.cache_clear()
    get_database.cache_clear()

    try:
        client = TestClient(app)

        create_response = client.post(
            "/api/v1/jobs",
            json={"name": "Mantou review", "scan_path": "/media/download/Mantou", "notes": "manual trigger"},
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Mantou review"
        assert created["scan_path"] == "/media/download/Mantou"
        assert created["status"] == "pending"
        assert created["total_items"] == 0

        list_response = client.get("/api/v1/jobs")
        assert list_response.status_code == 200
        jobs = list_response.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == created["job_id"]

        detail_response = client.get(f"/api/v1/jobs/{created['job_id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["job"]["job_id"] == created["job_id"]
        assert detail["items"] == []
    finally:
        get_database.cache_clear()
        get_settings.cache_clear()


def test_create_job_rejects_paths_outside_allowed_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(tmp_path))
    from app.config import get_settings
    from app.database import get_database

    get_settings.cache_clear()
    get_database.cache_clear()

    try:
        client = TestClient(app)

        response = client.post(
            "/api/v1/jobs",
            json={"name": "bad", "scan_path": "/etc"},
        )

        assert response.status_code == 400
        assert "allowed media roots" in response.json()["detail"]
    finally:
        get_database.cache_clear()
        get_settings.cache_clear()
