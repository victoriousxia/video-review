# 功能列表

## v0.3.2 已支持

- 标准 Git 管理的 Docker 项目结构
- GitHub 协作流程：`victoriousxia/video-review`
- FastAPI 应用骨架的首页
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
- 递归扫描指定目录下的视频文件
- 识别常见视频扩展名（mp4、mkv、avi、mov、wmv、flv、webm、m4v、ts、rmvb 等）
- 自动跳过临时文件和下载中文件
- 扫描结果写入 `review_items`（路径、文件名、目录、大小、扩展名、mtime）
- `POST /api/v1/jobs/{job_id}/scan` 触发扫描
- Job 状态流转：pending → running → ready/failed
- 任务详情页展示视频条目表格
- 测试支持 Mac 本地运行
- Web 创建任务表单（首页和 /jobs 页面）
- `POST /jobs` HTML form 创建任务，303 跳转
- scan_now=true 创建后立即扫描
- 任务详情页扫描/重新扫描按钮
- SQLite additive migration 自动补齐老库缺失字段
- replace_items 解决重新扫描重复问题
- docker-compose.nas.yml NAS host network 部署
- 任务详情页 ?dir= 参数浏览子目录
- 目录仪表盘：子目录列表、直接文件数、递归总数、pending/已处理统计
- 面包屑导航
- 当前目录文件列表只展示直接文件
- 非法 dir 参数返回 400
- `PATCH /api/v1/items/{item_id}` 支持 review_status / user_action / user_notes
- review_status 可选值：pending、keep、move_later、delete_later、ignore、unsure

## v0.3.2 未支持

- ffprobe 元数据提取
- ffmpeg 截图生成
- 动态重新生成截图批次
- 执行计划 dry-run
- 文件移回收站操作
- Hermes 触发通知
- 定时扫描

## 后续计划

- 元数据提取
- 截图批次
- 动态截图重新生成
- 安全 dry-run 执行计划
- 回收站优先的安全执行
- Hermes 消息触发和通知
- 定时扫描
