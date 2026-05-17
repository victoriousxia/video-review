# video-review Trash Retention Policy

## 当前策略

默认不自动永久删除 `.video-review-trash` 里的文件。

原因：

- `扔垃圾桶` 是第一阶段安全删除，目标是可恢复。
- NAS 媒体文件误删代价高。
- Docker 内删除未必进入 NAS 系统回收站，因此必须由本项目自己控制保留和清理。

## 推荐策略

- 默认保留：30 天。
- 30 天后不自动清理；先生成 purge plan。
- purge plan 展示：operation id、文件数、总大小、最早/最新移动时间、文件路径样例。
- 用户确认后才永久删除。

## 当前状态

已实现：

- `move_to_trash`：移动到 `<hermes_root>/.video-review-trash/<operation_id>/...`
- completed/audit JSON：记录每个文件的原路径和 trash 路径。
- `delete-permanently`：只针对 pending operation，且需要强确认。

暂未实现：

- trash purge plan。
- trash restore。
- 定期提醒“回收站占用空间”。

## 后续实现建议

新增脚本：`scripts/hermes_trash_maintenance.py`

功能：

1. `list`
   - 汇总 `/nas/download/.video-review-trash` 和 `/nas/media/.video-review-trash`。
2. `purge-plan --older-than-days 30`
   - 只生成计划，不删除。
3. `purge --older-than-days 30 --confirm PURGE_VIDEO_REVIEW_TRASH`
   - 强确认后永久删除。
4. `restore <operation_id>`
   - 根据 completed/audit JSON 把文件从 trash 移回原路径。
   - 原路径存在时拒绝覆盖。

安全要求：

- purge 只允许删除 `.video-review-trash/<operation_id>` 下的文件。
- 必须 `Path.resolve()` 后确认目标仍在 `.video-review-trash` 内。
- 默认不启用自动 purge cron。
