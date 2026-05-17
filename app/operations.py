from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings


def generate_operation_id() -> str:
    now = datetime.now(timezone.utc)
    suffix = secrets.token_hex(4)
    return f"op_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"


def derive_source_root(
    container_path: Path,
    download_root: Path,
    library_root: Path,
) -> tuple[str, str]:
    """Return (source_root_key, relative_path) for a container path.

    Raises ValueError if the path is not under either allowed root.
    """
    resolved = container_path.resolve(strict=False)

    for key, root in [("download", download_root), ("library", library_root)]:
        root_resolved = root.resolve(strict=False)
        try:
            rel = resolved.relative_to(root_resolved)
            return key, str(rel)
        except ValueError:
            continue

    raise ValueError(
        f"path {container_path} is not under download_root ({download_root}) "
        f"or library_root ({library_root})"
    )


def build_operation_request(
    job: dict[str, Any],
    items: list[dict[str, Any]],
    settings: Settings,
    current_dir: str = "",
) -> dict[str, Any]:
    """Build a move_to_trash operation request dict per schema v1."""
    operation_id = generate_operation_id()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    download_root = settings.download_root
    library_root = settings.library_root

    op_items = []
    total_size = 0
    skipped = []

    for item in items:
        container_path = Path(item["original_path"])
        try:
            source_root, relative_path = derive_source_root(
                container_path, download_root, library_root
            )
        except ValueError:
            skipped.append(item["item_id"])
            continue

        size = item.get("file_size", 0)
        total_size += size

        op_items.append({
            "item_id": item["item_id"],
            "file_name": item["file_name"],
            "source_root": source_root,
            "container_path": str(container_path),
            "relative_path": relative_path,
            "size_bytes": size,
            "requested_action": "move_to_trash",
        })

    request = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation_type": "move_to_trash",
        "status": "pending_approval",
        "created_at": now,
        "created_by": "video-review",
        "job": {
            "job_id": job["job_id"],
            "name": job["name"],
            "scan_path": job["scan_path"],
            "current_dir": current_dir,
        },
        "summary": {
            "item_count": len(op_items),
            "total_size_bytes": total_size,
        },
        "path_mappings": {
            "download": {
                "container_root": str(download_root),
                "hermes_root": "/nas/download",
            },
            "library": {
                "container_root": str(library_root),
                "hermes_root": "/nas/media",
            },
        },
        "items": op_items,
        "approval": {
            "required": True,
            "executor": "hermes",
        },
    }

    return request, skipped


def write_operation_request(request: dict[str, Any], pending_dir: Path) -> Path:
    """Atomically write an operation request JSON to the pending directory."""
    pending_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{request['operation_id']}.json"
    target = pending_dir / filename
    tmp = pending_dir / f"{filename}.tmp"

    tmp.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(target))
    return target
