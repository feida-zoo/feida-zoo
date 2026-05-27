# UI Design — pl_3edd4a81

**需求**: 需求管理和问题管理页，已解决/已关闭按时间从新到旧，开启中按优先级从高到低排序

**日期**: 2026-05-27
**设计人**: alpha 🐢

---

## 1. 页面布局

本次改动不改变页面整体布局结构，仅在现有组件的内部做增量调整。

### 1.1 需求管理页（Tab 4）

| 区域 | 当前 | 变更 |
|------|------|------|
| 表单（左/上卡片） | title + desc + assignee + 提交按钮 | **+ priority 选择器**（description 下方） |
| 列表（右/下卡片） | `slice().reverse()` 倒序展示，无优先级信息 | **分组排序 + 优先级别名 + 优先级徽标** |

### 1.2 问题管理页（Tab 6）

| 区域 | 当前 | 变更 |
|------|------|------|
| 筛选工具栏 | status / priority / search，不变 | 不变 |
| 列表 | 后端按 updated_at 倒序，前端直接渲染 | **前端分组排序**（先 priority 后排时间） |

---

## 2. 交互逻辑

### 2.1 需求表单 — 新增优先级选择

```
用户填写需求 → 选择优先级（可选，默认 P3） → 点击提交
                                                    ↓
                                            POST /api/requirements
                                           { title, desc, assignee, priority }
                                                    ↓
                                              列表刷新 →
                                          分组排序 + 优先级别展示
```

**新增选择器位置**：`description` 字段之后，`指派给` 之前。

```
┌─ 新增需求 ─────────────────────────────────┐
│  标题  [___________________________]       │
│  描述  [___________________________]       │
│         [___________________________]       │
│  优先级  [P3 低 ▼]    ← 新增               │
│  指派给  [-- 选择成员 -- ▼]                 │
│  [📨 提交需求]                              │
└────────────────────────────────────────────┘
```

**默认值**: P3（最低优先级），用户可自行提升到 P0~P2。

### 2.2 需求列表 — 分组排序渲染

```
fetch /api/requirements
        ↓
sortRequirementsForDisplay()
  ├── 1. 过滤出开启中集 (status ∉ terminal)
  │     └── 按 priority: P0→P1→P2→P3 升序
  ├── 2. 过滤出已解决集 (status ∈ terminal)
  │     └── 按 completed_at / updated_at 降序
  └── 3. 合并: [...开启中, ...已解决]
        ↓
render(): 开启中在前 → 已解决在后
```

**关于"已解决/已关闭"分组的交互说明**：
- 开启中列表和已解决列表之间**无显式分隔线/标签头**
- 排序自然告诉用户信息层级：先看"要做的事"，再看"做过的事"
- 用户通过**状态标签**（`done`/`cancelled` 等）识别当前分组

### 2.3 问题列表 — 分组排序渲染

```
fetch /api/issues?status=&priority=&search=
        ↓
sortIssuesForDisplay()
  ├── 1. 过滤出开启中集 (open / in_progress)
  │     └── 按 priority: P0→P1→P2→P3 升序
  ├── 2. 过滤出已解决集 (resolved / closed)
  │     └── 按 resolved_at / updated_at 降序
  └── 3. 合并: [...开启中, ...已解决]
        ↓
render()
```

---

## 3. 状态定义

### 3.1 需求状态归属

| 分组 | 判定条件 | 排序键 | 方向 |
|------|---------|--------|------|
| 开启中 | `status ∉ ['done','cancelled','timed_out','escalated']` | `priority` (字段可能为空 → 按 P3 处理) | P0→P1→P2→P3 |
| 已解决/已关闭 | `status ∈ ['done','cancelled','timed_out','escalated']` | `completed_at` → `updated_at` → `created_at` fallback | 新→旧 |

### 3.2 问题状态归属

| 分组 | 判定条件 | 排序键 | 方向 |
|------|---------|--------|------|
| 开启中 | `status ∈ ['open','in_progress']` | `priority` | P0→P1→P2→P3 |
| 已解决/已关闭 | `status ∈ ['resolved','closed']` | `resolved_at` → `updated_at` fallback | 新→旧 |

### 3.3 排序稳定性

- 同 priority 的开启中项目 → 维持 API 返回顺序（即创建时间顺序，最近在先）
- 同 resolved_at 的已解决项目 → 以 `updated_at` 为第二排序键，较晚更新的排前

---

## 4. 视觉说明

### 4.1 需求表单新增的优先级选择器

**风格**：与现有表单字段（标题、描述、指派给）保持完全一致
- 使用 `.form-group` 容器
- `<select>` 元素，`.form-group select` 样式自动继承
- 选项顺序与问题表单的优先级选择器一致：`P3 低 → P2 中 → P1 高 → P0 紧急`

```html
<div class="form-group">
    <label for="req-priority">优先级</label>
    <select id="req-priority">
        <option value="P3">P3 低</option>
        <option value="P2">P2 中</option>
        <option value="P1">P1 高</option>
        <option value="P0">P0 紧急</option>
    </select>
</div>
```

**与问题表单对齐**：已知问题表单优先级 `<select>` 使用同样的选项顺序（P3→P2→P1→P0）和相同的 CSS 类。

### 4.2 需求列表新增优先级徽标

**位置**：`req-meta` 区域内，`<i class="fas fa-tag"></i>` 状态标签之前

**样式**：继承现有的 `req-meta span` 布局（flex row，gap 12px）

**颜色方案**（light theme）：

| 优先级 | 背景色 | 文字色 | 边框 |
|--------|--------|--------|------|
| P0 | `rgba(231, 76, 60, 0.1)` | `#c0392b` | `rgba(231, 76, 60, 0.3)` |
| P1 | `rgba(243, 156, 18, 0.12)` | `#d35400` | `rgba(243, 156, 18, 0.3)` |
| P2 | `rgba(241, 196, 15, 0.15)` | `#b7950b` | `rgba(241, 196, 15, 0.3)` |
| P3 | `rgba(149, 165, 166, 0.15)` | `#7f8c8d` | `rgba(149, 165, 166, 0.3)` |

**预期渲染效果**：

```
┌─ req-list-item ─────────────────────────────────────┐
│  需求标题文字                                            │
│  🔖 P0 紧急  🏷️ 验证中  👤 🐢 阿尔法  🕐 2026-05-27   │  ← 带优先级徽标
└───────────────────────────────────────────────────────┘
```

**徽标本身**（需求管理页，light theme）：
```css
.req-priority-badge {
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}

.req-priority-badge.p0  { ... }
.req-priority-badge.p1  { ... }
.req-priority-badge.p2  { ... }
.req-priority-badge.p3  { ... }
```

### 4.3 问题列表 — 无视觉变更

问题列表已有的卡片布局（`.issue-card`）和优先级左边框颜色（`.priority-p0` → `#f38ba8` 等）保持不变。分组排序仅影响渲染顺序，不影响每个卡片的外观。

### 4.4 空列表状态

当列表经过排序后为空时，现有空状态提示（"暂无需求"/"暂无问题"）保持不变。空状态出现在 sorted list 为空的场合（即没有数据），不受排序逻辑影响。

---

## 5. 组件树

```
.dev-center-container
├── header (不变)
├── nav.tab-nav (不变)
└── main.dev-center-main
    ├── #tab-requirements (需求管理)
    │   └── .requirements-container
    │       ├── .req-form-card (新增 <select>)
    │       │   ├── .form-group: 标题 (不变)
    │       │   ├── .form-group: 描述 (不变)
    │       │   ├── .form-group: 优先级 (新增)
    │       │   ├── .form-group: 指派给 (不变)
    │       │   └── .btn-submit: 提交 (不变)
    │       └── .req-list-card
    │           └── .req-list
    │               └── .req-list-item (排序变化 + 新增徽标)
    │                   ├── .req-title (不变)
    │                   └── .req-meta
    │                       ├── .req-priority-badge (新增)
    │                       ├── .req-status-badge (不变)
    │                       ├── .req-assignee (不变)
    │                       └── .req-time (不变)
    │
    ├── #tab-issues (问题管理)
    │   └── .issues-container
    │       ├── .issues-header (不变)
    │       ├── .issues-toolbar (不变)
    │       └── .issues-list (排序变化)
    │           └── .issue-card (不变)
    │
    └── ...其他 tab (不变)
```

---

## 6. CSS 新增样式

新增约 20 行 CSS 到 `dev_center.css`，用于需求列表的优先级徽标：

```css
/* 需求管理页 - 优先级徽标 */
.req-priority-badge {
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
}
.req-priority-badge.p0 {
    background: rgba(231, 76, 60, 0.1);
    color: #c0392b;
    border: 1px solid rgba(231, 76, 60, 0.3);
}
.req-priority-badge.p1 {
    background: rgba(243, 156, 18, 0.12);
    color: #d35400;
    border: 1px solid rgba(243, 156, 18, 0.3);
}
.req-priority-badge.p2 {
    background: rgba(241, 196, 15, 0.15);
    color: #b7950b;
    border: 1px solid rgba(241, 196, 15, 0.3);
}
.req-priority-badge.p3 {
    background: rgba(149, 165, 166, 0.15);
    color: #7f8c8d;
    border: 1px solid rgba(149, 165, 166, 0.3);
}
```

**不变的内容**：`.req-list-item` 的 padding/border/hover、`.req-meta` 的 flex 布局、`.req-status-badge` 的全部状态样式。

---

## 7. 交互流程总结

```
[用户打开需求管理页]
    ↓
loadRequirementsList()
    ↓
fetch /api/requirements
    ↓
sortRequirementsForDisplay()
    ├─ 开启中: 按 P0→P1→P2→P3
    └─ 已解决: 按 completed_at 新→旧
    ↓
render: 开启中在前, 已解决在后, 每项附加优先级徽标

[用户打开问题管理页]
    ↓
loadIssues()
    ↓
fetch /api/issues?filters
    ↓
sortIssuesForDisplay()
    ├─ 开启中: 按 P0→P1→P2→P3
    └─ 已解决: 按 resolved_at 新→旧
    ↓
render: 开启中在前, 已解决在后
```

**新建需求后的刷新流**：
```
submitRequirement()
  → POST /api/requirements { ..., priority }
  → loadRequirementsList()    ← 自动按优先级和时间排序
  → ZooDevCenter.loadKanbanData()
```

---

## 8. 完成后确认

| 检查点 | 预期 |
|--------|------|
| 需求表单优先级选择器可见 | 在描述下方、指派给上方，默认 P3 |
| 需求列表开启中排在前 | status 非 terminal 的全部排在 terminal 前面 |
| 需求列表开启中按 priority 升序 | P0 → P1 → P2 → P3 |
| 需求列表已解决按 completed_at 降序 | 最新完成的排最上方 |
| 需求列表新增优先级徽标 | light theme 色系，与状态徽标一致 |
| 问题列表开启中按 priority 升序 | P0 → P1 → P2 → P3 |
| 问题列表已解决按 resolved_at 降序 | 最新解决的排最上方 |
| 筛选器与排序不冲突 | 先筛选后排序，筛选结果内部仍分组排序 |
| 看板页不受影响 | 看板 Tab 排序逻辑不变 |
