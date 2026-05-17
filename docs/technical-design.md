# Video-Review 技术设计文档

版本：v0.3.2+（含删除审批闭环 + Gateway Interceptor）
更新日期：2026-05-18

## 1. 系统定位

video-review 是一个运行在 FnOS NAS 上的 Docker 化视频文件 Review 与清理工具。用户通过 Web UI 浏览、标记待删除文件，真实文件操作由 Hermes Agent 在 Telegram/微信获得用户确认后执行。

核心原则：**Web app 不直接操作真实媒体文件**。所有破坏性操作必须经过 Hermes 审批闭环。

## 2. 整体架构

```text
┌───────────────────────────────────────────────────────────┐
│  用户                                                                │
│  ├── 浏览器 (Lucky 反代) ──→ video-review Web UI          │
│  └── Telegram / 微信 ──→ Hermes Gateway                             │
└─────────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────┐    ┌──────────────────────────────────────┐
│  video-review 容器    │    │  Hermes Agent 容器                    │
│                      │    │                                      │
│  FastAPI + SQLite    │    │  gateway/run.py                      │
│  Web UI (Jinja2)     │    │         │◄───┤                                      │
│      pending/        │    │  scripts/ (NAS 挂载)                  │
│      completed/      │    │    ├─ hermes_gateway_interceptor.py  │
│      rejected/       │    │    ├─ hermes_operation_approval.py   │
│      .hermes-        │    │    ├─ hermes_operationg_operation_      │
│  notify hook ────────┼────┤    │   notify.py                     │
│                      │    │    └─ hermes_pending_operation_      │
└──────────────────────┘    │        watchdog.py                   │
                            └──────────────────────────────────────┘
```

## 3. 组件职责

### 3.1 video-review 容器

| 组件 | 职责 |
|------|------|
| FastAPI app | HTTP 服务、Web UI、API |
| SQLite | review_jobs、review_items、schema_meta |
| 扫描器 | 递归扫描视频文件，写入 review_items |
| 操作请求生成 | 用户点击删除后写入 pending operation JSON |
| Notify hook | 写入 pending 后异步触发通知脚本 |

容器路径映射：

- `/media/download` ← NAS `/vol1/1000/Download`（只读）
- `/media/library` ← NAS `/vol1/1000/Media`（读写）
- `/app/data` ← `./data`（应用数据）

### 3.2 Hermes Agent 容器

| 组件 | 职责 |
|------|------|
| Gateway interceptor | 在 LLM dispatch 前拦截审批回复 |
| Operation state | 管理审批状态持久化 (.hermes-approvals.json) |
| Operation approval | 解析用户回复、匹配 operation、调用 executor |
| Operation executor | 执行真实文件操作（move_to_trash / delete_permanently） |
| Notify script | 生成审批文案、发送到 Telegram/微信 |
| Watchdog | 兜底扫描未通知的 pending operation |

NAS 挂载：

- `/nas/download` ← `/vol1/1000/Download`
- `/nas/media` ← `/vol1/1000/Media`
- `/nas/docker` ← `/vol2/1000/Docker`

## 4. 删除审批闭环流程

```text
用户在 Web UI 标记文件 → 点击"提交删除"
    │
    ▼
video-review 写入 pending/<operation_id>.json
    │
    ▼ (即时 notify hook)
hermes_pending_operation_notify.py
    │
    ├─ 生成 Telegram inline keyboard / 微信文本菜单
    ├─ 记录 approval state (awaiting_choice)
    └─ 通过 Hermes send_message 发送审批通知
    │
    ▼
用户在 Telegram/微信回复 1/2/3 或带操作码
    │
    ▼
Hermes gateway → _try_vr_intercept()
    │
    ├─ looks_like_approval_reply() 快速过滤
    ├─ 非审批消息 → handled=false → 继续 LLM 对话
    └─ 审批消息 → _resolve_via_import()
         │
         ├─ ApprovalStore.find_match() 匹配 operation
         ├─ run_action() 执行对应动作
         └─ 返回 handled=true + message
              │
              ▼
         Gateway 回复用户，跳过 LLM
```

### 4.1 用户选项

| 回复 | 动作 | 安全级别 |
|------|------|----------|
| `1` | move_to_trash | 安全，可恢复 |
| `2` | 请求永久删除（返回二次确认提示） | 需二次确认 |
| `3` | 取消（operation → rejected/） | 无操作 |
| `DELETE_PERMANENTLY <op_id>` | 永久删除 | 仅在 awaiting_delete_confirmation 状态下生效 |

### 4.2 安全约束

- `DELETE_PERMANENTLY` 必须在 operation 处于 `awaiting_delete_confirmation` 状态时才执行（不可跳过选 2 直接永久删除）
- 通知只发送到已注册的 platform home chl
- 未收到通知的 chat 无法触发审批
- 真实路径通过 `path_mappings[source_root].hermes_root + relative_path` 解析，不信任 container_path
- 路径经过 `resolve(strict=True)` + `relative_to()` 防止路径穿越

## 5. Gateway Interceptor 接入

位置：`/opt/hermes/gateway/run.py` → `_process_message_background()`

```text
消息到达
  │
  ├─ is_internal=True → 跳过
  ├─ platform 不是 telegram/weixin → 跳过
  └─ _try_vr_intercept(platform, chat_id, thread_id, text, reply_to_message_id)
       │
       ├─ handled=True → 发送 result["message"]，return（不进 LLM）
       └─ handled=False → 继续正常 Hermes 对话流程
```

interceptor 模块：`/nas/docker/video-review/scripts/hermes_gateway_interceptor.py`

- `looks_like_approval_reply(text)` — 正则快速过滤，O(1)
- `try_intercept(...)` — 完整匹配+执行，仅在 looks_like 通过后调用
- 支持 `use_subprocess=True离）和 `use_subprocess=False`（直接 import，默认）

## 6. 状态管理

### 6.1 Operation 生命周期

```text
pending/ ──→ completed/   (执行成功)
         └─→ rejected/    (用户取消)
```

### 6.2 Approval State 生命周期

```text
(upsert) → awaiting_choice
              │
              ├─ 选 1 → resolved (move_to_trash)
              ├─ 选 2 → awaiting_delete_confirmation
              │            └─ DELETE_PERMANENTLY → resolved (delete_permanently)
              └─ 选 3 → resolved (rejected)
```

持久化文件：`data/operations/.hermes-approvals.json`

### 6.3 通知匹配规则

优先级从高到低：

1. `DELETE_PERMANENTLY <op_id>` — 精确匹配 operation_id + 状态检查
2. `N VR-XXXX` — 操作码精确匹配
3. reply_to_message_id 匹配审批通知消息
4. 同 platform 只有 1 个 active approval → 裸回复 `1/2/3` 生效
5. 同 platform 多个 active → 返回 ambiguity 提示

channel 匹配：通知记录的 `chat_id` 为 platform 名称（如 `"telegram"`）时视为 home channel 通配符，匹配该 platform 上的任何 chat。

## 7. 目录结构

```text
video-review/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # SQLite 初始化
│   ├── scanner.py           # 视频文件扫描
│   ├── templates/           # Jinja2 模板
│   └── static/              # CSS/JS
├── scripts/
│   ├── hermes_gateway_interceptor.py      # Gateway 拦截入口
│   ├── hermes_gateway_integration_example.py  # 集成示例
│   ├── hermes_operation_state.py          # ApprovalStore 状态管理
│   ├── hermes_operation_approval.py       # 审批解析 + CLI
│   ├── hermes_operation_executor.py       # 文件操作执行器
│   ├── hermes_pending_operation_notify.py # 通知脚本
│   └── hermes_pending_operation_watchdog.py # 兜底 watchdog
├── tests/
│   ├── test_hermes_gateway_interceptor.py
│   ├── test_hermes_operation_approval.py
│   ├── test_hermes_operation_executor.py
│   ├── test_hermes_operation_state.py
│   ├── test_hermes_pending_operation_notify.py
│   ├── test_operations.py
│   ├── test_scanner.py
│   └── test_web_forms.py
├── data/
│   └── operations/
│       ├── pending/
│       ├── completed/
│       ├── rejected/
│       └── .hermes-approvals.json
├── docs/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.nas.yml
├── VERSION
└── CHANGELOG.md
```

## 8. 部署拓扑

```text
FnOS NAS
├── Docker
│   ├── video-review 容器 (host network, port 8765)
│   │   └── /app/data → /vol2/1000/Docker/video-review/data
│   └── hermes 容器 (host network)
│       ├── /nas/download → /vol1/1000/Download
│       ├── /nas/media → /vol1/1000/Media
│       └── /nas/docker → /vol2/1000/Docker
└── Lucky 反代
    └── HTTPS + 认证 → localhost:8765
```

## 9. 技术栈

- Python 3.11+
- FastAPI + Uvicorn
- Jinja2 模板
- SQLite（无 ORM，直接 SQL）
- pytest（测试）
- Docker + docker-compose
- Hermes Agent（gateway 集成）

## 10. 已知限制与后续计划

### 当前限制

- Telegram inline button callback 尚未处理（仅文本回复有效）
- 通知记录使用 platform 名称作为 chat_id（单用户场景足够）
- 无 ffprobe 元数据提取
- 无截图生成
- 无定时扫描

### 后续迭代方向

- P1：替换 Open WebUI 为独立前端
- P2：设置持久化
- P3：文档/测试同步
- 元数据提取 + 截图
- Telegram inline button 支持
- 多用户 chat 隔离
