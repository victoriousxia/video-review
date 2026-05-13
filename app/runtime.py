from pathlib import Path

from .config import Settings


def ensure_data_dirs(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False
