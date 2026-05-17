from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.hermes_operation_executor import (
    ExecutorError,
    OperationExecutor,
    resolve_item_source,
)


def make_operation(root: Path, op_id: str = "op_test_001", rel: str = "Show/E01.mkv") -> dict:
    return {
        "schema_version": 1,
        "operation_id": op_id,
        "operation_type": "move_to_trash",
        "status": "pending_approval",
        "created_at": "2026-05-17T00:00:00+00:00",
        "created_by": "video-review",
        "job": {"job_id": "job123", "name": "Test Job", "scan_path": "/media/download/Show", "current_dir": ""},
        "summary": {"item_count": 1, "total_size_bytes": 3},
        "path_mappings": {
            "download": {"container_root": "/media/download", "hermes_root": str(root)},
            "library": {"container_root": "/media/library", "hermes_root": str(root / "library")},
        },
        "items": [
            {
                "item_id": "item1",
                "file_name": Path(rel).name,
                "source_root": "download",
                "container_path": f"/media/download/{rel}",
                "relative_path": rel,
                "size_bytes": 3,
                "requested_action": "move_to_trash",
            }
        ],
        "approval": {"required": True, "executor": "hermes"},
    }


def write_pending(base: Path, operation: dict) -> Path:
    pending = base / "pending"
    pending.mkdir(parents=True)
    path = pending / f"{operation['operation_id']}.json"
    path.write_text(json.dumps(operation, ensure_ascii=False), encoding="utf-8")
    return path


def test_resolve_item_source_uses_mapping_and_relative_path(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    op = make_operation(root)

    resolved = resolve_item_source(op, op["items"][0])

    assert resolved == source.resolve(strict=True)


def test_resolve_item_source_blocks_sibling_prefix_escape(tmp_path):
    root = tmp_path / "download"
    root.mkdir()
    outside = tmp_path / "download_evil" / "E01.mkv"
    outside.parent.mkdir(parents=True)
    outside.write_text("abc", encoding="utf-8")
    op = make_operation(root, rel="../download_evil/E01.mkv")

    with pytest.raises(ExecutorError, match="outside allowed root"):
        resolve_item_source(op, op["items"][0])


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlink not supported")
def test_resolve_item_source_blocks_symlink_escape(tmp_path):
    root = tmp_path / "download"
    root.mkdir()
    outside = tmp_path / "outside.mkv"
    outside.write_text("abc", encoding="utf-8")
    link = root / "link.mkv"
    link.symlink_to(outside)
    op = make_operation(root, rel="link.mkv")

    with pytest.raises(ExecutorError, match="outside allowed root"):
        resolve_item_source(op, op["items"][0])


def test_execute_requires_exact_confirmation(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    op = make_operation(root)
    write_pending(operations, op)

    executor = OperationExecutor(operations)

    with pytest.raises(ExecutorError, match="confirmation"):
        executor.execute("op_test_001", confirm="wrong")

    assert source.exists()


def test_execute_moves_to_app_trash_and_marks_completed(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    op = make_operation(root)
    write_pending(operations, op)

    executor = OperationExecutor(operations)
    result = executor.execute("op_test_001", confirm="op_test_001")

    assert result["status"] == "completed"
    assert not source.exists()
    trash_path = Path(result["items"][0]["trash_path"])
    assert trash_path.exists()
    assert trash_path.read_text(encoding="utf-8") == "abc"
    assert ".video-review-trash" in trash_path.parts
    assert (operations / "completed" / "op_test_001.json").exists()
    assert not (operations / "pending" / "op_test_001.json").exists()


def test_execute_partial_failure_records_successful_moves(tmp_path, monkeypatch):
    root = tmp_path / "download"
    first = root / "Show" / "E01.mkv"
    second = root / "Show" / "E02.mkv"
    first.parent.mkdir(parents=True)
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    operations = tmp_path / "operations"
    op = make_operation(root)
    op["items"].append({**op["items"][0], "item_id": "item2", "file_name": "E02.mkv", "relative_path": "Show/E02.mkv"})
    op["summary"]["item_count"] = 2
    write_pending(operations, op)

    real_move = shutil.move

    def fail_second(src, dst):
        if str(src).endswith("E02.mkv"):
            raise OSError("simulated move failure")
        return real_move(src, dst)

    monkeypatch.setattr("scripts.hermes_operation_executor.shutil.move", fail_second)
    executor = OperationExecutor(operations)

    with pytest.raises(ExecutorError, match="simulated move failure"):
        executor.execute("op_test_001", confirm="op_test_001")

    failed = operations / "failed" / "op_test_001.json"
    data = json.loads(failed.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert len(data["execution"]["items"]) == 1
    assert data["execution"]["items"][0]["item_id"] == "item1"
    assert Path(data["execution"]["items"][0]["trash_path"]).exists()
    assert second.exists()


def test_execute_rejects_unexpected_source_root_even_if_mapping_exists(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    op = make_operation(root)
    op["path_mappings"]["evil"] = {"container_root": "/media/evil", "hermes_root": str(root)}
    op["items"][0]["source_root"] = "evil"
    write_pending(operations, op)

    executor = OperationExecutor(operations)

    with pytest.raises(ExecutorError, match="unsupported source_root"):
        executor.execute("op_test_001", confirm="op_test_001")


def test_execute_rejects_item_requested_action_mismatch(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    op = make_operation(root)
    op["items"][0]["requested_action"] = "permanent_delete"
    write_pending(operations, op)

    executor = OperationExecutor(operations)

    with pytest.raises(ExecutorError, match="requested_action"):
        executor.execute("op_test_001", confirm="op_test_001")


def test_execute_missing_source_marks_failed_without_moving_json_to_completed(tmp_path):
    root = tmp_path / "download"
    root.mkdir(parents=True)
    operations = tmp_path / "operations"
    op = make_operation(root)
    write_pending(operations, op)

    executor = OperationExecutor(operations)

    with pytest.raises(ExecutorError, match="source path does not exist"):
        executor.execute("op_test_001", confirm="op_test_001")

    failed = operations / "failed" / "op_test_001.json"
    assert failed.exists()
    data = json.loads(failed.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["execution"]["errors"]


def test_list_pending_returns_operation_summaries(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root))

    executor = OperationExecutor(operations)

    assert executor.list_pending() == [
        {
            "operation_id": "op_test_001",
            "job_name": "Test Job",
            "operation_type": "move_to_trash",
            "item_count": 1,
            "total_size_bytes": 3,
            "path": str(operations / "pending" / "op_test_001.json"),
        }
    ]
