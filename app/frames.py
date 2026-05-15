from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = get_duration(video_path)
    if duration <= 0:
        raise RuntimeError(f"invalid video duration: {duration}")

    timestamps = []
    for i in range(count):
        t = duration * (i + 1) / (count + 1)
        timestamps.append(t)

    filenames: list[str] = []
    for idx, ts in enumerate(timestamps):
        filename = f"frame_{idx:03d}.jpg"
        out_path = output_dir / filename
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-ss", f"{ts:.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-qscale:v", str(quality),
                str(out_path),
            ],
            capture_output=True,
            timeout=30,
        )
        if out_path.exists():
            filenames.append(filename)

    if not filenames:
        raise RuntimeError("ffmpeg produced no frames")
    return filenames


def list_frames(output_dir: Path) -> list[str]:
    if not output_dir.exists():
        return []
    return sorted(f.name for f in output_dir.iterdir() if f.suffix == ".jpg")


def remove_frames(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
