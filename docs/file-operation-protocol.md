# File Operation Protocol v1

This document defines the JSON contract between `video-review` and Hermes for media file operations such as delete, move, and rename.

## Purpose

`video-review` must not directly delete, move, or rename NAS media files from the web app.

Instead, `video-review` records an operation request under `/app/data/operations/pending/`. Hermes reads the request, asks the user for approval via Telegram/WeChat, and executes the operation only after approval.

For P0, the only supported operation type is:

- `move_to_trash`

This represents first-stage deletion by moving media into a project-managed trash location. It is not permanent deletion.

## Directory layout

Inside the container:

```text
/app/data/operations/
  pending/
  processing/
  approved/
  completed/
  failed/
  rejected/
```

From Hermes on the NAS:

```text
/nas/docker/video-review/data/operations/
  pending/
  processing/
  approved/
  completed/
  failed/
  rejected/
```

`video-review` only writes to `pending/` in the P0 implementation.

## File naming

Each operation request is one JSON file:

```text
/app/data/operations/pending/<operation_id>.json
```

Recommended operation id format:

```text
op_YYYYMMDD_HHMMSS_<random_suffix>
```

Example:

```text
op_20260517_153012_abcd1234.json
```

Writes must be atomic:

1. Write `<operation_id>.json.tmp`.
2. Rename to `<operation_id>.json`.

This prevents Hermes from reading a partially written file.

## Schema version

Every request must include:

```json
"schema_version": 1
```

Schema version 1 fields are stable. Additional fields may be added, but existing contract fields must not be removed or renamed without bumping `schema_version`.

## Required JSON shape

```json
{
  "schema_version": 1,
  "operation_id": "op_20260517_153012_abcd1234",
  "operation_type": "move_to_trash",
  "status": "pending_approval",
  "created_at": "2026-05-17T15:30:12+00:00",
  "created_by": "video-review",
  "job": {
    "job_id": "36f306321033401298f8dd4994be3fb9",
    "name": "Mantou cleanup",
    "scan_path": "/media/download/some/folder",
    "current_dir": ""
  },
  "summary": {
    "item_count": 1,
    "total_size_bytes": 123456789
  },
  "path_mappings": {
    "download": {
      "container_root": "/media/download",
      "hermes_root": "/nas/download"
    },
    "library": {
      "container_root": "/media/library",
      "hermes_root": "/nas/media"
    }
  },
  "items": [
    {
      "item_id": "item123",
      "file_name": "example.mkv",
      "source_root": "download",
      "container_path": "/media/download/some/folder/example.mkv",
      "relative_path": "some/folder/example.mkv",
      "size_bytes": 123456789,
      "requested_action": "move_to_trash"
    }
  ],
  "approval": {
    "required": true,
    "executor": "hermes"
  }
}
```

## Required fields

Top-level:

- `schema_version`: integer. Must be `1` for this contract.
- `operation_id`: string. Unique id for this request.
- `operation_type`: string. P0 supports `move_to_trash` only.
- `status`: string. Must be `pending_approval` when created by `video-review`.
- `created_at`: ISO-8601 timestamp with timezone.
- `created_by`: string. Must be `video-review`.
- `job`: object. Source review job metadata.
- `summary`: object. Aggregate item count and size.
- `path_mappings`: object. Container-to-Hermes path mapping.
- `items`: array. Files requested for operation.
- `approval`: object. Approval requirement metadata.

`job`:

- `job_id`: review job id.
- `name`: review job name.
- `scan_path`: job scan path as seen inside the container.
- `current_dir`: current relative directory filter, or empty string for root.

`summary`:

- `item_count`: number of items in the request.
- `total_size_bytes`: sum of item sizes.

`path_mappings`:

- `download.container_root`: `/media/download`
- `download.hermes_root`: `/nas/download`
- `library.container_root`: `/media/library`
- `library.hermes_root`: `/nas/media`

`items[]`:

- `item_id`: review item id.
- `file_name`: original file name.
- `source_root`: either `download` or `library`.
- `container_path`: original path as stored by `video-review`, under `/media/download` or `/media/library`.
- `relative_path`: path relative to the selected source root.
- `size_bytes`: file size recorded by scan.
- `requested_action`: must match `operation_type` for P0.

`approval`:

- `required`: must be `true`.
- `executor`: must be `hermes`.

## Path mapping rules

Hermes must not execute directly from `container_path`.

Hermes should resolve real source paths using:

```text
real_source = path_mappings[items[].source_root].hermes_root / items[].relative_path
```

Examples:

- `source_root = download`
- `relative_path = some/folder/example.mkv`
- `hermes_root = /nas/download`
- real source path: `/nas/download/some/folder/example.mkv`

This keeps the protocol independent from container-only paths.

## Path safety rules for video-review

When building operation requests, `video-review` must:

- include only items whose paths are under configured media roots
- derive `relative_path` using resolved roots, not raw string prefix replacement
- reject or skip paths outside `/media/download` and `/media/library`
- reject or skip symlink escapes
- not mutate source media files

Recommended Python approach:

```python
candidate = Path(container_path).resolve(strict=False)
root = Path(container_root).resolve(strict=False)
relative_path = candidate.relative_to(root)
```

Use `Path.relative_to()` or equivalent safety checks instead of `str(path).startswith(root)`.

## P0 API behavior

Existing endpoint may be kept for UI compatibility:

```text
POST /api/v1/jobs/{job_id}/delete-files
```

But its behavior must change:

- old behavior: directly delete files with `unlink()`
- new behavior: create a `move_to_trash` operation request and return `pending_approval`

Suggested response:

```json
{
  "operation_id": "op_20260517_153012_abcd1234",
  "status": "pending_approval",
  "operation_type": "move_to_trash",
  "item_count": 1,
  "operation_file": "/app/data/operations/pending/op_20260517_153012_abcd1234.json",
  "message": "已提交删除请求，等待 Hermes 审批执行"
}
```

The endpoint must not remove review items from SQLite. The endpoint must not delete, move, or rename source files.

## UI language

The UI should not say that files were deleted.

Use language such as:

- `提交删除请求（N）`
- `已提交删除请求，等待 Hermes 审批执行`
- `video-review 不会直接删除文件；Hermes 会在你确认后移动到回收站`

## Capability flags

`GET /api/v1/info` should truthfully report that `video-review` itself does not mutate media files.

Recommended additions:

```json
{
  "capabilities": {
    "media_mutation": false,
    "file_operation_requests": true,
    "hermes_approval_required": true,
    "trash_plan": true,
    "trash_execute": false
  },
  "safety": {
    "review_only": true,
    "moves_files": false,
    "deletes_files": false,
    "creates_operation_requests": true,
    "executor": "hermes",
    "approval_required": true
  }
}
```

## Test requirements

Tests must verify:

1. Creating a delete request does not delete or move the media file.
2. A JSON file appears under `operations/pending/`.
3. The JSON includes all required schema version 1 contract fields.
4. `operation_type` is `move_to_trash`.
5. `status` is `pending_approval`.
6. `approval.required` is `true`.
7. `approval.executor` is `hermes`.
8. `items[].source_root` is `download` or `library`.
9. `items[].relative_path` is relative to the correct root.
10. Outside-root and symlink-escape paths are rejected or skipped.
11. `/api/v1/info` capability and safety flags match the review-only architecture.

## Non-goals for P0

Do not implement these in `video-review` P0:

- permanent deletion
- direct web-app move/rename execution
- writable media mounts for the normal web app
- automatic execution without Hermes approval
- Telegram/WeChat messaging inside `video-review`
- Docker daemon or NAS host-wide network changes

Hermes-side execution will be implemented separately after this protocol is in place.
