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
