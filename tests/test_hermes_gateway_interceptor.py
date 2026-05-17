"""Tests for hermes_gateway_interceptor.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from hermes_gateway_interceptor import looks_like_approval_reply, try_intercept


class TestLooksLikeApprovalReply:
    """Quick regex filter — should pass approval patterns, reject everything else."""

    @pytest.mark.parametrize("text", [
        "1", "2", "3",
        " 1 ", " 2", "3 ",
        "1 VR-ABCD", "2 VR-D21E", "3 VR-xxxx",
        "1 some-token",
        "DELETE_PERMANENTLY op_20260517_153012_abcd1234",
        "delete_permanently op_test",
        "  DELETE_PERMANENTLY   op_123  ",
    ])
    def test_matches_approval_patterns(self, text):
        assert looks_like_approval_reply(text) is True

    @pytest.mark.parametrize("text", [
        "",
        "hello",
        "what's the weather",
        "12",
        "123",
        "4",
        "one",
        "帮我查一下天气",
        "I want to delete something",
        "delete file.txt",
        "1234 VR-ABCD",
    ])
    def test_rejects_non_approval_messages(self, text):
        assert looks_like_approval_reply(text) is False


class TestTryInterceptNoActiveApprovals:
    """When there are no pending operations, interceptor should return handled=false."""

    def test_non_approval_text_returns_immediately(self, tmp_path):
        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="hello world",
            operations_dir=tmp_path,
        )
        assert result == {"handled": False}

    def test_approval_text_no_pending_ops_returns_not_handled(self, tmp_path):
        pending = tmp_path / "pending"
        pending.mkdir(parents=True)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="1",
            operations_dir=tmp_path,
        )
        assert result["handled"] is False


class TestTryInterceptWithActiveApproval:
    """Integration test: single active approval, bare reply should work."""

    def _setup_pending_operation(self, ops_dir: Path) -> str:
        """Create a minimal pending operation JSON."""
        pending = ops_dir / "pending"
        pending.mkdir(parents=True, exist_ok=True)

        operation_id = "op_20260517_100000_test1234"
        op_data = {
            "schema_version": 1,
            "operation_id": operation_id,
            "operation_type": "move_to_trash",
            "status": "pending_approval",
            "created_at": "2026-05-17T10:00:00+00:00",
            "created_by": "video-review",
            "job": {
                "job_id": "testjob1",
                "name": "Test cleanup",
                "scan_path": "/media/download/TestShow",
                "current_dir": "",
            },
            "summary": {"item_count": 1, "total_size_bytes": 1024},
            "path_mappings": {
                "download": {
                    "container_root": "/media/download",
                    "hermes_root": str(ops_dir.parent / "download"),
                },
                "library": {
                    "container_root": "/media/library",
                    "hermes_root": str(ops_dir.parent / "media"),
                },
            },
            "items": [{
                "item_id": "item1",
                "file_name": "episode01.mkv",
                "source_root": "download",
                "container_path": "/media/download/TestShow/episode01.mkv",
                "relative_path": "TestShow/episode01.mkv",
                "size_bytes": 1024,
                "requested_action": "move_to_trash",
            }],
            "approval": {"required": True, "executor": "hermes"},
        }
        (pending / f"{operation_id}.json").write_text(
            json.dumps(op_data, ensure_ascii=False), encoding="utf-8"
        )

        # Create the source file so executor can move it
        download_dir = ops_dir.parent / "download" / "TestShow"
        download_dir.mkdir(parents=True, exist_ok=True)
        (download_dir / "episode01.mkv").write_bytes(b"x" * 1024)

        # Register notifications (simulates what the notify script does in production:
        # sends to "telegram"/"weixin" targets and records chat_id=platform_name).
        from scripts.hermes_operation_state import ApprovalStore
        store = ApprovalStore(ops_dir / ".hermes-approvals.json")
        store.upsert_operation(operation_id)
        store.record_notification(operation_id, platform="telegram", chat_id="telegram")
        store.record_notification(operation_id, platform="weixin", chat_id="weixin")

        return operation_id

    def test_choice_1_moves_to_trash(self, tmp_path):
        ops_dir = tmp_path / "operations"
        operation_id = self._setup_pending_operation(ops_dir)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="1",
            operations_dir=ops_dir,
        )

        assert result["handled"] is True
        assert "message" in result
        assert "垃圾桶" in result["message"]
        # Source file should have been moved
        source = tmp_path / "download" / "TestShow" / "episode01.mkv"
        assert not source.exists()

    def test_choice_2_requests_confirmation(self, tmp_path):
        ops_dir = tmp_path / "operations"
        operation_id = self._setup_pending_operation(ops_dir)

        result = try_intercept(
            platform="weixin",
            chat_id="wx_user_1",
            text="2",
            operations_dir=ops_dir,
        )

        assert result["handled"] is True
        assert "DELETE_PERMANENTLY" in result["message"]
        # File should NOT be deleted yet
        source = tmp_path / "download" / "TestShow" / "episode01.mkv"
        assert source.exists()

    def test_choice_3_rejects_operation(self, tmp_path):
        ops_dir = tmp_path / "operations"
        operation_id = self._setup_pending_operation(ops_dir)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="3",
            operations_dir=ops_dir,
        )

        assert result["handled"] is True
        assert "取消" in result["message"]
        # File should still exist
        source = tmp_path / "download" / "TestShow" / "episode01.mkv"
        assert source.exists()
        # Operation should be in rejected/
        assert (ops_dir / "rejected" / f"{operation_id}.json").exists()

    def test_normal_text_not_intercepted(self, tmp_path):
        ops_dir = tmp_path / "operations"
        self._setup_pending_operation(ops_dir)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="今天天气怎么样",
            operations_dir=ops_dir,
        )

        assert result["handled"] is False


class TestTryInterceptMultipleApprovals:
    """When multiple approvals are active, bare 1/2/3 should return ambiguity."""

    def _setup_two_pending(self, ops_dir: Path) -> tuple[str, str]:
        pending = ops_dir / "pending"
        pending.mkdir(parents=True, exist_ok=True)

        ids = []
        for i, suffix in enumerate(["aaaa1111", "bbbb2222"]):
            operation_id = f"op_20260517_10000{i}_{suffix}"
            ids.append(operation_id)
            op_data = {
                "schema_version": 1,
                "operation_id": operation_id,
                "operation_type": "move_to_trash",
                "status": "pending_approval",
                "created_at": f"2026-05-17T10:00:0{i}+00:00",
                "created_by": "video-review",
                "job": {
                    "job_id": f"job{i}",
                    "name": f"Job {i}",
                    "scan_path": "/media/download/Test",
                    "current_dir": "",
                },
                "summary": {"item_count": 1, "total_size_bytes": 512},
                "path_mappings": {
                    "download": {
                        "container_root": "/media/download",
                        "hermes_root": str(ops_dir.parent / "download"),
                    },
                    "library": {
                        "container_root": "/media/library",
                        "hermes_root": str(ops_dir.parent / "media"),
                    },
                },
                "items": [{
                    "item_id": f"item{i}",
                    "file_name": f"file{i}.mkv",
                    "source_root": "download",
                    "container_path": f"/media/download/Test/file{i}.mkv",
                    "relative_path": f"Test/file{i}.mkv",
                    "size_bytes": 512,
                    "requested_action": "move_to_trash",
                }],
                "approval": {"required": True, "executor": "hermes"},
            }
            (pending / f"{operation_id}.json").write_text(
                json.dumps(op_data, ensure_ascii=False), encoding="utf-8"
            )

        # Register notifications for both operations
        from scripts.hermes_operation_state import ApprovalStore
        store = ApprovalStore(ops_dir / ".hermes-approvals.json")
        for op_id in ids:
            store.upsert_operation(op_id)
            store.record_notification(op_id, platform="telegram", chat_id="telegram")

        return tuple(ids)

    def test_bare_choice_returns_ambiguity(self, tmp_path):
        ops_dir = tmp_path / "operations"
        self._setup_two_pending(ops_dir)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="1",
            operations_dir=ops_dir,
        )

        assert result["handled"] is True
        assert result.get("ambiguous") is True
        assert "操作码" in result["message"]


class TestTryInterceptSubprocess:
    """Test subprocess mode calls the script correctly."""

    def test_subprocess_mode_non_approval_text(self, tmp_path):
        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="hello",
            operations_dir=tmp_path,
            use_subprocess=False,
        )
        assert result["handled"] is False

    def test_subprocess_mode_no_pending(self, tmp_path):
        pending = tmp_path / "pending"
        pending.mkdir(parents=True)

        result = try_intercept(
            platform="telegram",
            chat_id="12345",
            text="1",
            operations_dir=tmp_path,
            use_subprocess=True,
        )
        assert result["handled"] is False
