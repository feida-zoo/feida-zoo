# 🐢 看板优化 — UI/UX 设计

**Pipeline**: pl_cc412a3a  
**需求ID**: cc412a3a-583f-4553-b8e6-dbc7df83e3c4  
**设计时间**: 2026-05-17  
**作者**: Alpha 🐢  
**前置**: 设计文档 → `design/pl_cc412a3a_kanban_optimization.md`

---

## 1. 看板列布局

### 1.1 列数变更

| 项目 | 当前 (6列) | 目标 (5列) |
|------|-----------|-----------|
| 列数 | 6列（含异常列） | 5列 |
| Grid 布局 | `repeat(6, 1fr)` | `repeat(5, 1fr)` |
| 列宽占比 | 每列 ~16.6% | 每列 ~20% |

### 1.2 5列视觉层次

| 列 | CSS Class | 背景色 | Emoji | 用于 |
|----|-----------|--------|-------|------|
| 📥 需求池 | `kanban-column.request` | `var(--backlog-color)` (浅蓝) | 📥 | request + validate |
| 🎨 设计阶段 | `kanban-column.design` | `var(--design-color)` (粉紫) | 🎨 | design + ui_design + review |
| 🔧 开发阶段 | `kanban-column.develop` | `var(--develop-color)` (浅黄/橙) | 🔧 | develop_wt + review_test + develop_code + test |
| 🗸 验收阶段 | `kanban-column.audit` | `var(--audit-color)` (浅绿) | 🗸 | audit + final_check |
| ✅ 已完成 | `kanban-column.done` | `var(--done-color)` (灰色底+绿) | ✅ | deliver + done + cancelled |

### 1.3 移动端适配

当前无断点媒体查询，移动端看板水平滚动。
5列后列宽增加，水平滚动体验改善（列内容更宽，卡片不拥挤）。

---

## 2. 卡片视觉设计

### 2.1 卡片结构（自上而下）

```
┌─────────────────────────────────────┐
│ task-id           severity badge     │  ← 需求ID + P0/P1/P2/P3
│─────────────────────────────────────│
│ 任务标题文本                          │  ← 一至两行，overflow: ellipsis
│─────────────────────────────────────│
│ 🐢 责任人       🔧 编码中            │  ← Emoji + 人名 | Phase中文
└─────────────────────────────────────┘
         ↑ 左侧4px severity 色条
```

### 2.2 已有样式（不变部分）

| 元素 | 样式 | 来源 |
|------|------|------|
| 卡片白色背景 + 阴影 | `background: white; box-shadow` | 已有 `.task-card` |
| 左侧色条 | `border-left: 4px solid ...` | 已有 `.severity-p0~p3` |
| 悬浮效果 | `transform: translateX(5px)` | 已有 `.task-card:hover` |

### 2.3 新增样式

#### 异常状态卡片 (`task-exception`)

```css
.task-card.task-exception {
    border-left-color: #e74c3c !important;   /* 红色覆盖 severity 色条 */
    background: #fdf2f2;                      /* 浅红底色 */
}
.task-card.task-exception:hover {
    box-shadow: 0 3px 10px rgba(231, 76, 60, 0.3);
}
```

#### 异常状态徽标

卡片底部的 `task-phase` 位置显示对应 Emoji + 中文：

| 原始 Pipeline 阶段 | 卡片显示 | 颜色 |
|-------------------|---------|------|
| cancelled | 🚫 已取消 | #e74c3c |
| timed_out | ⏰ 已超时 | #f39c12 |
| escalated | 🚨 已升级 | #e74c3c |

```css
.task-phase-exception {
    background: #fce4ec;
    color: #c0392b;
    font-weight: 600;
}
```

---

## 3. 列标题变更

### 3.1 当前
```
📥 需求池  🎨 设计阶段  🔧 开发阶段  🔍 审计中  ✅ 已完成  ⚠️ 异常
```

### 3.2 目标
```
📥 需求池  🎨 设计阶段  🔧 开发阶段  🗸 验收阶段  ✅ 已完成
```

> "审计中" → "验收阶段"（与需求描述保持一致）
> "⚠️ 异常" → 移除，异常归入主列

### 3.3 列标题属性

列标题显示任务计数：
```
📥 需求池  [5]    🎨 设计阶段  [2]    🔧 开发阶段  [3]    🗸 验收阶段  [1]    ✅ 已完成  [8]
```

当前这个功能已经存在（`task-count`），无需改动。

---

## 4. 交互行为

### 4.1 卡片点击

**行为不变**：点击卡片弹出详情弹窗（`showTaskDetail()`），展示完整信息。
在详情弹窗中，需要新增「内部 Pipeline 阶段」字段展示。

### 4.2 刷新

**行为不变**：刷新按钮强制从后端重新拉取看板数据。

### 4.3 异常卡片交互

异常卡片点击同样弹出详情，但左上角增加 ⚠️ 异常状态横幅。

---

## 5. 响应式行为

当前 CSS 对联不支持 `<script>` 标签内 breakpoint，后续可考虑添加媒体查询：

```css
@media (max-width: 1200px) {
    .kanban-columns {
        grid-template-columns: repeat(3, 1fr); /* 小屏改为3列 */
    }
}
@media (max-width: 768px) {
    .kanban-columns {
        grid-template-columns: repeat(2, 1fr);
        overflow-x: auto;
    }
}
```

> **注**：此优化为 Nice-to-have，不在本次 P0 范围内。

---

## 6. 改动点汇总

| # | 文件 | 修改内容 | 类型 |
|---|------|---------|------|
| 1 | `dev_center.css` | `.kanban-columns` grid → `repeat(5, 1fr)` | CSS |
| 2 | `dev_center.css` | 移除 `.kanban-column.exception` 块 | CSS |
| 3 | `dev_center.css` | 新增 `.task-exception` 卡片样式 | CSS |
| 4 | `dev_center.css` | 新增 `.task-phase-exception` 徽标样式 | CSS |
| 5 | `dev_center.css` | 可选：`ui-design` 列样式删除（不再独立） | CSS |
| 6 | `app_enhanced.py` | `KANBAN_STATUS` 移除 exception 列 | Python |
| 7 | `app_enhanced.py` | `PIPELINE_PHASE_TO_COLUMN` mapped exception phases to main columns | Python |
| 8 | `app_enhanced.py` | 新增 `PHASE_TO_CHINESE` 映射 | Python |
| 9 | `app_enhanced.py` | 在看板数据结构中添加 `pipeline_status_raw` | Python |
| 10 | `app_enhanced.py` | `_get_kanban_data()` 去重逻辑 | Python |
| 11 | `dev_center.js` | `createTaskCard()` 异常检测 + CSS class 添加 | JS |
| 12 | `dev_center.js` | 防御性渲染：忽略未知列 | JS |

---

## 7. 视觉效果预期

### 7.1 Before（用户看到的15+列）
```
📥 需求池 | 📥 需求池 | 🎨 设计阶段 | 🔧 开发中 | 🔧 开发中 | ...（重复+零散）
[空]      | [空]      | [1个卡]     | [空]      | [1个卡]    | ...
```

### 7.2 After（5列精简）
```
📥 需求池   🎨 设计阶段   🔧 开发阶段   🗸 验收阶段   ✅ 已完成
[需求A]     [需求C]       [需求D]       [需求E]       [需求F]
[需求B]     ──────        ──────        ──────        [🚫已取消需求G]
            ↑ 空列不占          ↑ 卡片底部显示中文 phase
              视觉空间              "审查中" / "编码中"
```

---

## 8. 验收标准

| # | 验收项 | 测试方法 |
|---|-------|---------|
| 1 | 看板准确显示5列，无第6列 | 进入看板 Tab 目视检查 |
| 2 | 列标题正确：需求池/设计阶段/开发阶段/验收阶段/已完成 | 目视检查 |
| 3 | 无重复的列 | 对比看板列和 requirements.json 数据 |
| 4 | 异常状态卡片（cancelled/timed_out/escalated）出现在正确列中 | 目视检查 + 点击查看详情 |
| 5 | 异常卡片有红色边框/浅红底色 | 目视检查 |
| 6 | 卡片底部显示中文阶段名 | 目视检查 |
| 7 | 刷新按钮正常刷新 | 点击测试 |
| 8 | 同一个 pipeline_id 的任务不重复出现 | 对比后端响应 JSON |

---

**设计审核状态**: ✏️ 草稿，待审查  
**下一阶段**: review → develop_wt（UI 设计输出审核通过后推进）
