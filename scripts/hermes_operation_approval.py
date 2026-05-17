#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.hermes_operation_state import ApprovalStore, operation_token

DEFAULT_OPERATIONS_DIR = Path("/nas/docker/video-review/data/operations")


def load_executor_module():
    sys.path.insert(0, str(SCRIPT_DIR.parent))
    from scripts.hermes_operation_executor import OperationExecutor, format_plan

    return OperationExecutor, format_plan


def summarize_plan(plan: dict[str, Any]) -> str:
    job_name = (plan.get("job") or {}).get("name", "")
    operation_id = plan["operation_id"]
    summary = plan.get("summary") or {}
    item_count = len(plan.get("items") or [])
    total_size = summary.get("total_size_bytes", 0)
    lines = [
        "video-review 删除审批",
        f"操作: {operation_id}",
        f"操作码: {operation_token(operation_id)}",
        f"任务: {job_name}",
        f"文件数: {item_count}",
        f"总大小: {total_size} bytes",
        "",
        "选项：",
        "1. 扔垃圾桶",
        "2. 立刻删除（永久删除，不进垃圾桶，需二次确认）",
        "3. 取消",
    ]
    for item in (plan.get("items") or [])[:5]:
        lines.append(f"- {item.get('file_name')}")
    if item_count > 5:
        lines.append(f"... 还有 {item_count - 5} 个文件")
    return "\n".join(lines)


def telegram_menu_payload(plan: dict[str, Any]) -> dict[str, Any]:
    op_id = plan["operation_id"]
    return {
        "text": summarize_plan(plan),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "1. 扔垃圾桶", "callback_data": f"vr|trash|{op_id}"},
                    {"text": "2. 立刻删除", "callback_data": f"vr|delete_request|{op_id}"},
                ],
                [{"text": "3. 取消", "callback_data": f"vr|cancel|{op_id}"}],
            ]
        },
    }


def weixin_prompt(plan: dict[str, Any]) -> str:
    return summarize_plan(plan) + "\n\n请回复序号：1 / 2 / 3"


def run_action(operations_dir: Path, operation_id: str, choice: str) -> dict[str, Any]:
    OperationExecutor, _ = load_executor_module()
    executor = OperationExecutor(operations_dir)
    normalized = choice.strip().lower()
    if normalized in {"1", "trash", "扔垃圾桶"}:
        return executor.execute(operation_id, confirm=operation_id)
    if normalized in {"2", "delete", "立刻删除"}:
        return {
            "status": "requires_confirmation",
            "operation_id": operation_id,
            "action": "delete_permanently",
            "confirm": f"DELETE_PERMANENTLY {operation_id}",
            "message": f"永久删除不会进入垃圾桶。如确认，请回复：DELETE_PERMANENTLY {operation_id}",
        }
    if normalized == f"delete_permanently {operation_id}" or normalized == f"delete_permanently {operation_id}".lower():
        return executor.delete_permanently(operation_id, confirm=f"DELETE_PERMANENTLY {operation_id}")
    if choice.strip() == f"DELETE_PERMANENTLY {operation_id}":
        return executor.delete_permanently(operation_id, confirm=choice.strip())
    if normalized in {"3", "cancel", "取消"}:
        op = executor.reject(operation_id, reason="cancelled by user")
        return {
            "status": "rejected",
            "operation_id": operation_id,
            "operation_file": str(executor.rejected_dir / f"{operation_id}.json"),
            "operation": op,
        }
    raise SystemExit(f"unknown choice: {choice}")


def user_message_for_result(result: dict[str, Any]) -> str:
    operation_id = result.get("operation_id", "")
    status = result.get("status")
    if status == "completed" and result.get("action") == "delete_permanently":
        return f"已永久删除 video-review 操作 {operation_id}。"
    if status == "completed":
        return f"已扔垃圾桶：video-review 操作 {operation_id} 已完成。"
    if status == "requires_confirmation":
        return result.get("message") or f"永久删除需要二次确认：DELETE_PERMANENTLY {operation_id}"
    if status == "rejected":
        return f"已取消 video-review 删除操作 {operation_id}。"
    return json.dumps(result, ensure_ascii=False)


def send_text(target: str, message: str) -> None:
    code = (
        "from hermes_tools import send_message\n"
        f"send_message(action='send', target={target!r}, message={message!r})\n"
    )
    subprocess.run(["python3", "-c", code], check=True)


def _ensure_state_for_pending_operations(operations_dir: Path, platform: str, chat_id: str, thread_id: str | None) -> ApprovalStore:
    store = ApprovalStore(operations_dir / ".hermes-approvals.json")
    pending_dir = operations_dir / "pending"
    for path in sorted(pending_dir.glob("*.json")):
        operation_id = path.stem
        store.upsert_operation(operation_id)
        store.record_notification(operation_id, platform=platform, chat_id=chat_id, thread_id=thread_id)
    return store


def resolve_reply(
    operations_dir: Path,
    *,
    platform: str,
    chat_id: str,
    thread_id: str | None,
    text: str,
    reply_to_message_id: str | None = None,
) -> dict[str, Any]:
    store = _ensure_state_for_pending_operations(operations_dir, platform, chat_id, thread_id)
    match = store.find_match(
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )
    if match["status"] == "no_match":
        return {"handled": False}
    if match["status"] == "ambiguous":
        choices = ", ".join(f"{item['operation_id']}({item.get('token')})" for item in match.get("candidates", []))
        return {
            "handled": True,
            "ambiguous": True,
            "message": f"当前有多个 video-review 待处理删除请求，请回复：{match.get('choice')} 操作码。可选：{choices}",
            "candidates": match.get("candidates", []),
        }

    operation_id = match["operation_id"]
    result = run_action(operations_dir, operation_id, str(match["choice"]))
    if result.get("status") == "requires_confirmation":
        store.mark_delete_confirmation_requested(operation_id)
    else:
        store.mark_resolved(operation_id, result)
    return {
        "handled": True,
        "operation_id": operation_id,
        "result": result,
        "message": user_message_for_result(result),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or handle video-review approval menus for Hermes gateway channels")
    parser.add_argument("--operations-dir", type=Path, default=DEFAULT_OPERATIONS_DIR)
    sub = parser.add_subparsers(dest="command", required=True)

    prompt_p = sub.add_parser("prompt")
    prompt_p.add_argument("operation_id")
    prompt_p.add_argument("--platform", choices=["telegram", "weixin"], default="weixin")
    prompt_p.add_argument("--json", action="store_true")
    prompt_p.add_argument("--send-to", help="Optional Hermes messaging target, e.g. telegram or weixin")

    action_p = sub.add_parser("action")
    action_p.add_argument("operation_id")
    action_p.add_argument("choice", help="1/trash, 2/delete, 3/cancel")

    resolve_p = sub.add_parser("resolve-reply")
    resolve_p.add_argument("--platform", required=True, choices=["telegram", "weixin"])
    resolve_p.add_argument("--chat-id", required=True)
    resolve_p.add_argument("--thread-id")
    resolve_p.add_argument("--text", required=True)
    resolve_p.add_argument("--reply-to-message-id")

    args = parser.parse_args()
    OperationExecutor, _ = load_executor_module()
    executor = OperationExecutor(args.operations_dir)

    if args.command == "prompt":
        plan = executor.build_plan(args.operation_id)
        store = ApprovalStore(args.operations_dir / ".hermes-approvals.json")
        store.upsert_operation(args.operation_id)
        if args.platform == "telegram":
            payload = telegram_menu_payload(plan)
            output = json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["text"]
        else:
            output = weixin_prompt(plan)
        if args.send_to:
            send_text(args.send_to, output)
        else:
            print(output)
    elif args.command == "action":
        print(json.dumps(run_action(args.operations_dir, args.operation_id, args.choice), ensure_ascii=False, indent=2))
    elif args.command == "resolve-reply":
        print(json.dumps(
            resolve_reply(
                args.operations_dir,
                platform=args.platform,
                chat_id=args.chat_id,
                thread_id=args.thread_id,
                text=args.text,
                reply_to_message_id=args.reply_to_message_id,
            ),
            ensure_ascii=False,
            indent=2,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
