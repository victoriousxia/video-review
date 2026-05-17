# 架构设计

video-review 设计成“通用 Docker 服务 + 可选 Hermes 编排”的结构。

核心原则：服务本身不依赖 Hermes 内部实现。Hermes 可以调用它，但它不应该只能被 Hermes 使用。

## 核心服务

video-review 核心服务包括：

- FastAPI HTTP 应用
- SQLite 数据库
- Web Review 页面
- 任务 API
- 后续的视频扫描器
- 后续的 ffprobe 元数据模块
- 后续的 ffmpeg 截图服务
- 后续的 Review 决策模块
- 后续的 dry-run 执行计划模块
- 后续的安全执行器

## Hermes 集成边界

Hermes 不嵌入 video-review 服务内部。

Hermes 通过稳定接口集成：

1. HTTP API

- 创建 Review 任务
- 查询任务状态
- 查询 Review 进度
- 生成 dry-run 计划
- 在用户确认后触发执行

2. CLI 包装器，后续可选

- `video-review scan PATH`
- `video-review job JOB_ID`
- `video-review plan JOB_ID`

3. 通知

- video-review 返回任务状态和链接
- Hermes 负责把链接发到 Telegram、微信、Open WebUI 或其他消息渠道

这样设计后，cron、curl、Mac 脚本、其他自动化服务也可以使用 video-review。

## 默认容器路径

容器内默认路径：

```text
/media/download   下载目录，可写，用于扫描和直接删除已确认文件
/media/library    媒体库目录，可写，用于扫描和直接删除已确认文件
/app/data         应用数据目录
```

NAS 上的推荐映射：

```text
/nas/download -> /media/download:rw
/nas/media    -> /media/library:rw
./data        -> /app/data
```

## 当前 v0.2.0 流程

```text
用户/Lucky/浏览器
  -> video-review Web 页面
  -> FastAPI
  -> SQLite
  -> 返回任务列表/任务详情
```

当前版本已验证部署、任务记录、扫描、截图和浏览器确认后的直接删除链路。

## 当前完整流程

```text
用户通过 Lucky/浏览器打开 video-review
  -> 创建 Review 任务并扫描目录
  -> video-review 扫描目录并生成截图
  -> 用户在 Web 页面保存 Review 决策
  -> 用户把文件标记为“待删除”
  -> 用户点击“删除文件（N）”并确认浏览器弹窗
  -> video-review 通过读写媒体挂载直接删除已确认文件
  -> video-review 从 SQLite 任务条目中移除已删除文件
```
