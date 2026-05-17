# Hermes Operation Executor

`video-review` 只负责生成 `/app/data/operations/pending/*.json`，不直接改动媒体文件。Hermes 侧执行器负责读取这些 pending operation，在用户确认后把文件移动到项目回收站。

## 路径

- pending 请求：`/nas/docker/video-review/data/operations/pending/*.json`
- 完成记录：`/nas/docker/video-review/data/operations/completed/*.json`
- 失败记录：`/nas/docker/video-review/data/operations/failed/*.json`
- 拒绝记录：`/nas/docker/video-review/data/operations/rejected/*.json`
- 审计副本：`/nas/docker/video-review/data/operations/audit/*.json`
- 回收站：`<hermes_root>/.video-review-trash/<operation_id>/<relative_path>`
  - download 示例：`/nas/download/.video-review-trash/<operation_id>/...`
  - media 示例：`/nas/media/.video-review-trash/<operation_id>/...`

## 使用方式

推荐交互式菜单：

```bash
/nas/docker/video-review/scripts/hermes-approve-operation.sh
```

也可以直接用 Python 脚本：

```bash
python3 /nas/docker/video-review/scripts/hermes_operation_executor.py list
python3 /nas/docker/video-review/scripts/hermes_operation_executor.py plan <operation_id>
python3 /nas/docker/video-review/scripts/hermes_operation_executor.py execute <operation_id> --confirm <operation_id>
python3 /nas/docker/video-review/scripts/hermes_operation_executor.py reject <operation_id> --reason "用户拒绝"
```

`execute` 需要确认码等于 operation id，或者 `MOVE_TO_TRASH <operation_id>`。

## 安全规则

- 只支持 `schema_version: 1`。
- 只支持 `operation_type: move_to_trash`。
- 只处理 `status: pending_approval`。
- 必须满足 `approval.required: true` 和 `approval.executor: hermes`。
- 不使用 `container_path` 执行文件操作。
- 真实源路径只由 `path_mappings[source_root].hermes_root / relative_path` 解析。
- 使用 `Path.resolve(strict=True)` 和 `relative_to()` 阻止 sibling-prefix 和 symlink escape。
- 第一阶段只移动到 `.video-review-trash`，不永久删除。
- 如果执行前校验失败，请求会进入 `failed/`，源文件不会移动。

## 当前 P0 范围

已实现：

- 列出 pending operation。
- 展示 move plan。
- 拒绝 operation。
- 执行 move-to-trash。
- 写 completed/failed/rejected/audit JSON。
- 自动创建 operations 子目录。

暂未实现：

- 自动定时扫描并主动发 Telegram/微信消息。
- 数据库 item 状态回写。
- restore/purge 工作流。

这些可以在 P0 基础可用后继续扩展。
