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
/media/download   下载目录，只读
/media/library    媒体库目录，后续执行整理时可写
/app/data         应用数据目录
```

NAS 上的推荐映射：

```text
/nas/download -> /media/download:ro
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

当前版本只验证部署和任务记录链路。

## 后续完整流程

```text
用户对 Hermes 说：整理某个目录 review 一下
  -> Hermes 调用 video-review 创建扫描任务
  -> video-review 扫描目录、提取元数据、生成截图
  -> Hermes 通知用户 Review 链接
  -> 用户通过 Lucky 打开 Web 页面并保存 Review 决策
  -> Hermes 查询 Review 进度
  -> video-review 生成 dry-run 执行计划
  -> Hermes 把计划摘要发给用户确认
  -> 用户明确确认执行
  -> video-review 安全移动/重命名/回收文件
  -> Hermes 通知执行结果
```
