# Review 工作流

## 当前 v0.2.0 可验证流程

v0.2.0 用来验证 Docker、Lucky、Web、SQLite 和 API 是否能串起来。

流程：

1. 启动 Docker 服务。
2. 打开首页 `/`。
3. 打开健康检查 `/healthz`。
4. 打开任务列表 `/jobs`。
5. 通过 API 创建一个测试 Review 任务。
6. 回到 `/jobs`，确认任务出现。
7. 点击任务进入 `/jobs/{job_id}`，确认任务详情页可打开。
8. 通过 Lucky 外部地址重复上述访问，确认反代可用。

这个阶段不会扫描真实视频，也不会生成截图。

## 未来完整工作流

1. 用户通过消息渠道告诉 Hermes：把某个目录整理 Review 一下。
2. Hermes 调用 video-review 创建 Review 任务。
3. video-review 扫描目录，记录候选视频。
4. video-review 使用 ffprobe 提取元数据。
5. video-review 使用 ffmpeg 生成第一批截图。
6. Hermes 通知用户 Review 链接。
7. 用户通过 Lucky 打开 Web 页面。
8. 用户逐个查看视频信息、路径、大小、截图和整理建议。
9. 如果截图不满意，用户重新生成截图批次。
10. 用户保存每个视频的 Review 决策。
11. Hermes 查询 Review 是否完成。
12. video-review 生成 dry-run 执行计划。
13. Hermes 把计划摘要发给用户确认。
14. 用户明确确认执行。
15. video-review 执行移动、重命名或回收站操作。
16. Hermes 通知执行结果。

## Review 决策类型规划

后续每个视频至少支持这些决策：

- 保留原位
- 按建议整理
- 手动指定目标路径
- 手动指定新文件名
- 标记为重复，暂不删除
- 标记为可删除，等待二次确认
- 忽略
- 需要进一步分析
