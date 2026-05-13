# 发布流程

每个版本都必须维护代码、测试和文档的一致性。

## 发布前检查

1. 确认代码已同步远端：

```bash
git pull --ff-only
```

2. 运行测试。
3. 构建 Docker 镜像。
4. 启动容器并检查 `/healthz`。
5. 验证关键页面能打开。
6. 更新版本文档。

## 每个版本必须更新

- `VERSION`
- `CHANGELOG.md`
- `docs/progress.md`
- `docs/feature-list.md`
- 必要时更新 `README.md` 和相关 docs

## 提交规则

提交信息使用简洁格式：

```text
feat: add review job API
fix: correct Lucky deployment docs
docs: translate project docs to Chinese
release: complete v0.2.0 deployment flow
```

## Docker 验证

```bash
docker build -t video-review:版本号 .
docker run --rm -p 8818:8818 video-review:版本号
```

正式部署建议用：

```bash
docker compose up -d --build
```

## 禁止事项

不要为了构建或部署 video-review 修改 NAS 全局 Docker daemon DNS。这个操作影响所有容器，风险过高。
