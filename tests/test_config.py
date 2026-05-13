from pathlib import Path

from app.config import Settings


def test_settings_database_and_screenshot_paths_are_under_data_dir(tmp_path):
    settings = Settings(VIDEO_REVIEW_DATA_DIR=tmp_path)

    assert settings.database_path == tmp_path / "video_review.db"
    assert settings.screenshot_dir == tmp_path / "screenshots"


def test_default_roots_are_container_standard_paths():
    settings = Settings()

    assert settings.download_root == Path("/media/download")
    assert settings.library_root == Path("/media/library")
