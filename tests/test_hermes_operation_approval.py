from __future__ import annotations

import json
from pathlib import Path

from scripts.hermes_operation_approval import resolve_reply, run_action, telegram_menu_payload, weixin_prompt
from scripts.hermes_operation_executor import OperationExecutor
from tests.test_hermes_operation_executor import make_operation, write_pending


def test_telegram_menu_payload_has_three_fixed_options(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root))
    plan = OperationExecutor(operations).build_plan("op_test_001")

    payload = telegram_menu_payload(plan)

    assert "video-review 删除审批" in payload["text"]
    keyboard = payload["reply_markup"]["inline_keyboard"]
    assert keyboard == [
        [
            {"text": "1. 扔垃圾桶", "callback_data": "vr|trash|op_test_001"},
            {"text": "2. 立刻删除", "callback_data": "vr|delete_request|op_test_001"},
        ],
        [{"text": "3. 取消", "callback_data": "vr|cancel|op_test_001"}],
    ]


def test_weixin_prompt_asks_for_reply_number(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root))
    plan = OperationExecutor(operations).build_plan("op_test_001")

    prompt = weixin_prompt(plan)

    assert "1. 扔垃圾桶" in prompt
    assert "2. 立刻删除" in prompt
    assert "3. 取消" in prompt
    assert "操作码: VR-" in prompt
    assert "请回复序号：1 / 2 / 3" in prompt


def test_run_action_choice_numbers_execute_safe_operations_and_delete_requires_explicit_confirmation(tmp_path):
    root = tmp_path / "download"
    operations = tmp_path / "operations"
    first = root / "Show" / "E01.mkv"
    first.parent.mkdir(parents=True)
    first.write_text("abc", encoding="utf-8")
    write_pending(operations, make_operation(root, op_id="op_trash", rel="Show/E01.mkv"))

    trash_result = run_action(operations, "op_trash", "1")

    assert trash_result["status"] == "completed"
    assert Path(trash_result["items"][0]["trash_path"]).exists()
    assert not first.exists()

    second = root / "Show" / "E02.mkv"
    second.write_text("abc", encoding="utf-8")
    write_pending(operations, make_operation(root, op_id="op_delete", rel="Show/E02.mkv"))

    delete_request = run_action(operations, "op_delete", "2")

    assert delete_request["status"] == "requires_confirmation"
    assert "DELETE_PERMANENTLY op_delete" in delete_request["confirm"]
    assert second.exists()

    delete_result = run_action(operations, "op_delete", "DELETE_PERMANENTLY op_delete")

    assert delete_result["action"] == "delete_permanently"
    assert not second.exists()
    completed = json.loads((operations / "completed" / "op_delete.json").read_text(encoding="utf-8"))
    assert completed["execution"]["action"] == "delete_permanently"

    third = root / "Show" / "E03.mkv"
    third.write_text("abc", encoding="utf-8")
    write_pending(operations, make_operation(root, op_id="op_cancel", rel="Show/E03.mkv"))

    cancel_result = run_action(operations, "op_cancel", "3")

    assert cancel_result["status"] == "rejected"
    assert third.exists()
    assert (operations / "rejected" / "op_cancel.json").exists()


def test_resolve_reply_matches_single_active_operation_and_marks_state(tmp_path):
    root = tmp_path / "download"
    source = root / "Show" / "E01.mkv"
    source.parent.mkdir(parents=True)
    source.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root, op_id="op_reply", rel="Show/E01.mkv"))

    # Pre-register notification (simulates notify script sending to weixin home)
    from scripts.hermes_operation_state import ApprovalStore
    store = ApprovalStore(operations / ".hermes-approvals.json")
    store.upsert_operation("op_reply")
    store.record_notification("op_reply", platform="weixin", chat_id="weixin")

    result = resolve_reply(
        operations,
        platform="weixin",
        chat_id="wx-chat",
        thread_id=None,
        text="1",
    )

    assert result["handled"] is True
    assert result["operation_id"] == "op_reply"
    assert "已扔垃圾桶" in result["message"]
    assert not source.exists()


def test_resolve_reply_reports_ambiguity_for_multiple_active_operations(tmp_path):
    root = tmp_path / "download"
    first = root / "Show" / "E01.mkv"
    second = root / "Show" / "E02.mkv"
    first.parent.mkdir(parents=True)
    first.write_text("abc", encoding="utf-8")
    second.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root, op_id="op_a", rel="Show/E01.mkv"))
    write_pending(operations, make_operation(root, op_id="op_b", rel="Show/E02.mkv"))

    # Pre-register notifications
    from scripts.hermes_operation_state import ApprovalStore
    store = ApprovalStore(operations / ".hermes-approvals.json")
    for op_id in ("op_a", "op_b"):
        store.upsert_operation(op_id)
        store.record_notification(op_id, platform="telegram", chat_id="telegram")

    result = resolve_reply(
        operations,
        platform="telegram",
        chat_id="tg-chat",
        thread_id="1902",
        text="1",
    )

    assert result["handled"] is True
    assert result["ambiguous"] is True
    assert "当前有多个" in result["message"]
    assert first.exists()
    assert second.exists()


def test_resolve_reply_token_selects_operation_when_multiple_active(tmp_path):
    root = tmp_path / "download"
    first = root / "Show" / "E01.mkv"
    second = root / "Show" / "E02.mkv"
    first.parent.mkdir(parents=True)
    first.write_text("abc", encoding="utf-8")
    second.write_text("abc", encoding="utf-8")
    operations = tmp_path / "operations"
    write_pending(operations, make_operation(root, op_id="op_a", rel="Show/E01.mkv"))
    write_pending(operations, make_operation(root, op_id="op_b", rel="Show/E02.mkv"))

    # Pre-register notifications
    from scripts.hermes_operation_state import ApprovalStore, operation_token
    store = ApprovalStore(operations / ".hermes-approvals.json")
    for op_id in ("op_a", "op_b"):
        store.upsert_operation(op_id)
        store.record_notification(op_id, platform="telegram", chat_id="telegram")

    token_b = operation_token("op_b")

    result = resolve_reply(
        operations,
        platform="telegram",
        chat_id="tg-chat",
        thread_id="1902",
        text=f"1 {token_b}",
    )

    assert result["handled"] is True
    assert result["operation_id"] == "op_b"
    assert first.exists()
    assert not second.exists()
