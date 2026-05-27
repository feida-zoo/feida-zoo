# Design 阶段 — pl_3edd4a81

**需求**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序

**设计日期**: 2026-05-27
**设计人**: alpha 🐢

---

## 1. What — 具体改动

### 1.1 功能概述

在「需求管理」和「问题管理」两个页面上引入**分组排序**：
1. 将列表拆为上下两组 — **开启中（优先级排序）** + **已解决/已关闭（时间倒序）**
2. 需求页面新增**优先级字段**（数据模型 + 表单 + 展示）

### 1.2 改动粒度

| # | 改动点 | 文件 | 类型 |
|---|--------|------|------|
| 1 | 需求表单添加优先级选择器 | `dev_center.html` | HTML |
| 2 | `submitRequirement()` 发送 priority | `dev_center.js` | JS |
| 3 | `_handle_requirements_post()` 接收 priority | `app_enhanced.py` | Python |
| 4 | `loadRequirementsList()` 分组排序 + 展示优先级 | `dev_center.js` | JS |
| 5 | `loadIssues()` 分组排序 | `dev_center.js` | JS |
| 6 | `_handle_issues_get()` 移除后端排序 | `app_enhanced.py` | Python |

共计 **6 处改动**，无新增文件，无架构层改动。

---

## 2. Why — 背景与解决的问题

### 2.1 现状
- **需求管理页**：通过 `reqs.slice().reverse()` 展示，按 `created_at` 倒序
- **问题管理页**：后端按 `updated_at` 倒序返回，前端原样渲染
- 两个页面均混排开启中和已关闭的项目，**用户难以快速定位高优先级待办**

### 2.2 解决的问题
1. **信息层级模糊**：一个刚解决的 P3 问题排在最前，P0 待办却沉在列表底部
2. **效率浪费**：每次需要人为扫描整个列表找未完成的高优项
3. **需求录入缺失**：现有需求表单没有优先级字段，这是一个已存在的功能缺口

---

## 3. Tradeoff — 方案取舍

### 3.1 前端排序 vs 后端排序

| 维度 | 前端排序 (选中) | 后端排序 |
|------|----------------|---------|
| 实现代价 | 低（纯 JS 改动） | 中（需重构 API 返回结构） |
| 排序可控性 | ✅ 灵活，不受 API 改变影响 | ⚠️ 需要扩接口传递排序参数 |
| 代码可读性 | ✅ 分组逻辑在渲染前集中处理 | 需要配合筛选参数 |
| 性能 | 批量数据小（<200 条），无差异 | 无差异 |

**结论**：前端排序更简单可控，当前数据规模下性能无影响。

### 3.2 分组展示 vs 混排 + 标记

- **分组展示（选中）**：开启中在上方，已解决在下方，中间无分隔
- **混排 + 标签**：全部混在一起，仅靠状态标签区分
- **理由**：分组是更直接的信息架构——用户先关注"还要做什么"，再看"做过什么"。与 validate 建议一致。

### 3.3 给需求添加 priority vs 不添加

- **添加（选中）**：数据模型扩展，需求页可参与按优先级排序
- **不添加**：需求页"开启中"只能按创建时间排序，**与需求描述矛盾**
- **默认值**：P3，现有历史数据自动归入最低档，不破坏已有体验

### 3.4 需求终端状态归属

- `done` / `cancelled` / `timed_out` / `escalated` 均归入"已解决/已关闭"组
- `done` 按 `completed_at` 排序，其余终端状态按 `updated_at` 排序
- 不进行二次细分，保持分组语义统一

---

## 4. 接口定义

### 4.1 后端: `POST /api/requirements` — 新增字段

```python
# 当前请求体
{
    "title": "string (required)",
    "description": "string (optional)",
    "assignee": "string (optional)"
}

# 新请求体（增加 priority）
{
    "title": "string (required)",
    "description": "string (optional)",
    "assignee": "string (optional)",
    "priority": "string (optional, default 'P3')"  # P0|P1|P2|P3
}
```

`_handle_requirements_post()` 改动：读取 `priority` 字段，写入 requirement 字典。

### 4.2 后端: `GET /api/issues` — 移除后端排序

```python
# 当前
issues.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

# 改为（删除该行）
# 排序交由前端统一处理
```

改动位置：`_handle_issues_get()` 末尾。

### 4.3 前端: 分组排序函数

```javascript
// 问题分组排序
function sortIssuesForDisplay(issues) {
    const PRORITY_ORDER = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3 };
    const open = issues.filter(i => ['open', 'in_progress'].includes(i.status));
    const closed = issues.filter(i => ['resolved', 'closed'].includes(i.status));
    
    open.sort((a, b) => (PRORITY_ORDER[a.priority] ?? 3) - (PRORITY_ORDER[b.priority] ?? 3));
    closed.sort((a, b) => {
        const ta = a.resolved_at || a.updated_at || '';
        const tb = b.resolved_at || b.updated_at || '';
        return tb.localeCompare(ta);  // 新→旧
    });
    
    return [...open, ...closed];
}

// 需求分组排序
function sortRequirementsForDisplay(reqs) {
    const TERMINAL_STATUS = ['done', 'cancelled', 'timed_out', 'escalated'];
    const PRORITY_ORDER = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3 };
    
    const open = reqs.filter(r => !TERMINAL_STATUS.includes(r.status));
    const closed = reqs.filter(r => TERMINAL_STATUS.includes(r.status));
    
    open.sort((a, b) => (PRORITY_ORDER[a.priority] ?? 3) - (PRORITY_ORDER[b.priority] ?? 3));
    closed.sort((a, b) => {
        const ta = a.completed_at || a.updated_at || '';
        const tb = b.completed_at || b.updated_at || '';
        return tb.localeCompare(ta);  // 新→旧
    });
    
    return [...open, ...closed];
}
```

### 4.4 前端: `submitRequirement()` — 发送 priority

```javascript
// 新增读取优先级选择器
const priority = document.getElementById('req-priority');

fetch('/api/requirements', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        title: title.value.trim(),
        description: desc ? desc.value.trim() : '',
        assignee: assignee ? assignee.value : '',
        priority: priority ? priority.value : 'P3'  // 新增
    })
})
```

### 4.5 需求列表渲染 — 新增优先级展示

```javascript
// 在 req-meta 区域增加优先级标注
const priorityLabels = { 'P0': 'P0 紧急', 'P1': 'P1 高', 'P2': 'P2 中', 'P3': 'P3 低' };
const priorityClasses = { 'P0': 'p0', 'P1': 'p1', 'P2': 'p2', 'P3': 'p3' };

// 在 req-list-item 的 meta 部分新增
`<span><i class="fas fa-flag"></i> <span class="req-priority-badge ${priorityClasses[r.priority] || 'p3'}">${priorityLabels[r.priority] || 'P3'}</span></span>`
```

---

## 5. 文件清单

| 文件 | 操作 | 改动内容 |
|------|------|----------|
| `dashboard/templates/dev_center.html` | 🔧 修改 | 需求表单新增 `<select id="req-priority">`（4 个 option: P0~P3，默认 P3） |
| `dashboard/static/dev_center.js` | 🔧 修改 | ① `submitRequirement()` 读取并发送 priority ② `loadRequirementsList()` 分组排序 + 优先级别展示 ③ `loadIssues()` 分组排序 |
| `dashboard/app_enhanced.py` | 🔧 修改 | ① `_handle_requirements_post()` 接收 priority ② `_handle_issues_get()` 移除后端排序行 |
| `dashboard/data/requirements.json` | 🔄 自动 | 新创建的需求自动写入 priority 字段，旧数据保留无 priority |

**无新增文件**，全部在现有文件上增量修改。

---

## 6. Open Questions

| # | 问题 | 决策 | 理由 |
|---|------|------|------|
| **已关闭** | 需求是否要加 priority？ | ✅ **加** | 否则需求页无法按优先级排序，与需求矛盾 |
| **已关闭** | 需求终端状态如何归类？ | ✅ 全归入"已解决/已关闭" | `done/cancelled/timed_out/escalated` 都不再需要操作 |
| **已关闭** | 排序位置：前端还是后端？ | ✅ **前端** | 纯展示层逻辑，后端不关心里 |
| **已关闭** | 历史需求无 priority 怎么处理？ | ✅ 默认 P3 | 不影响原有排序行为 |
| **已关闭** | 需求列表需要显示优先级吗？ | ✅ **显示** | 否则开启中排序后用户看不到排序依据 |
| **已关闭** | 看板页是否需要同步改？ | ❌ **不变** | 看板是独立视图，需求仅针对需求/问题管理列表页 |
| ❓ | 问题管理页筛选器+排序的交互顺序？ | ✅ 先筛选后排序 | 筛选器缩小范围后，在结果集内分组排序 |

---

## 7. Next Action — 希望审查方重点关注

1. **分组语义校验**：开启中/已解决的判定条件是否覆盖全面，无漏判/错判
2. **终端状态完整覆盖**：需求状态列表（request→deliver→done/cancelled/timed_out/escalated）中终端态的判定
3. **历史数据兼容**：旧需求无 priority，按 P3 处理是否合理；旧问题的 resolved_at 可能为空是否已兜底
4. **筛选与排序不冲突**：筛选器过滤后，排序逻辑在过滤结果上执行，不互相干扰
5. **表单优先级选项顺序**：问题表单用 `P3→P2→P1→P0`（低→高），需求表单建议保持一致

---

## 8. 里程碑

| 阶段 | 产出 | 预估工时 |
|------|------|---------|
| develop | 6 处改动实现 + `requirements.json` 历史数据 priority 默认值回填脚本 | 1 次 Claude Code 会话 |
| test | 验证分组排序正确性 + 筛选不冲突 + 历史数据兼容 | 15~30 分钟 |
