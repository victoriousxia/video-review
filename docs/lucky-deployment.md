# Lucky 反代部署说明

video-review 是一个普通 HTTP Docker 服务。Lucky 负责把外部 HTTPS 地址反代到 video-review，并提供账号密码认证。

## 推荐拓扑

外部访问地址：

```text
https://video-review.你的域名
```

Lucky 反代目标，优先使用：

```text
http://NAS_IP:8818
```

如果 Lucky 和 video-review 在同一个 Docker 网络，并且能解析容器名，也可以使用：

```text
http://video-review:8818
```

第一版建议先用 `http://NAS_IP:8818`，更直观，便于排查。

## 认证建议

v0.x 阶段推荐：

1. Lucky 负责 HTTPS。
2. Lucky 负责账号密码访问控制。
3. video-review 内部认证暂时设为 `VIDEO_REVIEW_AUTH_MODE=none`。
4. video-review 当前版本只创建 Review 任务，不执行媒体文件改动。

不要在没有 Lucky 认证的情况下把服务暴露到公网。

## 启动服务

在 NAS 宿主机 SSH 中执行：

```bash
cd /vol2/1000/Docker/video-review
git pull
cp .env.example .env
```

如果 `.env` 已存在，不要覆盖，直接编辑即可。

建议 `.env`：

```text
VIDEO_REVIEW_HOST=0.0.0.0
VIDEO_REVIEW_PORT=8818
VIDEO_REVIEW_DATA_DIR=/app/data
VIDEO_REVIEW_PUBLIC_BASE_URL=https://video-review.你的域名
VIDEO_REVIEW_DOWNLOAD_ROOT=/media/download
VIDEO_REVIEW_LIBRARY_ROOT=/media/library
VIDEO_REVIEW_AUTH_MODE=none
VIDEO_REVIEW_APP_TOKEN=
```

启动：

```bash
docker compose up -d --build
```

如果系统是旧版 compose：

```bash
docker-compose up -d --build
```

## 反代前验证

在 Lucky 配置前，先从 Mac 浏览器或 NAS 宿主网络访问：

```text
http://NAS_IP:8818/
http://NAS_IP:8818/healthz
http://NAS_IP:8818/jobs
```

预期结果：

- `/` 显示 video-review 首页。
- `/healthz` 返回 JSON，包含 `"ok": true`。
- `/jobs` 显示 Review 任务列表页面。

## 创建联通性测试任务

在 NAS 宿主机或 Mac 上执行：

```bash
curl -X POST http://NAS_IP:8818/api/v1/jobs   -H 'Content-Type: application/json'   -d '{"name":"Lucky 联通性测试","scan_path":"/media/download","notes":"验证 Lucky 反代流程"}'
```

然后打开：

```text
http://NAS_IP:8818/jobs
```

如果能看到 `Lucky 联通性测试`，说明：

- Docker 服务可访问
- API 可用
- SQLite 可写
- Web 页面能读取任务

## Lucky 配置

在 Lucky 中新增反代规则：

```text
域名：video-review.你的域名
目标：http://NAS_IP:8818
WebSocket：不需要
HTTPS：开启
认证：开启，使用你的 NAS/Lucky 账号密码策略
```

保存后访问：

```text
https://video-review.你的域名/
https://video-review.你的域名/healthz
https://video-review.你的域名/jobs
```

再通过外部地址创建测试任务：

```bash
curl -X POST https://video-review.你的域名/api/v1/jobs   -H 'Content-Type: application/json'   -d '{"name":"Lucky 外部联通性测试","scan_path":"/media/download","notes":"验证外部反代流程"}'
```

如果 Lucky 开启了 Basic Auth，这条 curl 需要加 `-u 用户名:密码`。

## 当前版本限制

v0.2.0 只创建 Review 任务记录。

它不会：

- 扫描真实视频
- 生成截图
- 移动文件
- 重命名文件
- 删除文件

## 环境警告

不要为了这个项目修改 NAS 全局 Docker daemon DNS。

之前全局 Docker DNS 修改曾导致 Hermes/Open WebUI/模型连接异常。video-review 必须以不影响其他容器的方式部署。

## 常见问题

### 打不开页面

检查容器是否运行：

```bash
docker ps | grep video-review
```

检查日志：

```bash
docker logs video-review --tail 100
```

检查端口：

```bash
curl http://127.0.0.1:8818/healthz
```

### /jobs 打开但没有任务

这是正常的。先用联通性测试 API 创建一个任务。

### Hermes 里 curl 宿主端口失败

当前环境中，Hermes 执行命名空间访问宿主映射端口不一定可靠。Lucky 验证请以 Mac 浏览器、NAS UI 或宿主机 SSH 结果为准。
