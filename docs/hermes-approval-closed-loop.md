# Hermes Approval Closed Loop

本文档记录 `video-review` 删除审批闭环。当前范围只覆盖 P0 删除审批，不处理 P1 镜像、P2 设置持久化、P3 版本同步。

## 总体流程

1. 用户在 `video-review` Web UI 中把条目标记为待删除。
2. 用户点击删除/提交后，Web app 只写入 pending operation：
   `/app/data/operations/pending/<operation_id>.json`。
3. Web app 立即触发 notify hook：
   `scripts/hermes_pending_operation_notify.py <operation_id>`。
4. notify script 生成 Telegram/微信审批文案，记录审批 state，并发送到 Hermes 已连接渠道。
5. 用户在 Telegram/微信回复 `1`、`2`、`3`，或带操作码回复，例如 `1 VR-ABCD`。
6. Hermes gateway 消息路由接入后，应在普通 LLM dispatch 前调用：
   `scripts/hermes_operation_approval.py resolve-reply ...`。
7. 只有 `resolve-reply` 匹配到 active approval 后，Hermes 才执行真实文件操作。

## 安全边界

- `video-review` Web app 不得直接删除、移动、重命名真实媒体文件。
- Web app 不得调用 `Path.unlink()`、`os.remove()`、`rm` 或 `shutil.move()` 处理真实媒体。
- 默认删除动作是 `move_to_trash`，目标为：
  `<hermes_root>/.video-review-trash/<operation_id>/<relative_path>`。
- 永久删除必须输入二次确认文本：
  `DELETE_PERMANENTLY <operation_id>`。
- 执行真实路径时不得信任 operation JSON 中的 `container_path`。
- 真实源路径必须由：
  `path_mappings[source_root].hermes_root + relative_path`
  解析，并经过 `resolve(strict=True)`、`relative_to()` 等校验。
- 不修改 NAS 全局 Docker daemon DNS。

## 即时 notify hook

`app.main.delete_marked_files()` 在 `write_operation_request(...)` 成功后调用：

```python
notify_hermes_pending_operation(request["operation_id"])
```

hook 行为：

- 由配置 `VIDEO_REVIEW_HERMES_NOTIFY_ENABLED` 控制，默认开启。
- 脚本路径由 `VIDEO_REVIEW_HERMES_NOTIFY_SCRIPT` 控制，默认：
  `/nas/docker/video-review/scripts/hermes_pending_operation_notify.py`。
- 使用 `subprocess.Popen(..., start_new_session=True)` 异步触发。
- hook 是 best-effort：脚本不存在或启动失败时不影响 Web 请求；pending operation JSON 仍是 source of truth。

## Approval state 持久化

审批状态文件：

```text
/nas/docker/video-review/data/operations/.hermes-approvals.json
```

状态由 `scripts/hermes_operation_state.py` 管理，记录：

- `operation_id`
- 短操作码，如 `VR-D21E`
- 状态：`awaiting_choice`、`awaiting_delete_confirmation`、`resolved`
- 过期时间
- Telegram/微信通知绑定：`chat_id`、`thread_id`、`message_id`、`session_key`
- notify fingerprint，防止重复发送刷屏

持久化的目的：Hermes gateway 或容器重启后，仍能把用户回复绑定到正确 operation。

## Telegram / 微信回复绑定规则

`resolve-reply` 的匹配规则：

1. `DELETE_PERMANENTLY <operation_id>` 精确匹配永久删除二次确认。
2. `1 VR-XXXX`、`2 VR-XXXX`、`3 VR-XXXX` 使用操作码精确匹配。
3. 如果是 Telegram reply，并且 `reply_to_message_id` 匹配某条审批通知，则绑定对应 operation。
4. 同一 platform + chat/thread 中只有一个 active approval 时，允许裸回复 `1`、`2`、`3`。
5. 同一 platform + chat/thread 中有多个 active approval 时，裸回复 `1`、`2`、`3` 返回 ambiguity，不执行文件操作，并提示用户带操作码回复。
6. 无匹配时返回 `{"handled": false}`，gateway 应继续普通 Hermes/LLM 流程。

## 用户选项

- `1`：扔垃圾桶。
  - 执行 `move_to_trash`。
  - 文件移动到 `.video-review-trash/<operation_id>/`。
  - 可作为默认安全动作。
- `2`：申请永久删除。
  - 第一次选择 `2` 不删除文件。
  - 返回二次确认提示。
  - 只有用户回复 `DELETE_PERMANENTLY <operation_id>` 后才永久删除。
- `3`：取消。
  - operation 移入 `rejected/`。
  - 不移动、不删除媒体文件。

## Watchdog 只是兜底

`scripts/hermes_pending_operation_watchdog.py` 现在只扫描 pending operation 并调用 `hermes_pending_operation_notify.py`。

它的定位是兜底：

- 正常路径依赖 Web app 点击删除后的即时 notify hook。
- watchdog 用于补发 hook 失败、服务重启期间遗漏、或手工放入 pending operation 的请求。
- notify script 根据 fingerprint 和 approval state 保证幂等，避免重复刷屏；需要重发时可使用 `--force`。

## 当前尚未接入 Hermes gateway 消息路由

本仓库已提供 state、notify、approval resolver 和测试，但 Hermes gateway 还没有在消息入口中调用它们。

下一步交给 Claude Code：

- 在 `/opt/hermes/gateway/run.py` 中，在普通 LLM dispatch 前拦截 Telegram/微信文本消息。
- 对 `1`、`2`、`3`、`1 VR-XXXX`、`2 VR-XXXX`、`3 VR-XXXX`、`DELETE_PERMANENTLY <operation_id>` 调用：
  `python3 /nas/docker/video-review/scripts/hermes_operation_approval.py resolve-reply ...`
- 如果返回 `handled: true`，把返回的 `message` 发回用户，并跳过 LLM。
- 如果返回 `handled: false`，继续原 Hermes 消息流程。
- Telegram inline callback `vr|...` 可作为后续增强；当前测试重点是文本回复闭环。

## 验证命令

```bash
cd /nas/docker/video-review
uv run python -m pytest tests/test_hermes_operation_state.py tests/test_hermes_operation_approval.py tests/test_hermes_pending_operation_notify.py tests/test_hermes_operation_executor.py tests/test_operations.py -q
python3 -m py_compile app/main.py app/config.py scripts/hermes_operation_state.py scripts/hermes_operation_approval.py scripts/hermes_pending_operation_notify.py scripts/hermes_pending_operation_watchdog.py
```
