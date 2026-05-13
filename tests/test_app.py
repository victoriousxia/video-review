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
    assert body["capabilities"]["scan_jobs"] is False
    assert body["safety"]["review_only"] is True
    assert body["safety"]["moves_files"] is False
    assert body["safety"]["deletes_files"] is False


def test_index_page_renders_current_safety_state():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "video-review" in response.text
    assert "不会扫描、移动或删除任何视频" in response.text
