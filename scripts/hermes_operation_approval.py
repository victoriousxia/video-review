#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OPERATIONS_DIR = Path("/nas/docker/video-review/data/operations")


def load_executor_module():
    sys.path.insert(0, str(SCRIPT_DIR.parent))
    from scripts.hermes_operation_executor import OperationExecutor, format_plan

    return OperationExecutor, format_plan


def summarize_plan(plan: dict[str, Any]) -> str:
    job_name = (plan.get("job") or {}).get("name", "")
    summary = plan.get("summary") or {}
    item_count = len(plan.get("items") or [])
    total_size = summary.get("total_size_bytes", 0)
    lines = [
        "video-review 删除审批",
        f"操作: {plan['operation_id']}",
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
        return {"status": "rejected", "operation_id": operation_id, "operation_file": str(executor.rejected_dir / f"{operation_id}.json"), "operation": op}
    raise SystemExit(f"unknown choice: {choice}")


def send_text(target: str, message: str) -> None:
    code = (
        "from hermes_tools import send_message\n"
        f"send_message(action='send', target={target!r}, message={message!r})\n"
    )
    subprocess.run(["python3", "-c", code], check=True)


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

    args = parser.parse_args()
    OperationExecutor, _ = load_executor_module()
    executor = OperationExecutor(args.operations_dir)

    if args.command == "prompt":
        plan = executor.build_plan(args.operation_id)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
