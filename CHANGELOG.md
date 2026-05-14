# 版本变更记录

## 0.3.2 - 2026-05-15

多层目录 Review 和 Review 状态保存。

新增：

- 任务详情页支持 `?dir=<relative_dir>` 参数浏览子目录。
- 目录仪表盘：展示子目录列表、直接文件数、递归总数、pending/已处理统计。
- 每个子目录提供"进入目录"链接，支持逐层浏览。
- 面包屑导航，方便在目录层级间跳转。
- 当前目录文件列表只展示当前目录直接文件，不递归。
- 非法 dir 参数（绝对路径、包含 `..`）返回 400。
- 新增 `PATCH /api/v1/items/{item_id}` 接口，支持更新 review_status / user_action / user_notes。
- review_status 可选值：pending、keep、move_later、delete_later、ignore、unsure。
- API 和 Web 的 `GET /api/v1/jobs/{job_id}?dir=` 支持按目录过滤 items。

限制：

- 当前阶段只写数据库，不移动、不删除、不重命名媒体文件。

## 0.3.1 - 2026-05-15

Web 创建任务和扫描入口。

新增：

- 首页和 `/jobs` 页面顶部增加创建 Review 任务表单。
- 表单字段：name、scan_path、notes、scan_now。
- `POST /jobs` 支持 HTML form 创建任务，成功后 303 跳转到任务详情页。
- scan_now=true 时创建后立即触发扫描。
- 任务详情页 pending 状态显示"开始扫描"按钮。
- 任务详情页 ready/failed 状态显示"重新扫描"按钮。
- `POST /jobs/{job_id}/scan` Web 端点触发扫描后 303 跳转回详情页。
- 所有 scan_path 仍限制在 /media/download 或 /media/library 下。

修复：

- SQLite additive migration：老库缺少 review_items.extension / file_mtime 字段时自动补齐。
- 重新扫描不再产生重复 items：使用 replace_items 先删旧再写新。
- 新增 docker-compose.nas.yml 用于 NAS host network 部署。

## 0.3.0 - 2026-05-15

真实目录扫描和视频条目生成。

新增：

- 新增扫描器模块，递归扫描指定目录下的视频文件。
- 识别常见视频扩展名（mp4、mkv、avi、mov、wmv、flv、webm、m4v、ts、rmvb 等）。
- 自动跳过临时文件、下载中文件（.part、.!qb、.aria2、隐藏文件等）。
- 扫描路径必须在配置允许的根目录下，禁止越权路径。
- 新增 `POST /api/v1/jobs/{job_id}/scan` 接口，触发目录扫描。
- 扫描结果写入 `review_items` 表，保存路径、文件名、目录、大小、扩展名、mtime、初始状态。
- Job 状态流转：pending → running → ready/failed。
- 数据库 schema 升级到 v2，`review_items` 新增 `extension` 和 `file_mtime` 字段。
- 任务详情页展示扫描到的视频条目表格（文件名、大小、扩展名、修改时间、状态）。
- 未扫描任务显示 API 触发提示，扫描失败显示错误提示。
- 新增测试 conftest 支持 Mac 本地运行测试（不再依赖 Docker 内 /app/data 路径）。
- 新增 scanner 单元测试（9 个）和 scan API 集成测试（4 个）。

变更：

- 创建任务时初始状态从 `ready` 改为 `pending`（需先触发扫描）。
- 首页描述更新为反映扫描能力。

限制：

- v0.3.0 不调用 ffprobe，不提取视频元数据。
- v0.3.0 不生成截图。
- v0.3.0 不移动、重命名或删除任何媒体文件。

## 0.2.0 - 2026-05-13

Docker/Lucky 部署流程和 Review 任务基础版本。

新增：

- 服务启动时初始化 SQLite 数据库。
- 新增数据表：
  - `schema_meta`
  - `review_jobs`
  - `review_items`
- 新增 Review 任务 API：
  - `GET /api/v1/jobs`
  - `POST /api/v1/jobs`
  - `GET /api/v1/jobs/{job_id}`
- 新增扫描路径校验，只允许在配置的下载目录和媒体库目录下创建任务。
- 新增 Web 页面：
  - `/jobs`
  - `/jobs/{job_id}`
- 首页展示版本、路径、数据库、公开地址、最近任务和安全状态。
- 能力标识中开启 `scan_jobs: true`，但仍保持 `media_mutation: false`。
- 在 NAS 上验证 Docker 镜像可以构建，不需要修改全局 Docker daemon DNS。
- 验证容器可以启动、初始化 SQLite、创建和读取 smoke-test 任务。
- 新增 Lucky 反代部署文档。

限制：

- v0.2.0 只创建 Review 任务记录，还不会扫描真实视频。
- v0.2.0 还不会生成截图。
- v0.2.0 不会移动、重命名或删除任何媒体文件。
- Hermes 执行环境里访问宿主映射端口可能不稳定；Lucky 访问请从 NAS UI、Mac 浏览器或宿主网络路径验证。

## 0.1.0 - 2026-05-13

可运行的 Docker/FastAPI 服务基础版本。

新增：

- 项目定位为通用 Docker 服务，Hermes 作为可选编排器。
- FastAPI 应用骨架。
- `/` 首页。
- `/healthz` 健康检查接口。
- `/api/v1/info` 服务信息接口。
- 显式能力标识，方便自动化客户端判断当前支持哪些功能。
- 显式安全标识，说明当前版本不会移动或删除媒体。
- 应用数据目录：
  - `/app/data/screenshots`
  - `/app/data/jobs`
  - `/app/data/logs`
- FastAPI 启动逻辑使用 lifespan，避免 deprecated `on_event`。
- Dockerfile 避免 `apt-get`，不要求改 Docker daemon DNS。
- 在 NAS 上完成 Docker 镜像构建验证。
- 在现有 Open WebUI Python 环境里完成基础测试验证。

限制：

- v0.1.0 不扫描视频。
- v0.1.0 不生成截图。
- v0.1.0 不移动、重命名或删除任何媒体文件。
- Dockerfile 暂时默认使用本地已有的 `openwebui/open-webui:0.9.5` 作为基础镜像，以绕开 NAS Docker build 阶段外网 DNS 问题。后续应替换为更轻量的专用运行时镜像。

## 0.1.0-dev

初始项目骨架：

- Git 仓库初始化
- FastAPI 应用骨架
- 健康检查
- 配置模型
- 项目文档
- Dockerfile
- docker-compose.yml
