# Claude Code Instructions for video-review

## Project context

`video-review` is a NAS video review service. Its safety boundary is strict:

- The web app reviews media and records decisions.
- The web app must not directly delete, move, or rename real NAS media files.
- Real file operations are executed by Hermes only after explicit user approval through Telegram/WeChat.
- NAS media mounts should stay read-only in the normal `video-review` container.

Before implementing file-operation features, read:

- `docs/file-operation-protocol.md`
- `docs/safety-rules.md`
- `docs/hermes-integration.md`

## P0 architecture: Hermes-approved file operations

The P0 delete workflow is not direct deletion.

Expected flow:

1. User marks items as `delete_later` in the web UI.
2. User clicks the delete/submit button in `video-review`.
3. `video-review` writes a JSON operation request under:
   - container: `/app/data/operations/pending/<operation_id>.json`
   - Hermes/NAS repo path: `/nas/docker/video-review/data/operations/pending/<operation_id>.json`
4. `video-review` returns `pending_approval` and does not mutate media files.
5. Hermes reads the operation request, sends Telegram/WeChat approval to the user, and only after approval executes the file operation.
6. First-stage delete means `move_to_trash`, not permanent deletion.

## Non-negotiable constraints

- Do not call `Path.unlink()`, `os.remove()`, `rm`, or permanent delete from the web app for media files.
- Do not call `shutil.move()` or rename media files from the web app in the normal review service.
- Do not change media mounts from `:ro` to `:rw` for the normal web app.
- Do not modify NAS global Docker daemon DNS or other host-wide Docker settings.
- Do not change the operation JSON contract fields without updating `schema_version` and `docs/file-operation-protocol.md`.

## Operation JSON contract

The operation JSON is an internal protocol between `video-review` and Hermes. It is versioned with `schema_version`.

For schema version 1, these fields are required and should be treated as stable:

- `schema_version`
- `operation_id`
- `operation_type`
- `status`
- `created_at`
- `created_by`
- `job.job_id`
- `job.name`
- `job.scan_path`
- `job.current_dir`
- `summary.item_count`
- `summary.total_size_bytes`
- `path_mappings.download.container_root`
- `path_mappings.download.hermes_root`
- `path_mappings.library.container_root`
- `path_mappings.library.hermes_root`
- `items[].item_id`
- `items[].file_name`
- `items[].source_root`
- `items[].container_path`
- `items[].relative_path`
- `items[].size_bytes`
- `items[].requested_action`
- `approval.required`
- `approval.executor`

Adding fields is allowed. Removing or renaming contract fields is not allowed without a schema version bump.

## Implementation guidance

Prefer a dedicated module such as `app/operations.py` for:

- building operation request dictionaries
- validating paths and allowed roots
- deriving `source_root` and `relative_path`
- atomically writing JSON files into `/app/data/operations/pending`

Use atomic writes:

1. Write `<operation_id>.json.tmp`.
2. Rename to `<operation_id>.json`.

Tests should lock the protocol by asserting required fields exist.

## Current priority

P0: replace direct media deletion with Hermes-approved operation request creation.
