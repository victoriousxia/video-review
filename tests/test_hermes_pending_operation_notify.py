from __future__ import annotations

from scripts.hermes_pending_operation_notify import notify_operation
from scripts.hermes_operation_state import ApprovalStore
from tests.test_hermes_operation_executor import make_operation, write_pending


def test_notify_operation_records_state_and_is_idempotent(tmp_path, monkeypatch):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root, op_id="op_notify", rel="Show/E01.mkv"))
    sent: list[tuple[str, str]] = []

    monkeypatch.setattr("scripts.hermes_pending_operation_notify.send_message", lambda target, message: sent.append((target, message)))

    first = notify_operation("op_notify", operations_dir=operations, targets=("telegram", "weixin"))
    second = notify_operation("op_notify", operations_dir=operations, targets=("telegram", "weixin"))

    assert first["sent"] == ["telegram", "weixin"]
    assert second["skipped"] == ["telegram", "weixin"]
    assert len(sent) == 2
    assert all("操作码: VR-" in message for _, message in sent)
    state = ApprovalStore(operations / ".hermes-approvals.json")
    entry = state.get("op_notify")
    assert entry is not None
    assert entry["notifications"]["telegram"][0]["fingerprint"]


def test_notify_operation_force_resends(tmp_path, monkeypatch):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root, op_id="op_notify", rel="Show/E01.mkv"))
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr("scripts.hermes_pending_operation_notify.send_message", lambda target, message: sent.append((target, message)))

    notify_operation("op_notify", operations_dir=operations, targets=("telegram",))
    forced = notify_operation("op_notify", operations_dir=operations, targets=("telegram",), force=True)

    assert forced["sent"] == ["telegram"]
    assert len(sent) == 2
