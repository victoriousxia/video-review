from __future__ import annotations

from scripts.hermes_operation_state import (
    ApprovalStore,
    parse_reply_text,
)


def test_parse_reply_text_accepts_choice_token_and_confirm():
    assert parse_reply_text("1") == {"choice": "1", "token": None, "confirm_operation_id": None}
    assert parse_reply_text("2 VR-D21E") == {"choice": "2", "token": "VR-D21E", "confirm_operation_id": None}
    assert parse_reply_text("DELETE_PERMANENTLY op_test") == {
        "choice": None,
        "token": None,
        "confirm_operation_id": "op_test",
    }


def test_store_upsert_generates_stable_token_and_records_notification(tmp_path):
    store = ApprovalStore(tmp_path / ".hermes-approvals.json")

    entry = store.upsert_operation("op_test_001")
    again = store.upsert_operation("op_test_001")
    store.record_notification(
        "op_test_001",
        platform="weixin",
        chat_id="wx-chat",
        message_id="msg-1",
        session_key="weixin:wx-chat",
    )

    reloaded = ApprovalStore(tmp_path / ".hermes-approvals.json")
    saved = reloaded.get("op_test_001")

    assert entry["token"].startswith("VR-")
    assert again["token"] == entry["token"]
    assert saved["notifications"]["weixin"][0]["chat_id"] == "wx-chat"
    assert saved["notifications"]["weixin"][0]["message_id"] == "msg-1"


def test_find_match_allows_bare_choice_when_single_active_in_chat(tmp_path):
    store = ApprovalStore(tmp_path / ".hermes-approvals.json")
    store.upsert_operation("op_single", token="VR-ONE1")
    store.record_notification("op_single", platform="telegram", chat_id="tg-chat", thread_id="1902")

    match = store.find_match(platform="telegram", chat_id="tg-chat", thread_id="1902", text="1")

    assert match["status"] == "matched"
    assert match["operation_id"] == "op_single"
    assert match["choice"] == "1"


def test_find_match_requires_token_when_multiple_active_in_chat(tmp_path):
    store = ApprovalStore(tmp_path / ".hermes-approvals.json")
    store.upsert_operation("op_a", token="VR-AAAA")
    store.upsert_operation("op_b", token="VR-BBBB")
    store.record_notification("op_a", platform="weixin", chat_id="wx-chat")
    store.record_notification("op_b", platform="weixin", chat_id="wx-chat")

    ambiguous = store.find_match(platform="weixin", chat_id="wx-chat", thread_id=None, text="1")
    matched = store.find_match(platform="weixin", chat_id="wx-chat", thread_id=None, text="1 VR-BBBB")

    assert ambiguous["status"] == "ambiguous"
    assert {item["operation_id"] for item in ambiguous["candidates"]} == {"op_a", "op_b"}
    assert matched["status"] == "matched"
    assert matched["operation_id"] == "op_b"


def test_find_match_uses_reply_to_message_id(tmp_path):
    store = ApprovalStore(tmp_path / ".hermes-approvals.json")
    store.upsert_operation("op_reply", token="VR-REPL")
    store.record_notification(
        "op_reply",
        platform="telegram",
        chat_id="tg-chat",
        thread_id="1902",
        message_id="msg-approval",
    )

    match = store.find_match(
        platform="telegram",
        chat_id="tg-chat",
        thread_id="1902",
        text="3",
        reply_to_message_id="msg-approval",
    )

    assert match["status"] == "matched"
    assert match["operation_id"] == "op_reply"
    assert match["choice"] == "3"


def test_mark_resolved_removes_active_match(tmp_path):
    store = ApprovalStore(tmp_path / ".hermes-approvals.json")
    store.upsert_operation("op_done", token="VR-DONE")
    store.record_notification("op_done", platform="weixin", chat_id="wx-chat")

    store.mark_resolved("op_done", {"status": "completed"})
    match = store.find_match(platform="weixin", chat_id="wx-chat", thread_id=None, text="1 VR-DONE")

    assert match["status"] == "no_match"
    assert store.get("op_done")["status"] == "resolved"
