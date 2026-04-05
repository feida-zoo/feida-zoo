# Zoo-Dashboard v1.0 架构设计方案 🐢

**版本**: 1.0
**状态**: 草案 (Draft)
**架构师**: 阿尔法 (Alpha/玄龟) 🐢
**日期**: 2026-04-05

## 1. 概述
Zoo-Dashboard 是一个专为“飝龘动物园”设计的轻量化 Web 监控与交互面板。它旨在提供一个类似 OpenClaw Gateway UI 的视觉界面，使用户（园长）能够实时掌握所有成员（Agents）的状态、任务进度及系统日志。

## 2. 设计原则
- **轻量化 (Lightweight)**: 极简依赖，不引入复杂的重型框架，前端优先使用原生 JS/CSS。
- **文件驱动 (File-Driven)**: 核心数据来源于 `shared/` 目录下的 JSON/MD 文件，无需独立数据库。
- **低延迟 (Low Latency)**: 采用高效的文件轮询或 WebSockets (如果环境支持) 实现数据同步。
- **稳定性 (Stability)**: 进程隔离，仪表盘故障不应影响核心 Agent 的运行。

## 3. 核心功能
### 3.1 成员注册表 (Member Registry)
- **展示**: 可视化展示所有成员（Alpha, Weaver, Duci, Gulu, Aeterna）的在线状态、负载、当前角色。
- **数据源**: `shared/registry.json`
- **内容**: 包含名称、种族、专属 Emoji、活跃时间戳。

### 3.2 任务看板 (Task Kanban)
- **展示**: 类似 Trello 的三栏看板（待办/进行中/已完成）。
- **数据源**: `shared/tasks.md` 或 `shared/kanban.json`
- **交互**: 实时同步 Agent 提交的任务状态更新。

### 3.3 实时日志流 (Log Stream)
- **展示**: 聚合所有成员的实时执行日志。
- **数据源**: `debug_logs/` 下的实时日志文件。
- **优化**: 仅加载最后 100 行，采用滚动更新。

### 3.4 园长勋章系统 (Master Medal System)
- **功能**: 一个专属的评价显示位，实时同步园长在飞书/主会话中的评价。
- **数据源**: `shared/achievements.json`
- **视觉**: 采用发光特效（Glow Effect）展示园长授予的勋章或“蒸蚌”评价。

## 4. 技术栈架构
- **端口**: 18790
- **后端 (Server Side)**: 
    - 方案 A: 简单的 Python `http.server` 或 `FastAPI` (极简异步)。
    - 方案 B: Node.js `http` 模块 (如果环境中已包含)。
    - **选定方案**: Python 3 异步轻量级服务，直接读取文件系统。
- **前端 (Frontend)**:
    - 原生 HTML5 + CSS3 (使用 Flexbox/Grid 布局)。
    - Vanilla JS + Fetch API 定时轮询。
    - Tailwind CSS (可选 CDN 引入) 快速美化。

## 5. 目录结构规划
```text
framework/
└── shared/
    ├── zoo_dashboard_arch_v1.0.md  # 本设计文档
    ├── registry.json               # 成员动态状态
    ├── kanban.json                 # 任务看板数据
    └── achievements.json           # 园长评价与勋章
```

## 6. 数据同步机制 (Data Sync)
1. **写入端**: 各个 Agent 在执行任务或心跳时，通过 `shared-writer` 技能更新 `shared/` 下的对应的 JSON。
2. **读取端**: Dashboard Server 提供 `/api/status` 接口，读取文件并返回 JSON。
3. **前端渲染**: 前端每隔 2-5 秒发起一次 Fetch 请求，局部刷新 DOM 节点。

## 7. 安全与访问
- 仅限本地回环地址 (127.0.0.1) 访问，或通过 OpenClaw Gateway 提供的隧道暴露。
- 采用简单的只读权限，Dashboard 不具备对文件系统的写入权限（除了勋章同步）。

---
*阿尔法（玄龟）注：此方案优先保证“看”的能力，后续 v2.0 将引入“控”的能力。*
