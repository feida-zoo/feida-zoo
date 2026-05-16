# design: 动物园仪表盘自启动

## What — 要做什么
Gateway 重启后，Dashboard（app_enhanced.py）失去进程，需要手动重启。改为由 Pipeline plugin 在 gateway_start 时自动启动，无需人工介入。

## Why — 为什么要这么做
当前每次重启 Gateway 后 Dashboard 就掉了，需要手动 `nohup python app_enhanced.py`。如果要 Agent 能独立运行，Dashboard 的生命周期必须与 OpenClaw Gateway 绑定。

## Tradeoff — 权衡

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **A（选定）** | Pipeline plugin 的 gateway_start 里 spawn 子进程 | 与 ZooMesh daemon 同模式，一致性高 | 多一个子进程 |
| B | macOS LaunchAgent 自启 | 不依赖插件 | 需要额外配置 |
| C | systemd / cron | 跨平台差 | 要改外部配置 |

选定 A，与现有 ZooMesh daemon 管理代码完全一致。

## Open Questions
- Dashboard 的 Python 路径：hardcode `venv/bin/python` 还是从环境变量读取？
- 端口冲突：如果 Dashboard 被其他进程占用，启动失败如何处理？

## Next Action
请毒刺审查方案，确认后再实现。
