# 项目进度

当前版本：0.2.0

远端仓库：`git@github.com:victoriousxia/video-review.git`

NAS 工作目录：`/nas/docker/video-review`

## 已完成

- 选定仓库路径：`/nas/docker/video-review`
- 初始化 Git 仓库，主分支为 `main`
- 配置 GitHub remote：`git@github.com:victoriousxia/video-review.git`
- 配置 NAS/Hermes 专用 GitHub deploy key，具备该仓库写权限
- 已推送代码到 GitHub
- 明确项目架构：通用 Docker 服务优先，Hermes 可选编排
- 明确 Hermes 集成边界：通过 HTTP API/CLI/通知集成，不强耦合
- 建立项目文档体系
- FastAPI 服务骨架
- 首页 `/`
- 健康检查 `/healthz`
- 服务信息 `/api/v1/info`
- 应用数据目录：
  - `/app/data/screenshots`
  - `/app/data/jobs`
  - `/app/data/logs`
- Dockerfile 和 `docker-compose.yml`
- 避免修改全局 Docker daemon DNS；之前该操作曾影响 Hermes/Open WebUI/模型连接
- 发布 v0.1.0 服务基础版本
- 发布 v0.2.0 Docker/Lucky 流程和 Review 任务基础版本
- SQLite 启动初始化
- SQLite 表：
  - `schema_meta`
  - `review_jobs`
  - `review_items`
- API：
  - `GET /api/v1/jobs`
  - `POST /api/v1/jobs`
  - `GET /api/v1/jobs/{job_id}`
- 扫描路径校验：仅允许配置的下载目录和媒体库目录
- Web 页面：
  - `/jobs`
  - `/jobs/{job_id}`
- 首页展示最近任务和部署配置
- Lucky 部署文档
- 主要项目文档已改为中文

## 进行中

- 用户侧 Lucky 反代部署验证
- 反代后的 Web 页面和 smoke-test 流程验证

## 待实现

- 真实视频文件扫描
- Review 任务下的视频条目创建
- ffprobe 元数据提取
- 截图批次生成和重新生成
- Review 决策保存
- 整理建议
- dry-run 执行计划
- Hermes 触发通知
- 安全执行器

## 最近验证

- GitHub SSH deploy key 之前已验证可用于 `victoriousxia/video-review`。
- `docker build -t video-review:v0.2.0 .` 之前已在 NAS 上成功，不需要 `apt-get`，也不需要改 Docker daemon DNS。
- `video-review-v020-final` 容器当前运行中，镜像为 `video-review:v0.2.0`，端口映射为 `0.0.0.0:18818->8818/tcp`。
- 容器内部之前验证过：`GET /healthz` 正常，`GET /api/v1/jobs` 正常。
- 容器内部之前验证过：`POST /api/v1/jobs` 可以创建 smoke-test 任务，`GET /api/v1/jobs/{job_id}` 可以读取。
- 单元测试之前在项目镜像真实挂载路径下通过：`8 passed`。

## 重要环境记录

不要要求或建议为了 video-review 修改 NAS 全局 Docker daemon DNS。之前 daemon 级 DNS 修改导致 Hermes/Open WebUI/模型连接异常，已从备份恢复。项目必须使用低风险构建/部署策略，不改变现有容器全局网络。

## 构建说明

Dockerfile 当前默认使用 `openwebui/open-webui:0.9.5` 作为临时 NAS 本地基础镜像，因为该镜像已存在并包含 FastAPI/Uvicorn/Jinja2/Pytest 等依赖。这让当前版本可以在外部包索引解析不稳定的情况下构建。后续网络/构建条件稳定后，应替换为更轻量的专用运行时镜像。

## 网络说明

Hermes 执行环境访问宿主映射端口时可能出现 connection refused，即使 Docker 已显示端口发布且服务在容器内正常。Lucky 验证应以 NAS UI、Mac 浏览器或宿主机 SSH 访问为准。
