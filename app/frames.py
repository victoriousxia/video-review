from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path
from typing import Callable


def get_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    return float(result.stdout.strip())


def generate_frames(video_path: Path, output_dir: Path, count: int = 9, quality: int = 2) -> list[str]:
    return generate_frames_with_progress(video_path, output_dir, count, quality)


def generate_frames_with_progress(
    video_path: Path,
    output_dir: Path,
    count: int = 9,
    quality: int = 2,
    max_width: int = 0,
    skip_percent: int = 5,
    timeout: int = 30,
    randomize: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = get_duration(video_path)
    if duration <= 0:
        raise RuntimeError(f"invalid video duration: {duration}")

    skip_fraction = max(0, min(skip_percent, 45)) / 100.0
    start_time = duration * skip_fraction
    end_time = duration * (1 - skip_fraction)
    effective_duration = end_time - start_time
    step = effective_duration / (count + 1)

    timestamps = []
    for i in range(count):
        t = start_time + step * (i + 1)
        if randomize:
            jitter = random.uniform(-step * 0.4, step * 0.4)
            t = max(start_time, min(end_time, t + jitter))
        timestamps.append(t)

    vf_filters: list[str] = []
    if max_width > 0:
        vf_filters.append(f"scale='min({max_width},iw)':-2")

    filenames: list[str] = []
    last_error: str = ""
    for idx, ts in enumerate(timestamps):
        filename = f"frame_{idx:03d}.jpg"
        out_path = output_dir / filename
        cmd = [
            "ffmpeg", "-y", "-v", "quiet",
            "-ss", f"{ts:.3f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-qscale:v", str(quality),
        ]
        if vf_filters:
            cmd += ["-vf", ",".join(vf_filters)]
        cmd.append(str(out_path))
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if out_path.exists():
            filenames.append(filename)
        elif result.stderr:
            last_error = result.stderr.strip()[:200]
        if on_progress:
            on_progress(idx + 1, count)

    if not filenames:
        raise RuntimeError(f"ffmpeg produced no frames: {last_error}" if last_error else "ffmpeg produced no frames")
    return filenames


def list_frames(output_dir: Path) -> list[str]:
    if not output_dir.exists():
        return []
    return sorted(f.name for f in output_dir.iterdir() if f.suffix == ".jpg")


def remove_frames(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
