# 项目进度

当前版本：0.3.2

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
  - `POST /api/v1/jobs/{job_id}/scan`（v0.3.0 新增）
- 扫描路径校验：仅允许配置的下载目录和媒体库目录
- Web 页面：
  - `/jobs`
  - `/jobs/{job_id}`
- 首页展示最近任务和部署配置
- Lucky 部署文档
- 主要项目文档已改为中文
- 发布 v0.3.0 真实目录扫描和视频条目生成
- 扫描器模块：递归扫描、视频扩展名识别、临时文件跳过
- review_items 写入：路径、文件名、目录、大小、扩展名、mtime、初始状态
- Job 状态流转：pending → running → ready/failed
- 数据库 schema v2：新增 extension、file_mtime 字段
- 任务详情页展示视频条目表格
- 测试 conftest 支持 Mac 本地运行（21 个测试全部通过）
- 发布 v0.3.1 Web 创建任务和扫描入口
- 首页和 /jobs 页面增加创建 Review 任务表单
- POST /jobs HTML form 创建任务，303 跳转
- scan_now=true 创建后立即扫描
- 任务详情页扫描/重新扫描按钮
- SQLite additive migration 修复老库缺少 extension/file_mtime 字段
- replace_items 解决重新扫描重复 items 问题
- docker-compose.nas.yml 用于 NAS host network 部署
- 发布 v0.3.2 多层目录 Review 和状态保存
- 任务详情页支持 ?dir= 参数浏览子目录
- 目录仪表盘：子目录列表、直接文件数、递归总数、pending/已处理统计
- 面包屑导航
- 当前目录文件列表只展示直接文件
- 非法 dir 参数返回 400
- PATCH /api/v1/items/{item_id} 支持 review_status / user_action / user_notes
- 51 个测试全部通过

## 进行中

- NAS 上已完成 v0.3.2 镜像构建、正式部署和功能验收。
- Hermes 审查发现并已修复两个发布前安全/一致性问题：路径校验改为 resolve + relative_to，媒体库挂载改为只读。

## 待实现

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
- 当前正式运行容器名：`video-review`。
- 当前正式运行镜像：`video-review:v0.3.2`。
- 当前正式运行模式：`--network host`，应用直接监听 NAS 宿主网络 `0.0.0.0:8818`。
- 当前数据挂载：`/vol2/1000/Docker/video-review/data -> /app/data`。
- 当前媒体挂载：`/vol1/1000/Download -> /media/download:ro`，`/vol1/1000/Media -> /media/library:ro`。
- 容器内部已验证：`GET /healthz`、`GET /api/v1/info`、`GET /api/v1/jobs` 正常。
- 老 SQLite 数据库已在启动时迁移到 schema v2，`review_items.extension` 和 `review_items.file_mtime` 存在。
- 单元测试在项目镜像真实挂载路径下通过：`54 passed`。
- 已用 Web form 创建 `Hermes v0.3.2 验收任务`，scan_now 成功扫描真实 NAS 目录，生成 2 个条目。
- 已验证 `PATCH /api/v1/items/{item_id}` 只更新数据库 Review 状态/备注，不操作媒体文件。
- 已验证非法目录参数 `?dir=../x` 返回 400。

## 重要环境记录

不要要求或建议为了 video-review 修改 NAS 全局 Docker daemon DNS。之前 daemon 级 DNS 修改导致 Hermes/Open WebUI/模型连接异常，已从备份恢复。项目必须使用低风险构建/部署策略，不改变现有容器全局网络。

## 构建说明

Dockerfile 当前默认使用 `openwebui/open-webui:0.9.5` 作为临时 NAS 本地基础镜像，因为该镜像已存在并包含 FastAPI/Uvicorn/Jinja2/Pytest 等依赖。这让当前版本可以在外部包索引解析不稳定的情况下构建。后续网络/构建条件稳定后，应替换为更轻量的专用运行时镜像。

## 网络说明

Hermes 执行环境访问宿主映射端口时可能出现 connection refused，即使 Docker 已显示端口发布且服务在容器内正常。Lucky 验证应以 NAS UI、Mac 浏览器或宿主机 SSH 访问为准。


本环境中，Docker bridge 端口发布曾出现局域网访问超时：容器内部服务正常，`docker inspect` 也显示端口映射，但 Mac 浏览器访问 `NAS_IP:18818` 超时。已改用 host 网络模式运行正式容器，局域网访问 `http://192.168.5.2:8818/` 已由用户确认正常。后续如果改回 compose/bridge，需要单独排查 FnOS 防火墙、Docker bridge 转发或 Lucky 与服务容器同网络直连方案。

## 明天继续开发时的建议入口

1. 先读本文档、`ROADMAP.md`、`docs/feature-list.md`、`docs/lucky-deployment.md`。
2. 先执行 `git status --short --branch`，确认本地与 GitHub 同步。
3. 不要在 NAS 宿主机用 `ilaoxia` 直接 `git pull` 这份仓库；当前仓库的 Git SSH 配置使用 Hermes 容器内的 deploy key 路径。Mac 端从 GitHub 正常协作即可，Hermes 侧继续维护 NAS 工作目录。
4. 不要修改 NAS 全局 Docker daemon DNS。
5. 当前下一步优先级：先完成 Lucky 反代 smoke test；然后进入 v0.3.0，实现真实目录扫描和 `review_items` 生成。
