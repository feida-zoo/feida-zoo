# Zoo Dev-Center (飝龘动物园研发中心) v1.0 架构设计方案 🐢

**版本**: 1.0
**状态**: 设计中 (Draft)
**架构师**: 阿尔法 (Alpha/玄龟) 🐢
**更新日期**: 2026-04-06

## 1. 概述 (Overview)

为了满足生态演进需求，现将原有的“简单状态展示面板 (Zoo-Dashboard)”全面升级为“全链路研发管控中心 (Zoo Dev-Center)”。本系统旨在将动物园的研发流程标准化、可视化，实现从需求流转、代码提交到安全审计的无缝闭环。

## 2. 核心设计目标与子系统

### 2.1 需求生命周期管理 (Backlog Kanban)
**数据源**: `task_tracker.json` 的深度解析与重构扩展。
**交互设计**:
- **四象限看板流转**: 将任务分为四个核心列：
  1. 📥 **需求池 (Backlog)**: 尚未分配或规划中的需求。
  2. 🚧 **进行中 (In Progress)**: 织巢 (🐜) 正在施工的任务。
  3. 🔍 **待验收 (In Review)**: 触发虚拟 PR，等待毒刺 (🦂) 审计的任务。
  4. ✅ **已完成 (Done)**: 审计通过并合并入主干的任务。
- **关联挂载**: 每一个 Task 在看板卡片上强制挂载对应的“虚拟 PR 链接”与关联的 Git Commit ID，实现需求与代码的双向追溯。

### 2.2 Git 集成与实时时间线 (Git Sync & Timeline)
**数据源**: 物理文件系统 `code/feida_zoo/.git/` 与 Git 钩子。
**后端机制**:
- 采用 `pygit2` 或通过 `subprocess` 直接调用 `git log --pretty=format` 实时获取仓库状态。
- **Commit History 渲染**: 在看板右侧或底部开辟“生态时间线”专区，实时渲染 Git 提交记录。根据 Commit Message 中的专属 Emoji（如 🐢, 🐜, 🦂, 🐼），自动在时间线上高亮显示归属成员。

### 2.3 虚拟 PR 闭环机制 (Virtual PR Workflow)
为了弥补纯本地环境缺失协作平台的遗憾，我们设计了一套轻量级的“虚拟 PR (Pull Request)”流转机制：
1. **发起**: 织巢 (🐜) 完成当前 Task 代码后，生成 Patch 文件或通过比对工作区触发虚拟 PR，生成唯一的 `PR_ID`。
2. **审计**: 毒刺 (🦂) 接收到 PR 事件后，在看板界面针对 diff 代码块进行“行级提意见 (Line-level comments)”。
3. **修复与再审**: 织巢根据意见提交修正，并在虚拟 PR 下回复。整个对话记录、代码 Diff 状态在看板的“PR 详情页”可视化。
4. **闭环合入**: 毒刺确认无误后点击“批准 (Approve)”，系统自动或由织巢触发 `git merge`，任务自动流转至“✅ 已完成”。

## 3. 后端 Event 监听与对接设计

### 3.1 基于文件与 Hook 的事件总线
我们拒绝引入重量级的 Redis 或 MQ，采用**文件型 Event Bus + Git Hooks** 实现轻量解耦：
- **Git 钩子对接**: 
  激活 `.git/hooks/post-commit` 与 `post-merge`。当物理仓库发生变更时，触发 Python 脚本向 `dashboard/data/events.json` 追加一条事件记录（如：`type: commit, author: 🐜, hash: xxx`）。
- **Event 轮询/SSE 监听**:
  Dashboard 后端（Flask/FastAPI）建立一个 Event Watcher 线程，利用 `watchdog` 监控 `events.json` 和 `task_tracker.json` 的变动。
  一旦发生变更，通过 Server-Sent Events (SSE) 或 WebSocket 向前端推送更新，实现零刷新实时响应。

## 4. 史官标识修正声明 (Aeterna Identity Correction)

在早期的生态设定及 `registry.json` 中，永恒史官 Aeterna 的图腾存在混淆（曾出现 🪨 等标识）。
**架构师纠偏决议**：自本方案起，史官 Aeterna 的唯一官方图腾正式确立为 **📜 (羊皮卷/史卷)**。
所有前端渲染、Git Commit 识别及日志聚合中，只要检测到史官的输出，必须统一采用 📜 标识，彰显其铭刻历史的属性。

## 5. 目录结构与接口演进建议

```text
dashboard/
├── app.py                 # 增强版 Dashboard 后端 (引入 SSE 机制)
├── git_adapter.py         # 新增：封装 Git 状态获取与虚拟 PR 解析逻辑
├── templates/
│   └── dev_center.html    # 全新研发中心 UI 视图
└── static/
    ├── js/kanban.js       # 四象限拖拽与流转逻辑
    └── js/pr_viewer.js    # 虚拟 PR Diff 渲染与行级评论模块
```

## 6. 结语
Zoo Dev-Center 将成为动物园多智能体协作的心脏。它不仅是一个“看板”，更是规范、透明、严谨的工程化体现。稳固的底盘，才能承载星河般浩瀚的生态进化。🐢✨
