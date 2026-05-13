# 功能列表

## v0.2.0 已支持

- 标准 Git 管理的 Docker 项目结构
- GitHub 协作流程：`victoriousxia/video-review`
- FastAPI 应用骨架
- 移动端友好的首页
- `/healthz` 健康检查接口
- `/api/v1/info` 服务信息接口
- 自动化客户端可读取的能力标识
- 明确的安全标识：当前只 Review，不改媒体文件
- 应用数据目录：screenshots、jobs、logs
- 通用 Docker 服务优先的架构文档
- 可选 Hermes 集成边界文档
- 安全规则文档
- 当前 NAS 上可构建 Docker 镜像，不需要修改全局 Docker daemon DNS
- SQLite 启动初始化
- `review_jobs`、`review_items`、`schema_meta` 表
- Review 任务创建 API
- Review 任务列表 API
- Review 任务详情 API
- 扫描路径限制在配置的媒体根目录下
- `/jobs` Web 页面
- `/jobs/{job_id}` Web 页面
- Lucky 反代部署流程文档

## v0.2.0 未支持

- 递归扫描真实视频文件
- 从真实文件生成 `review_items`
- ffprobe 元数据提取
- ffmpeg 截图生成
- 动态重新生成截图批次
- Review 决策保存
- 执行计划 dry-run
- 文件移动、重命名、回收站操作
- Hermes 触发通知
- 定时扫描

## 后续计划

- 视频扫描
- 元数据提取
- 截图批次
- 动态截图重新生成
- Review 决策
- 安全 dry-run 执行计划
- 回收站优先的安全执行
- Hermes 消息触发和通知
- 定时扫描
