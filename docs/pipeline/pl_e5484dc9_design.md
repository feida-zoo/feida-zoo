# Design 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」界面

**阶段**: design  
**设计人**: 阿尔法 (Alpha) 🐢  
**日期**: 2026-05-29  

---

## 一、需求评审

### 1.1 问题陈述
1. 需求和问题是 Pipeline 自动派发的，新建时指派成员没有意义
2. 完成后所有需求/问题都挂在阿尔法名下（dev 阶段执行者），assignee 字段失真
3. 建议直接删除 assignee 界面元素和相关逻辑

### 1.2 可行性评估 ✅
- **可行**: 仅删除 UI 字段和后端字段，不破坏 Pipeline 派发核心逻辑
- **依赖**: `_phase_assignee` 使用 `requirement.assignee`（用户填写值）作兜底 → 需改为永不用 assignee 字段，完全依赖 `_pick_phase_agent` 自动路由
- **风险**: 低 — Pipeline 核心的 `_phase_assignee` 目前先检查 `requirement.assignee`，再 fallback 到 `_pick_phase_agent`。删除 assignee 后所有 req 都将走自动路由，这正是期望行为
- **优先级**: P1（界面整洁/语义正确性，非功能阻断）

### 1.3 需求合理性判定
**判定: 合理** ✅
- Pipeline 自动路由是设计意图，assignee 字段成为误导性残留
- 删除后数据更干净，逻辑更一致

---

## 二、架构设计

### 2.1 What — 产出物

| 产出 | 路径 | 说明 |
|------|------|------|
| 修改 HTML | `dashboard/templates/dev_center.html` | 移除需求和问题的 assignee 下拉框 |
| 修改 JS | `dashboard/static/dev_center.js` | 移除 assignee 读取/提交/显示逻辑 |
| 修改后端 | `dashboard/app_enhanced.py` | 移除 assignee 字段处理 |
| 修改后端 | `framework/core/mesh/zoo_mesh_daemon.py` | `_phase_assignee` 移除 assignee 兜底，纯自动路由 |
| Design 文档 | `docs/pipeline/pl_e5484dc9_design.md` | 本文件 |

### 2.2 Why — 为什么要删

| 当前问题 | 根因 |
|----------|------|
| 新建需求时 assignee 无用 → 用户总选错或留空 | Pipeline 自动派发不依赖用户填写 |
| 完成后全挂 alpha → assignee 数据失真 | dev 阶段自动路由到 alpha，用户填的 assignee 被覆盖 |
| UI 含多余字段 → 增加用户认知负荷 | 用户不需要也不能正确填写 |

### 2.3 Tradeoff

| 选项 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 完全删掉 assignee 字段 | UI 简洁，逻辑干净 | 历史数据的 assignee 暴露 | ✅ |
| UI 隐藏但不删后端 | 可快速恢复 | 拖泥带水，逻辑混乱 | ❌ |
| 保留但置灰 | 兼容旧数据 | 仍占空间 | ❌ |

### 2.4 接口变更

**删除的字段:**
- 需求表单: `req-assignee` 下拉框
- 问题表单: `issue-assignee` 下拉框
- API 创建需求: 请求体中的 `assignee` 字段
- API 创建问题: 请求体中的 `assignee` 字段
- 需求详情: 卡片上的 assignee 显示
- 问题详情: 列表中的 assignee 显示
- 看板需求项: `task.assignee` 显示

**后端行为变更:**
- `_phase_assignee`: 移除 `requirement.assignee` 优先逻辑，直接委托给 `_pick_phase_agent(phase)`
- 创建需求的 SSE/通知: 移除 assignee 相关逻辑
- dashboard 需求/问题 API: 移除 assignee 字段处理

**保持不变:**
- `_pick_phase_agent(phase)` 自动路由 → 永远准确
- `requirement.assignee` 字段仍写入，但不再被 UI 读取和显示

### 2.5 文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `dashboard/templates/dev_center.html` | 删除 UI 元素 | 删除需求和问题表单的 assignee 下拉框 |
| `dashboard/static/dev_center.js` | 删除 JS 逻辑 | 删除 assignee 读取/填充/提交/显示逻辑 |
| `dashboard/app_enhanced.py` | 删除后端处理 | 删除 assignee 表单处理、通知、响应体 |
| `framework/core/mesh/zoo_mesh_daemon.py` | 修改 core 逻辑 | `_phase_assignee` 移除 `requirement.assignee` 兜底 |

### 2.6 改动量估算

| 文件 | 改动量 |
|------|--------|
| dev_center.html | ~4 行删除（2 个下拉框） |
| dev_center.js | ~30 行删除（表单读取、看板显示、任务详情） |
| app_enhanced.py | ~20 行删除（参数解析、赋值、响应） |
| zoo_mesh_daemon.py | ~4 行修改（`_phase_assignee` 简化） |

---

## 三、UI 设计

### 3.1 删除内容（需求表单当前布局 → 移除后）

```
当前:
  ┌─ 创建新需求 ──────────────────────┐
  │  标题: [________]                   │
  │  描述: [________]                   │
  │  优先级: [P0 ▼]                     │
  │  指派给: [-- 选择成员 -- ▼]  ← 删除 │
  │  [提交需求]                         │
  └───────────────────────────────────┘

删除后:
  ┌─ 创建新需求 ──────────────────────┐
  │  标题: [________]                   │
  │  描述: [________]                   │
  │  优先级: [P0 ▼]                     │
  │  [提交需求]                         │
  └───────────────────────────────────┘
```

### 3.2 删除内容（问题表单同理）

```
当前:
  ┌─ 创建问题 ────────────────────────┐
  │  标题: [________]                   │
  │  描述: [________]                   │
  │  优先级: [P3 ▼]                     │
  │  指派给: [-- 选择成员 -- ▼]  ← 删除 │
  │  [创建问题]                         │
  └───────────────────────────────────┘
```

### 3.3 看板任务详情

当前看板 item 显示 `<span class="detail-value">🐢 alpha</span>` — **也删除**，因为：
- Pipeline 自动路由，显示执行者没有用户操作的场景
- 如果需要故障排查，可从 requirements.json 追溯

### 3.4 问题列表

当前显示 `<span class="issue-assignee"><i class="fas fa-user"></i> 🐢 阿尔法</span>` — **也删除**，理由同上

---

## 四、状态定义

无状态变更。只是 UI 展示和表单输入的清理。

### 影响范围确认

| 场景 | 改前 | 改后 |
|------|------|------|
| 新建需求 | 用户选指派成员 → 写入 .assignee | 不显示，Pipeline 自动路由 |
| 新建问题 | 同上 | 同上 |
| 看板显示 | 显示 .assignee (🐢 阿尔法) | 不显示 |
| 问题列表 | 显示 .assignee (🐢 阿尔法) | 不显示 |
| Pipeline 派发 | `_phase_assignee` 优先用 .assignee | 完全走自动路由 |
| 历史数据 | assignee 字段仍存在 | 不展示，不删除历史值 |
