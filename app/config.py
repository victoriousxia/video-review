from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "video-review"
    host: str = Field(default="0.0.0.0", alias="VIDEO_REVIEW_HOST")
    port: int = Field(default=8818, alias="VIDEO_REVIEW_PORT")
    data_dir: Path = Field(default=Path("/app/data"), alias="VIDEO_REVIEW_DATA_DIR")
    public_base_url: str = Field(default="", alias="VIDEO_REVIEW_PUBLIC_BASE_URL")
    download_root: Path = Field(default=Path("/media/download"), alias="VIDEO_REVIEW_DOWNLOAD_ROOT")
    library_root: Path = Field(default=Path("/media/library"), alias="VIDEO_REVIEW_LIBRARY_ROOT")
    auth_mode: str = Field(default="proxy", alias="VIDEO_REVIEW_AUTH_MODE")
    app_token: str = Field(default="", alias="VIDEO_REVIEW_APP_TOKEN")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "video_review.db"

    @property
    def screenshot_dir(self) -> Path:
        return self.data_dir / "screenshots"


def load_version() -> str:
    for candidate in (Path("/app/VERSION"), Path(__file__).resolve().parents[1] / "VERSION"):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.1.0-dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
