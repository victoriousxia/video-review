# video-review

video-review 是一个运行在 NAS 上的视频整理 Review 服务。

它的目标不是直接“自动清理视频”，而是先把下载目录里的视频扫描出来，生成元数据、截图和整理建议，让用户在 Web 页面里逐项 Review。只有在用户 Review 完成，并通过消息渠道明确确认后，后续版本才会执行移动、重命名或回收站清理。

当前版本：0.3.2

## 当前版本能做什么

v0.3.2 在 v0.3.0 基础上补齐了 Web 创建任务、多层目录 Review 和 Review 状态 PATCH API：

- Docker 服务可以启动
- Web 首页可以打开
- `/healthz` 健康检查可用
- `/api/v1/info` 服务信息接口可用
- SQLite 数据库会在启动时初始化
- 可以创建 Review 任务记录
- 可以查看任务列表和任务详情页
- 可以通过 Lucky 反代访问页面
- 可以触发目录扫描，递归发现视频文件
- 扫描结果写入 review_items，记录路径、文件名、大小、扩展名、修改时间
- 任务详情页支持按子目录浏览，并展示子目录直接文件数、递归总数、待处理/已处理数量
- 可以在 Web 页面创建任务，并选择创建后立即扫描
- `/api/v1/items/{item_id}` PATCH 可以保存 Review 状态、用户动作和备注
- 重新扫描会替换旧条目，避免重复生成 review_items
- Job 状态正确流转：pending → running → ready/failed

注意：v0.3.2 不会调用 ffprobe 提取元数据，不会生成截图，也不会移动、重命名或删除任何媒体文件。

## 架构原则

video-review 优先是一个通用 Docker 服务，Hermes 只是可选编排器。

video-review 负责：

- 管理 Review 任务
- 保存任务和条目数据
- 提供 Web UI
- 提供 HTTP API
- 后续负责扫描、截图、Review 决策、执行计划

Hermes 负责：

- 根据聊天命令触发扫描
- 给用户发送 Review 链接和通知
- 读取 Review 进度
- 在执行整理前向用户确认
- 调用 video-review API 执行后续动作

这样设计可以避免项目和 Hermes 强耦合。以后即使用 curl、cron、Mac 脚本或其他自动化服务，也可以调用 video-review。

## 目录结构

```text
app/                  FastAPI 应用代码
app/templates/        Web 页面模板
docs/                 项目文档
tests/                自动化测试
Dockerfile            Docker 镜像构建文件
docker-compose.yml    NAS 部署用 compose 文件
.env.example          环境变量示例
VERSION               当前版本号
CHANGELOG.md          版本变更记录
ROADMAP.md            版本路线图
```

## NAS 部署

当前用户 NAS 上已验证可用的运行方式是 host 网络模式，容器名为 `video-review`，监听：

```text
http://192.168.5.2:8818/
```

原因：本环境中 Docker bridge 端口发布曾出现局域网访问超时；host 网络模式已验证可以从同一局域网浏览器正常访问。

当前运行命令等价于：

```bash
sudo docker run -d \
  --name video-review \
  --restart unless-stopped \
  --network host \
  -e VIDEO_REVIEW_HOST=0.0.0.0 \
  -e VIDEO_REVIEW_PORT=8818 \
  -e VIDEO_REVIEW_DATA_DIR=/app/data \
  -e VIDEO_REVIEW_DOWNLOAD_ROOT=/media/download \
  -e VIDEO_REVIEW_LIBRARY_ROOT=/media/library \
  -v /vol2/1000/Docker/video-review/data:/app/data \
  -v /vol1/1000/Download:/media/download:ro \
  -v /vol1/1000/Media:/media/library:ro \
  video-review:v0.3.2
```

下面的 compose 方式是项目标准化目标，但当前 FnOS 环境下仍需要后续验证/优化。

在 NAS 宿主机或有 Docker Compose 权限的环境执行：

```bash
cd /vol2/1000/Docker/video-review
git pull
cp .env.example .env
```

根据需要编辑 `.env`：

```text
VIDEO_REVIEW_PUBLIC_BASE_URL=https://video-review.example.com
VIDEO_REVIEW_DOWNLOAD_ROOT=/media/download
VIDEO_REVIEW_LIBRARY_ROOT=/media/library
VIDEO_REVIEW_AUTH_MODE=none
```

启动：

```bash
docker compose up -d --build
```

如果系统使用旧版 compose：

```bash
docker-compose up -d --build
```

默认端口：

```text
http://NAS_IP:8818
```

## Lucky 反代

推荐 Lucky 反代目标：

```text
http://NAS_IP:8818
```

推荐外部访问地址：

```text
https://video-review.你的域名
```

Lucky 上必须开启 HTTPS 和认证。v0.x 阶段建议认证放在 Lucky 层处理，video-review 应用内部暂时保持 `VIDEO_REVIEW_AUTH_MODE=none`。

详细步骤见：

```text
docs/lucky-deployment.md
```

## 联通性测试

服务启动后先访问：

```text
http://NAS_IP:8818/
http://NAS_IP:8818/healthz
http://NAS_IP:8818/jobs
```

创建一个测试 Review 任务：

```bash
curl -X POST http://NAS_IP:8818/api/v1/jobs   -H 'Content-Type: application/json'   -d '{"name":"Lucky 联通性测试","scan_path":"/media/download","notes":"验证 Lucky 反代流程"}'
```

然后打开：

```text
http://NAS_IP:8818/jobs
```

如果能看到任务，说明 Docker 服务、SQLite、API、Web 页面基础链路已经跑通。

## Mac 协作开发

GitHub 主仓库：

```text
git@github.com:victoriousxia/video-review.git
```

Mac 上拉取：

```bash
git clone git@github.com:victoriousxia/video-review.git
```

日常协作规则：

```bash
git pull --ff-only
# 修改代码
git add .
git commit -m "说明本次改动"
git push
```

Hermes 继续开发前也会先 `git pull --ff-only`，避免覆盖你在 Mac 上的提交。

## 安全边界

当前版本不会改动媒体文件。

后续版本也会遵守：

- Review 阶段不移动、不重命名、不删除视频
- 删除默认先进入任务专属回收目录
- 执行动作前必须生成 dry-run 计划
- 整理/清理必须由用户在消息渠道明确确认
- 下载中、最近修改、疑似占用的文件默认跳过

## 重要环境约束

不要为了这个项目修改 NAS 的全局 Docker daemon DNS。

之前全局 DNS 修改曾导致 Hermes/Open WebUI/模型连接异常。项目必须使用低风险构建和部署策略，不依赖修改现有 Docker 全局网络。
