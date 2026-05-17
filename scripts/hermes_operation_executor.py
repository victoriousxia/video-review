#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIRM_PREFIX = "MOVE_TO_TRASH"
PERMANENT_CONFIRM_PREFIX = "DELETE_PERMANENTLY"
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ALLOWED_SOURCE_ROOTS = {"download", "library"}


class ExecutorError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExecutorError(f"invalid json: {path}: {exc}") from exc


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def validate_operation_id(operation_id: str) -> str:
    if not operation_id or not OPERATION_ID_RE.fullmatch(operation_id):
        raise ExecutorError(f"unsafe operation_id: {operation_id!r}")
    return operation_id


def validate_operation(op: dict[str, Any]) -> None:
    if op.get("schema_version") != 1:
        raise ExecutorError("unsupported schema_version")
    if op.get("operation_type") != "move_to_trash":
        raise ExecutorError("unsupported operation_type")
    if op.get("status") != "pending_approval":
        raise ExecutorError("operation is not pending_approval")
    approval = op.get("approval") or {}
    if approval.get("required") is not True or approval.get("executor") != "hermes":
        raise ExecutorError("operation does not require Hermes approval")
    validate_operation_id(str(op.get("operation_id", "")))
    items = op.get("items")
    if not isinstance(items, list) or not items:
        raise ExecutorError("operation contains no items")
    for item in items:
        source_root = item.get("source_root")
        if source_root not in ALLOWED_SOURCE_ROOTS:
            raise ExecutorError(f"unsupported source_root: {source_root}")
        if item.get("requested_action") != op["operation_type"]:
            raise ExecutorError("item requested_action does not match operation_type")


def resolve_item_source(op: dict[str, Any], item: dict[str, Any]) -> Path:
    source_root = item.get("source_root")
    mappings = op.get("path_mappings") or {}
    mapping = mappings.get(source_root) if isinstance(mappings, dict) else None
    if not isinstance(mapping, dict):
        raise ExecutorError(f"missing path mapping for source_root: {source_root}")

    hermes_root_raw = mapping.get("hermes_root")
    relative_raw = item.get("relative_path")
    if not hermes_root_raw or not relative_raw:
        raise ExecutorError("item missing hermes_root or relative_path")

    relative = Path(str(relative_raw))
    if relative.is_absolute():
        raise ExecutorError(f"unsafe relative_path: {relative_raw}")

    root = Path(str(hermes_root_raw)).resolve(strict=True)
    raw_candidate = root / relative
    try:
        candidate = raw_candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ExecutorError(f"source path does not exist: {raw_candidate}") from exc
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ExecutorError(f"source path is outside allowed root: {candidate}") from exc
    return candidate


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(1, 1000):
        candidate = parent / f"{stem}.{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise ExecutorError(f"cannot find non-conflicting trash path for {path}")


class OperationExecutor:
    def __init__(self, operations_dir: Path | str):
        self.operations_dir = Path(operations_dir)
        self.pending_dir = self.operations_dir / "pending"
        self.processing_dir = self.operations_dir / "processing"
        self.completed_dir = self.operations_dir / "completed"
        self.failed_dir = self.operations_dir / "failed"
        self.rejected_dir = self.operations_dir / "rejected"
        self.audit_dir = self.operations_dir / "audit"
        for directory in (
            self.pending_dir,
            self.processing_dir,
            self.completed_dir,
            self.failed_dir,
            self.rejected_dir,
            self.audit_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def pending_path(self, operation_id: str) -> Path:
        operation_id = validate_operation_id(operation_id)
        return self.pending_dir / f"{operation_id}.json"

    def list_pending(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in sorted(self.pending_dir.glob("*.json")):
            op = load_json(path)
            summaries.append(
                {
                    "operation_id": op.get("operation_id", path.stem),
                    "job_name": (op.get("job") or {}).get("name", ""),
                    "operation_type": op.get("operation_type", ""),
                    "item_count": (op.get("summary") or {}).get("item_count", len(op.get("items") or [])),
                    "total_size_bytes": (op.get("summary") or {}).get("total_size_bytes", 0),
                    "path": str(path),
                }
            )
        return summaries

    def load_pending(self, operation_id: str) -> dict[str, Any]:
        path = self.pending_path(operation_id)
        if not path.exists():
            raise ExecutorError(f"pending operation not found: {operation_id}")
        op = load_json(path)
        if op.get("operation_id") != operation_id:
            raise ExecutorError("operation_id mismatch between file name and JSON")
        validate_operation(op)
        return op

    def build_plan(self, operation_id: str) -> dict[str, Any]:
        op = self.load_pending(operation_id)
        planned_items = []
        for item in op["items"]:
            source = resolve_item_source(op, item)
            source_root = item["source_root"]
            root = Path(op["path_mappings"][source_root]["hermes_root"]).resolve(strict=True)
            relative = source.relative_to(root)
            trash = unique_destination(root / ".video-review-trash" / op["operation_id"] / relative)
            planned_items.append(
                {
                    "item_id": item.get("item_id"),
                    "file_name": item.get("file_name"),
                    "source_path": str(source),
                    "trash_path": str(trash),
                    "size_bytes": item.get("size_bytes", 0),
                }
            )
        return {
            "operation_id": op["operation_id"],
            "operation_type": op["operation_type"],
            "status": op["status"],
            "job": op.get("job", {}),
            "summary": op.get("summary", {}),
            "items": planned_items,
            "confirm": op["operation_id"],
        }

    def reject(self, operation_id: str, reason: str = "rejected by user") -> dict[str, Any]:
        op = self.load_pending(operation_id)
        op["status"] = "rejected"
        op["rejected_at"] = utc_now()
        op["rejection_reason"] = reason
        target = self.rejected_dir / f"{operation_id}.json"
        atomic_write_json(target, op)
        self.pending_path(operation_id).unlink()
        return op

    def execute(self, operation_id: str, confirm: str) -> dict[str, Any]:
        operation_id = validate_operation_id(operation_id)
        if confirm != operation_id and confirm != f"{CONFIRM_PREFIX} {operation_id}":
            raise ExecutorError("confirmation does not match operation_id")

        source_path = self.pending_path(operation_id)
        if not source_path.exists():
            raise ExecutorError(f"pending operation not found: {operation_id}")
        processing_path = self.processing_dir / source_path.name
        os.replace(source_path, processing_path)
        op = load_json(processing_path)
        executed_items: list[dict[str, Any]] = []
        try:
            if op.get("operation_id") != operation_id:
                raise ExecutorError("operation_id mismatch between file name and JSON")
            validate_operation(op)
            plan_items = []
            for item in op["items"]:
                source = resolve_item_source(op, item)
                source_root = item["source_root"]
                root = Path(op["path_mappings"][source_root]["hermes_root"]).resolve(strict=True)
                relative = source.relative_to(root)
                trash = unique_destination(root / ".video-review-trash" / operation_id / relative)
                plan_items.append((item, source, trash))

            for item, source, trash in plan_items:
                trash.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(trash))
                executed_items.append(
                    {
                        "item_id": item.get("item_id"),
                        "file_name": item.get("file_name"),
                        "source_path": str(source),
                        "trash_path": str(trash),
                        "size_bytes": item.get("size_bytes", 0),
                        "status": "moved_to_trash",
                    }
                )

            op["status"] = "completed"
            op["executed_at"] = utc_now()
            op["execution"] = {
                "executor": "hermes",
                "action": "move_to_trash",
                "items": executed_items,
                "errors": [],
            }
            target = self.completed_dir / processing_path.name
            atomic_write_json(target, op)
            audit = self.audit_dir / f"{operation_id}.json"
            atomic_write_json(audit, op)
            processing_path.unlink(missing_ok=True)
            return {"status": "completed", "operation_id": operation_id, "items": executed_items, "operation_file": str(target)}
        except Exception as exc:
            message = str(exc)
            if not isinstance(exc, ExecutorError):
                message = f"{type(exc).__name__}: {message}"
            op["status"] = "failed"
            op["failed_at"] = utc_now()
            op["execution"] = {
                "executor": "hermes",
                "action": "move_to_trash",
                "items": executed_items,
                "errors": [message],
            }
            failed = self.failed_dir / processing_path.name
            atomic_write_json(failed, op)
            processing_path.unlink(missing_ok=True)
            raise ExecutorError(message) from exc

    def delete_permanently(self, operation_id: str, confirm: str) -> dict[str, Any]:
        operation_id = validate_operation_id(operation_id)
        if confirm != f"{PERMANENT_CONFIRM_PREFIX} {operation_id}":
            raise ExecutorError("permanent deletion confirmation does not match")

        source_path = self.pending_path(operation_id)
        if not source_path.exists():
            raise ExecutorError(f"pending operation not found: {operation_id}")
        processing_path = self.processing_dir / source_path.name
        os.replace(source_path, processing_path)
        op = load_json(processing_path)
        executed_items: list[dict[str, Any]] = []
        try:
            if op.get("operation_id") != operation_id:
                raise ExecutorError("operation_id mismatch between file name and JSON")
            validate_operation(op)
            plan_items = []
            for item in op["items"]:
                source = resolve_item_source(op, item)
                plan_items.append((item, source))

            for item, source in plan_items:
                source.unlink()
                executed_items.append(
                    {
                        "item_id": item.get("item_id"),
                        "file_name": item.get("file_name"),
                        "source_path": str(source),
                        "size_bytes": item.get("size_bytes", 0),
                        "status": "deleted_permanently",
                    }
                )

            op["status"] = "completed"
            op["executed_at"] = utc_now()
            op["execution"] = {
                "executor": "hermes",
                "action": "delete_permanently",
                "items": executed_items,
                "errors": [],
            }
            target = self.completed_dir / processing_path.name
            atomic_write_json(target, op)
            audit = self.audit_dir / f"{operation_id}.json"
            atomic_write_json(audit, op)
            processing_path.unlink(missing_ok=True)
            return {
                "status": "completed",
                "operation_id": operation_id,
                "action": "delete_permanently",
                "items": executed_items,
                "operation_file": str(target),
            }
        except Exception as exc:
            message = str(exc)
            if not isinstance(exc, ExecutorError):
                message = f"{type(exc).__name__}: {message}"
            op["status"] = "failed"
            op["failed_at"] = utc_now()
            op["execution"] = {
                "executor": "hermes",
                "action": "delete_permanently",
                "items": executed_items,
                "errors": [message],
            }
            failed = self.failed_dir / processing_path.name
            atomic_write_json(failed, op)
            processing_path.unlink(missing_ok=True)
            raise ExecutorError(message) from exc



def format_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"操作: {plan['operation_id']}",
        f"任务: {(plan.get('job') or {}).get('name', '')}",
        f"类型: {plan['operation_type']}",
        f"文件数: {len(plan['items'])}",
        f"总大小: {(plan.get('summary') or {}).get('total_size_bytes', 0)} bytes",
        "",
        "将移动到 .video-review-trash，不会永久删除。",
    ]
    for item in plan["items"][:10]:
        lines.append(f"- {item['file_name']}")
        lines.append(f"  from: {item['source_path']}")
        lines.append(f"  to:   {item['trash_path']}")
    if len(plan["items"]) > 10:
        lines.append(f"... 还有 {len(plan['items']) - 10} 个文件")
    lines.append("")
    lines.append(f"执行确认码: {plan['confirm']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes executor for video-review pending operation JSON files")
    parser.add_argument("--operations-dir", default="/nas/docker/video-review/data/operations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    plan_p = sub.add_parser("plan")
    plan_p.add_argument("operation_id")
    exec_p = sub.add_parser("execute")
    exec_p.add_argument("operation_id")
    exec_p.add_argument("--confirm", required=True)
    delete_p = sub.add_parser("delete-permanently")
    delete_p.add_argument("operation_id")
    delete_p.add_argument("--confirm", required=True)
    reject_p = sub.add_parser("reject")
    reject_p.add_argument("operation_id")
    reject_p.add_argument("--reason", default="rejected by user")
    args = parser.parse_args()

    executor = OperationExecutor(args.operations_dir)
    if args.command == "list":
        print(json.dumps(executor.list_pending(), indent=2, ensure_ascii=False))
    elif args.command == "plan":
        print(format_plan(executor.build_plan(args.operation_id)))
    elif args.command == "execute":
        print(json.dumps(executor.execute(args.operation_id, args.confirm), indent=2, ensure_ascii=False))
    elif args.command == "delete-permanently":
        print(json.dumps(executor.delete_permanently(args.operation_id, args.confirm), indent=2, ensure_ascii=False))
    elif args.command == "reject":
        print(json.dumps(executor.reject(args.operation_id, args.reason), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
