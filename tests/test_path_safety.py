from pathlib import Path

from app.database import path_is_under
from app.scanner import scan_directory


def test_path_is_under_rejects_sibling_prefix(tmp_path):
    root = tmp_path / "media"
    sibling = tmp_path / "media-other"
    root.mkdir()
    sibling.mkdir()

    assert path_is_under(root, root)
    assert not path_is_under(sibling, root)


def test_path_is_under_rejects_symlink_escape(tmp_path):
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "linked-outside"
    link.symlink_to(outside, target_is_directory=True)

    assert not path_is_under(link, root)


def test_scan_directory_rejects_symlink_root_escape(tmp_path):
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.mp4").write_bytes(b"\x00" * 1024)
    link = root / "linked-outside"
    link.symlink_to(outside, target_is_directory=True)

    try:
        scan_directory(link, (root,))
    except ValueError as exc:
        assert "not under any allowed root" in str(exc)
    else:
        raise AssertionError("scan_directory should reject symlink roots escaping allowed roots")
