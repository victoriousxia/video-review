from pathlib import Path

from .config import Settings


def ensure_data_dirs(settings: Settings) -> None:
    """Create application-owned writable directories.

    The service may mount media roots read-only, so startup only creates paths
    under the configured data directory.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.frames_dir.mkdir(parents=True, exist_ok=True)


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def path_is_writable(path: Path) -> bool:
    try:
        probe_dir = path if path.is_dir() else path.parent
        return probe_dir.exists() and probe_dir.is_dir() and probe_dir.stat().st_mode is not None
    except OSError:
        return False
