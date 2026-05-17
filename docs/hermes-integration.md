# Hermes Integration

video-review is not strongly coupled to Hermes.

## P0：Hermes 审批执行文件操作

video-review 不直接删除、移动或重命名真实媒体文件。Web UI 中的删除/整理操作只生成操作请求文件，真正执行由 Hermes 在用户确认后完成。

核心协议见：`docs/file-operation-protocol.md`。

P0 流程：

1. 用户在 Web UI 标记条目为待删除。
2. 用户点击提交删除请求。
3. video-review 写入 `/app/data/operations/pending/<operation_id>.json`。
4. Hermes 从 `/nas/docker/video-review/data/operations/pending/` 读取请求。
5. Hermes 通过 Telegram/微信请求用户确认。
6. 用户确认后，Hermes 执行移动到回收站等真实文件操作。

Hermes 侧执行器：

- 交互式菜单：`scripts/hermes-approve-operation.sh`
- 直接 CLI：`scripts/hermes_operation_executor.py`
- 使用说明：`docs/hermes-operation-executor.md`

约束：

- video-review 正常容器的媒体目录继续只读挂载。
- video-review 不调用 `unlink()`、`rm`、`shutil.move()` 处理真实媒体文件。
- 第一阶段“删除”表示 `move_to_trash`，不是永久删除。

## Recommended model

The Docker service exposes standard HTTP endpoints and later a CLI. Hermes acts as an orchestrator:

- user says: scan a folder for review
- Hermes calls video-review API
- video-review returns job id and URL
- Hermes sends the URL to the same message channel
- user reviews in browser
- user says: generate plan or execute
- Hermes calls dry-run API, summarizes, and asks for explicit confirmation
- Hermes calls execution API only after confirmation

## Why not strong coupling

Strong coupling would make the app hard to use from Mac, cron, shell, or other services. It would also mix messaging credentials with media-management code.

## Standard API surface planned

- `GET /healthz`
- `GET /api/v1/info`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/progress`
- `POST /api/v1/items/{item_id}/screenshots/regenerate`
- `POST /api/v1/items/{item_id}/decision`
- `POST /api/v1/jobs/{job_id}/plan`
- `POST /api/v1/jobs/{job_id}/execute` guarded by confirmation token in later versions

## Notifications

video-review should not send Telegram/WeChat messages itself in V1. It returns machine-readable status and links; Hermes delivers the notification through the active channel.
