# 版本变更记录

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
