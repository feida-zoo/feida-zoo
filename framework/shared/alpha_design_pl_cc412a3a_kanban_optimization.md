# 🐢 看板优化 — 设计文档

**Pipeline**: pl_cc412a3a  
**需求ID**: cc412a3a-583f-4553-b8e6-dbc7df83e3c4  
**设计时间**: 2026-05-17  
**作者**: Alpha 🐢

---

## 1. What — 具体改动

### 1.1 Bug修复：看板状态列重复

**现象**：看板上同时出现两个"📥 需求池"列、"🔧 开发中"、"🔍 审计中"、"✅ 已完成"也各自出现两次以上，共约15列。

**根因分析**（已定位）：

`app_enhanced.py` → `_get_kanban_data()` 在 Pipeline V2（2026-05-16）中已经实现了5+1列合并映射（`PIPELINE_PHASE_TO_COLUMN` + `KANBAN_STATUS`），但可能有以下残留情况：

1. **task_tracker.json 读取路径**: 代码中已有注释标记该路径"已弃用"，但未确认是否还有条件分支仍然读取。需审核 `_get_kanban_data()` 中所有数据源。
2. **后端映射双链路**: `_get_kanban_data()` 先从 `requirements.json` 读取需求，再从 `_get_active_pipelines()` 读取活跃管道。如果同一个 pipeline_id 的数据同时出现在两个数据源中（如 requirement 从老数据迁移时的 status 残留），会同一需求出现在两列中。
3. **前端渲染无去重**: `createKanbanColumn()` 直接渲染后端返回的所有列，若无 `columns` 去重逻辑，老版本前端可能渲染全部 Pipeline 阶段。

**修复方案**：

| 位置 | 改动 |
|------|------|
| `_get_kanban_data()` | 添加 `seen_ids` 集合，对已出现在 kanban_tasks 中的 pipeline_id 跳过步骤 3（active_pipelines 补充） |
| 前端 `createKanbanColumn()` | 确保不处理 `statusKey` 不在 `KANBAN_STATUS` 中的未知列（防御性编程） |

### 1.2 展示列精简：5+0（移除异常列）

**当前**：6列（需求池、设计阶段、开发阶段、验收阶段、已完成、异常）  
**目标**：5列（需求池、设计阶段、开发阶段、验收阶段、已完成）

| 看板列 | 覆盖的 Pipeline 阶段 | 变更 |
|--------|---------------------|------|
| 📥 需求池 | request + validate | ✅ 保留 |
| 🎨 设计阶段 | design + ui_design | ✅ 保留 |
| 🔧 开发阶段 | review + develop_wt + review_test + develop_code + test | ✅ 保留 |
| 🗸 验收阶段 | audit + final_check | ✅ 保留 |
| ✅ 已完成 | deliver + done | ✅ 保留 |
| ~~⚠️ 异常~~ | cancelled + timed_out + escalated | ❌ 移除 |

**异常状态处理**（折中方案）：
- 已取消（cancelled）→ 归入"已完成"列，卡片附加 `🚫 已取消` 徽标
- 超时（timed_out）→ 归入"验收阶段"列，卡片附加 `⏰ 超时` 徽标
- 升级（escalated）→ 归入"开发阶段"列，卡片附加 `🚨 已升级` 徽标
- 卡片背景色变红以视觉区分

### 1.3 卡片级内部状态显示优化

**当前**：卡片底部的 pipeline_status 文本是原始英文 phase 名（如 `develop_wt`、`review_test`）

**目标**：显示人类可读的中文内部状态名

| 内部 Phase | 卡片显示文字 |
|-----------|-------------|
| request | 待处理 |
| validate | 验证中 |
| design | 设计中 |
| ui_design | UI设计中 |
| review | 审查中 |
| develop_wt | 开发中(WT) |
| review_test | 测试审查 |
| develop_code | 编码中 |
| test | 测试中 |
| audit | 验收中 |
| final_check | 终检中 |
| deliver | 交付中 |
| done | 已完成 |
| cancelled | 已取消 |
| timed_out | 已超时 |
| escalated | 已升级 |

实现方式：后端新增 `PHASE_TO_CHINESE` 映射字典，`pipeline_status` 字段改为中文显示名，同时保留 `pipeline_status_raw` 原始值用于 debug。

### 1.4 各文件改动概要

| 文件 | 改动 |
|------|------|
| `dashboard/app_enhanced.py` | ① `KANBAN_STATUS` 移除 `exception` 列 ② `_get_kanban_data()` 添加管道去重 ③ 新增 `PHASE_TO_CHINESE` 映射 ④ 异常状态归入主列 |
| `dashboard/static/dev_center.js` | ① `createTaskCard()` 中状态显示用中文映射 ② 防御性渲染：忽略不在 KANBAN_STATUS 的列 ③ 异常卡片视觉标识 |
| `dashboard/templates/dev_center.html` | 无改动（列数由后端动态控制） |
| `dashboard/data/requirements.json` | 无改动（纯数据层无副作用） |

---

## 2. Why — 背景与原因

### 业务背景
飝龘动物园 Dashboard 是研发团队日常使用的项目管理工具，看板 Tab 展示所有需求的流转状态。用户在每天的使用中发现：

- **列太多，无法聚焦**：15+ 列挤在一起，每个列只有 0-2 个卡片，空白面积大但信息密度低
- **重复列引起疑惑**：同时看到两个"需求池"无法理解哪个是当前应该关注的
- **内部状态暴露过多**：`develop_wt`、`review_test`、`develop_code` 这些 Pipeline 内部细粒度拆分对外没有意义

### 用户实际需求
- **简化运营视图**：只关心"需求在哪条主线上"，不关心"在 Sub-phase 的哪个节点"
- **保留细节**：卡片上能看到内部阶段即可，不需要单独成列
- **不动工作流**：Pipeline 内部流程已经稳定运行，不因 UI 展示调整改变

### 为什么不直接删列
- 看板是日常操作入口，列数直接影响使用效率
- 每个 Pipeline 阶段都有其存在的意义，只是不需要同时作为列展示

---

## 3. Tradeoff — 权衡分析

### 3.1 方案对比

| 方案 | 描述 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A（采用）** | 仅改前端看板展示层，后端 Pipeline 不变 | 0 工作流风险，可快速部署 | 卡片的内部状态需额外映射 | ✅ **推荐** |
| **B** | 合并 StateMachine 中的 Pipeline 阶段 | 彻底解决列数问题 | ❌ 破坏工作流，整个 Pipeline 测试链受影响 | 不采用 |
| **C** | 前端 JS 动态合并列（不改后端） | 零后端变更 | 逻辑复杂度转移到前端；SSR/SSE 场景不一致 | 不采用 |

### 3.2 关键权衡

**1. 异常列的去留**
- **保留异常列（原始方案）**：6列，比5列多一列，但异常状态可见性好
- **移除异常列（本方案）**：5列完全对齐需求，异常状态用卡片标识替代
- **决策**：移除。5列才是用户要的，异常卡片用视觉标识更直观

**2. 卡片状态源**
- **后端映射（本方案）**：`PHASE_TO_CHINESE` 在 Python 层完成，前端只负责展示
- **前端映射**：前端维护映射表，后端不动
- **决策**：后端映射。前端已有足够复杂度（`memberEmojiMap`、SSE 等），后端控制显示更可靠

**3. 管道去重粒度**
- **pipeline_id 级别去重**：同一 pipeline_id 只在看板出现一次
- **req_id 级别去重**：更精细，但 requirement 和 pipeline 可能有独立 id
- **决策**：pipeline_id 级别。这是实际的重复源头

### 3.3 放弃的功能
- ❌ 不实现看板拖拽排序（scope 外，无此需求）
- ❌ 不实现看板自定义列（复杂度高，违背精简目标）
- ❌ 不动 Pipeline Workflow 任何代码

---

## 4. Op — 操作方案

### 4.1 实施优先级

| 优先级 | 项 | 预计工作量 |
|--------|----|-----------|
| P0 | 去重修复（`seen_ids` 过滤 + 前端防御） | 0.5h |
| P0 | 5列精简（移除 exception 列） | 0.25h |
| P0 | `PHASE_TO_CHINESE` 映射 + 卡片显示优化 | 0.5h |
| P1 | 异常卡片视觉标识（红色背景 + 徽标） | 0.5h |
| P2 | 前端样式微调（列宽自适应等） | 0.5h |

### 4.2 测试要点
1. **重复去重**：有 pipeline_id 的 requirement 不应在看板出现两次
2. **列数验证**：看板准确显示5列，无多余列
3. **异常状态**：cancelled/timed_out/escalated 的需求在正确的主列中出现
4. **卡片状态文本**：每个卡片底部的状态为中文可读文本
5. **回归**：正常流转的需求（非异常）不受影响

### 4.3 涉及文件
- `dashboard/app_enhanced.py` — 核心改动
- `dashboard/static/dev_center.js` — 前端适配
- **不涉及**: Pipeline Workflow、ZooMesh、requirements.json

---

## 5. 代码级设计详情

### 5.1 KANBAN_STATUS 修改
```python
# BEFORE
KANBAN_STATUS = {
    "request": "📥 需求池",
    "design":  "🎨 设计阶段",
    "develop": "🔧 开发阶段",
    "audit":   "🔍 验收阶段",
    "done":    "✅ 已完成",
    "exception": "⚠️ 异常",
}

# AFTER
KANBAN_STATUS = {
    "request": "📥 需求池",
    "design":  "🎨 设计阶段",
    "develop": "🔧 开发阶段",
    "audit":   "🔍 验收阶段",
    "done":    "✅ 已完成",
}
```

### 5.2 PIPELINE_PHASE_TO_COLUMN 修改
```python
# AFTER: exception 映射改为归入主列
PIPELINE_PHASE_TO_COLUMN = {
    "request":     "request",
    "validate":    "request",
    "design":      "design",
    "ui_design":   "design",
    "review":      "design",
    "develop_wt":  "develop",
    "review_test": "develop",
    "develop_code":"develop",
    "develop":     "develop",
    "test":        "develop",
    "audit":       "audit",
    "final_check": "audit",
    "deliver":     "done",
    "done":        "done",
    "cancelled":   "done",      # ← changed from exception
    "timed_out":   "audit",     # ← changed from exception
    "escalated":   "develop",   # ← changed from exception
}
```

### 5.3 PHASE_TO_CHINESE 新增
```python
PHASE_TO_CHINESE = {
    "request":      "待处理",
    "validate":     "验证中",
    "design":       "设计中",
    "ui_design":    "UI设计中",
    "review":       "审查中",
    "develop_wt":   "开发中(WT)",
    "review_test":  "测试审查",
    "develop_code": "编码中",
    "test":         "测试中",
    "audit":        "验收中",
    "final_check":  "终检中",
    "deliver":      "交付中",
    "done":         "已完成",
    "cancelled":    "🚫 已取消",
    "timed_out":    "⏰ 已超时",
    "escalated":    "🚨 已升级",
}
```

### 5.4 去重逻辑（`_get_kanban_data()` 中新增）
```python
# Step 2 中记录已覆盖的 pipeline_id
seen_pipeline_ids = set()

# 在 kanban_tasks 填充后，Step 3 之前：
if pipeline_id:
    seen_pipeline_ids.add(pipeline_id)

# Step 3 过滤
if pipeline_id in seen_pipeline_ids:
    continue  # 跳过已在 requirements 中出现的管道
```

### 5.5 异常状态在前端的视觉标识
在 `createTaskCard()` 中添加：
```javascript
// 异常状态检测
const isException = ['cancelled', 'timed_out', 'escalated'].includes(task.pipeline_status_raw);
if (isException) {
    taskCard.classList.add('task-exception');
}
```
CSS 中定义 `.task-exception` 的红色边框/背景样式。

---

## 6. 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 异常需求丢失（无列展示后找不到） | 需求被遗忘 | 低 | 卡片底部徽标 + 红色边框，仍然可见 |
| 去重过于激进（同一 pipeline 关联多 requirement） | 需求丢失显示 | 极低 | 目前 1:1 映射，无此情况 |
| 前端缓存导致未显示新列 | 用户看到旧看板 | 中 | 刷新按钮强制清缓存重新加载 |
| 映射表遗漏 phase | 卡片状态为空 | 低 | 默认 fallback 到原始值 |

---

**设计审核状态**: ✏️ 草稿，待审查  
**下一阶段**: review → develop_wt（Design Output 审核通过后推进）
