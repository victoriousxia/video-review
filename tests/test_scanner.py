from pathlib import Path

import pytest

from app.scanner import ScannedFile, is_video_file, scan_directory


def test_is_video_file_recognizes_common_extensions():
    assert is_video_file(Path("movie.mp4"))
    assert is_video_file(Path("show.mkv"))
    assert is_video_file(Path("clip.avi"))
    assert is_video_file(Path("record.MOV"))
    assert is_video_file(Path("stream.ts"))


def test_is_video_file_rejects_non_video():
    assert not is_video_file(Path("readme.txt"))
    assert not is_video_file(Path("image.jpg"))
    assert not is_video_file(Path("music.mp3"))
    assert not is_video_file(Path("archive.zip"))
    assert not is_video_file(Path("subtitle.srt"))


def test_scan_directory_finds_video_files(tmp_path):
    (tmp_path / "movie.mp4").write_bytes(b"\x00" * 1024)
    (tmp_path / "show.mkv").write_bytes(b"\x00" * 2048)
    (tmp_path / "readme.txt").write_text("not a video")

    results = scan_directory(tmp_path, (tmp_path,))

    assert len(results) == 2
    names = {r.file_name for r in results}
    assert names == {"movie.mp4", "show.mkv"}


def test_scan_directory_recurses_subdirectories(tmp_path):
    sub = tmp_path / "season1"
    sub.mkdir()
    (sub / "ep01.mp4").write_bytes(b"\x00" * 512)
    (sub / "ep02.mkv").write_bytes(b"\x00" * 512)

    results = scan_directory(tmp_path, (tmp_path,))

    assert len(results) == 2
    assert all(r.folder_path == str(sub) for r in results)


def test_scan_directory_skips_temp_files(tmp_path):
    (tmp_path / "good.mp4").write_bytes(b"\x00" * 100)
    (tmp_path / ".hidden.mp4").write_bytes(b"\x00" * 100)
    (tmp_path / "downloading.mp4.part").write_bytes(b"\x00" * 100)
    (tmp_path / "incomplete.mkv.!qb").write_bytes(b"\x00" * 100)

    results = scan_directory(tmp_path, (tmp_path,))

    assert len(results) == 1
    assert results[0].file_name == "good.mp4"


def test_scan_directory_populates_all_fields(tmp_path):
    video = tmp_path / "test.mp4"
    video.write_bytes(b"\x00" * 4096)

    results = scan_directory(tmp_path, (tmp_path,))

    assert len(results) == 1
    item = results[0]
    assert item.original_path == str(video)
    assert item.folder_path == str(tmp_path)
    assert item.file_name == "test.mp4"
    assert item.file_size == 4096
    assert item.extension == ".mp4"
    assert item.file_mtime  # non-empty ISO string


def test_scan_directory_rejects_path_outside_allowed_roots(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="not under any allowed root"):
        scan_directory(outside, (allowed,))


def test_scan_directory_raises_on_nonexistent_path(tmp_path):
    missing = tmp_path / "no_such_dir"

    with pytest.raises(FileNotFoundError):
        scan_directory(missing, (tmp_path,))


def test_scan_directory_returns_empty_for_no_videos(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    results = scan_directory(tmp_path, (tmp_path,))

    assert results == []
