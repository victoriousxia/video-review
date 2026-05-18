from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .frames import generate_frames_with_progress, list_frames


class _CancelledError(Exception):
    pass


@dataclass
class FrameTaskStatus:
    status: str = "idle"
    progress_current: int = 0
    progress_total: int = 0
    error: str | None = None


class FrameWorker:
    _MAX_TERMINAL_TASKS = 20

    def __init__(
        self,
        frames_dir: Path,
        max_workers: int = 2,
        default_count: int = 9,
        default_quality: int = 2,
        default_max_width: int = 0,
        default_skip_percent: int = 5,
        default_timeout: int = 30,
    ):
        self._frames_dir = frames_dir
        self._max_workers = max_workers
        self._default_count = default_count
        self._default_quality = default_quality
        self._default_max_width = default_max_width
        self._default_skip_percent = default_skip_percent
        self._default_timeout = default_timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._tasks: dict[str, FrameTaskStatus] = {}
        self._cancelled: set[str] = set()

    def submit(self, item_id: str, video_path: str, force: bool = False) -> dict:
        with self._lock:
            task = self._tasks.get(item_id)
            if task and task.status in ("queued", "generating") and not force:
                return self._status_dict(item_id, task)
            if force and task and task.status in ("queued", "generating"):
                self._cancelled.add(item_id)
            task = FrameTaskStatus(status="queued", progress_total=self._default_count)
            self._tasks[item_id] = task

        self._executor.submit(self._generate, item_id, video_path, force)
        return self._status_dict(item_id, task)

    def get_status(self, item_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(item_id)

        if task:
            return self._status_dict(item_id, task)

        output_dir = self._frames_dir / item_id
        frames = list_frames(output_dir)
        if frames:
            return {
                "status": "done",
                "progress": f"{len(frames)}/{len(frames)}",
                "error": None,
                "frames": [f"/frames/{item_id}/{f}" for f in frames],
            }

        return {"status": "idle", "progress": None, "error": None, "frames": []}

    def cancel(self, item_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(item_id)
            if not task or task.status not in ("queued", "generating"):
                return False
            self._cancelled.add(item_id)
            task.status = "cancelled"
            return True

    def cancel_all(self) -> int:
        with self._lock:
            count = 0
            for item_id, task in self._tasks.items():
                if task.status in ("queued", "generating"):
                    self._cancelled.add(item_id)
                    task.status = "cancelled"
                    count += 1
            return count

    def _generate(self, item_id: str, video_path: str, force: bool) -> None:
        with self._lock:
            if item_id in self._cancelled:
                self._cancelled.discard(item_id)
                self._tasks.pop(item_id, None)
                return
            task = self._tasks.get(item_id)
            if not task:
                return
            task.status = "generating"
            task.progress_current = 0

        output_dir = self._frames_dir / item_id

        def on_progress(current: int, total: int) -> None:
            with self._lock:
                if item_id in self._cancelled:
                    raise _CancelledError()
                t = self._tasks.get(item_id)
                if t:
                    t.progress_current = current
                    t.progress_total = total

        try:
            filenames = generate_frames_with_progress(
                Path(video_path),
                output_dir,
                count=self._default_count,
                quality=self._default_quality,
                max_width=self._default_max_width,
                skip_percent=self._default_skip_percent,
                timeout=self._default_timeout,
                randomize=force,
                on_progress=on_progress,
            )
            with self._lock:
                task = self._tasks.get(item_id)
                if task:
                    task.status = "done"
                    task.progress_current = len(filenames)
                    task.progress_total = len(filenames)
                    self._cleanup_old_tasks()
        except _CancelledError:
            with self._lock:
                self._cancelled.discard(item_id)
                self._tasks.pop(item_id, None)
        except Exception as exc:
            with self._lock:
                task = self._tasks.get(item_id)
                if task:
                    task.status = "failed"
                    task.error = str(exc)[:200]
                    self._cleanup_old_tasks()

    def _status_dict(self, item_id: str, task: FrameTaskStatus) -> dict:
        frames: list[str] = []
        if task.status == "done":
            output_dir = self._frames_dir / item_id
            filenames = list_frames(output_dir)
            frames = [f"/frames/{item_id}/{f}" for f in filenames]

        progress = None
        if task.status in ("generating", "done"):
            progress = f"{task.progress_current}/{task.progress_total}"

        return {
            "status": task.status,
            "progress": progress,
            "error": task.error,
            "frames": frames,
        }

    def _cleanup_old_tasks(self) -> None:
        terminal = [k for k, t in self._tasks.items() if t.status in ("done", "failed", "cancelled")]
        if len(terminal) > self._MAX_TERMINAL_TASKS:
            for k in terminal[:len(terminal) - self._MAX_TERMINAL_TASKS]:
                del self._tasks[k]
        active_ids = {k for k, t in self._tasks.items() if t.status in ("queued", "generating")}
        self._cancelled = self._cancelled & active_ids
