from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .database import path_is_under

VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".ts", ".rmvb", ".rm", ".3gp", ".mpg", ".mpeg",
    ".vob", ".ogv", ".divx", ".asf", ".f4v", ".iso",
}


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _is_temp_or_partial(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith(".") or name.startswith("~"):
        return True
    if name.endswith(".part") or name.endswith(".downloading") or name.endswith(".tmp"):
        return True
    if name.endswith(".!qb") or name.endswith(".aria2"):
        return True
    return False


@dataclass
class ScannedFile:
    original_path: str
    folder_path: str
    file_name: str
    file_size: int
    extension: str
    file_mtime: str


def scan_directory(root: Path, allowed_roots: tuple[Path, ...]) -> list[ScannedFile]:
    if not any(path_is_under(root, allowed) for allowed in allowed_roots):
        raise ValueError(f"scan path {root} is not under any allowed root")

    if not root.exists():
        raise FileNotFoundError(f"scan path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"scan path is not a directory: {root}")

    results: list[ScannedFile] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if not is_video_file(fpath):
                continue
            if _is_temp_or_partial(fpath):
                continue
            try:
                stat = fpath.stat()
            except OSError:
                continue
            mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            results.append(
                ScannedFile(
                    original_path=str(fpath),
                    folder_path=str(fpath.parent),
                    file_name=fname,
                    file_size=stat.st_size,
                    extension=fpath.suffix.lower(),
                    file_mtime=mtime_dt.replace(microsecond=0).isoformat(),
                )
            )

    return results
