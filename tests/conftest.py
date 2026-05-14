import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    """Ensure all tests use a temporary data dir so they don't try to write to /app/data."""
    data_dir = tmp_path / "app_data"
    monkeypatch.setenv("VIDEO_REVIEW_DATA_DIR", str(data_dir))

    from app.config import get_settings
    from app.database import get_database

    get_settings.cache_clear()
    get_database.cache_clear()

    import app.main

    new_settings = get_settings()
    monkeypatch.setattr(app.main, "settings", new_settings)

    yield

    get_settings.cache_clear()
    get_database.cache_clear()
