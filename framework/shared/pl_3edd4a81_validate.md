# Validate 阶段评审 — pl_3edd4a81

**需求标题**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序

**评审日期**: 2026-05-27
**评审人**: alpha 🐢

---

## 1. 可行性评估 ✅

### 1.1 问题管理页 — 完全可行
- 数据结构完备：`status` (open/in_progress/resolved/closed)、`priority` (P0/P1/P2/P3)、`resolved_at`、`updated_at`
- 当前后端已按 `updated_at` 降序排序，前端 `loadIssues()` 直接渲染
- 实现方式：前端在 `loadIssues()` 中对返回数据做二次分组排序即可

### 1.2 需求管理页 — **可行，但需扩展数据模型**
- 当前需求数据结构字段：`id, title, description, assignee, status, phase, created_at, updated_at, completed_at`
- **关键发现：需求没有 `priority` 字段**
- 如果"开启中按优先级排序"适用于需求页，则必须：
  1. 给 `requirements.json` 的数据模型添加 `priority` 字段（默认值 P3）
  2. 修改需求创建表单（`dev_center.html` + `dev_center.js`）添加优先级选择
  3. 后端 `_handle_requirements_post()` 处理并存储 priority
- 数据模型扩展属于常规增量改动，无技术障碍

---

## 2. 排序规则精确定义

### 2.1 问题管理页
| 状态分组 | 判定条件 | 排序键 | 方向 |
|---------|---------|--------|------|
| 开启中 | `status in ('open', 'in_progress')` | `priority` | P0 → P1 → P2 → P3（高→低）|
| 已解决/已关闭 | `status in ('resolved', 'closed')` | `resolved_at` 或 `updated_at` | 新→旧 |

**注**: `resolved_at` 优于 `updated_at`，因为 resolved 后可能还有后续更新（如关闭操作）。若 `resolved_at` 为空则 fallback 到 `updated_at`。

### 2.2 需求管理页
| 状态分组 | 判定条件 | 排序键 | 方向 |
|---------|---------|--------|------|
| 开启中 | `status != 'done'` | `priority`（需新增字段） | P0 → P1 → P2 → P3 |
| 已解决/已关闭 | `status == 'done'` | `completed_at` 或 `updated_at` | 新→旧 |

**注**: 需求状态 `cancelled` / `timed_out` / `escalated` 归类为"已解决/已关闭"还是"开启中"？从语义上，这些属于异常终止，建议归入"已解决/已关闭"组按时间排序。

---

## 3. 依赖项

| 依赖 | 状态 | 说明 |
|------|------|------|
| `requirements.json` 数据模型 | 需扩展 | 添加 `priority` 字段，现有数据需要默认值回填 |
| 需求创建表单 | 需扩展 | `dev_center.html` 表单加 `<select id="req-priority">` |
| 需求提交 JS | 需扩展 | `submitRequirement()` 需发送 priority |
| 后端 API (`_handle_requirements_post`) | 需扩展 | 接收并存储 priority |
| 问题数据模型 | ✅ 就绪 | 已有 `priority` / `resolved_at` |

---

## 4. 风险点 ⚠️

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| **需求模型缺 `priority` 字段** | 中 | design 阶段必须明确是否给需求加 priority；若不加，则需求页"开启中"只能按 `created_at` 排序，与需求描述有偏差 |
| **历史需求无 priority 值** | 低 | 默认值设为 P3，不破坏现有行为 |
| **排序与现有筛选器冲突** | 低 | 当前前端筛选器（status/priority/search）在 fetch 后过滤；分组排序应在过滤后执行，逻辑不冲突 |
| **跨页面一致性** | 低 | 看板页的需求卡片排序逻辑也需同步检查（`createKanbanColumn` 中的 `columnData.tasks` 顺序） |

---

## 5. 建议优先级

**P1 — 建议接受**

理由：
1. 功能需求明确，用户意图清晰（提升信息浏览效率）
2. 技术实现无硬障碍，纯前端排序即可完成 80%
3. 剩余 20%（需求 priority 字段）是常规数据模型扩展，风险可控
4. 与现有 Pipeline 阶段映射、看板逻辑无冲突

---

## 6. 实现建议（供 design 阶段参考）

### 前端排序核心逻辑（问题页示例）
```javascript
function sortIssues(issues) {
    const openStatuses = ['open', 'in_progress'];
    const closedStatuses = ['resolved', 'closed'];
    
    const openIssues = issues.filter(i => openStatuses.includes(i.status));
    const closedIssues = issues.filter(i => closedStatuses.includes(i.status));
    
    const priorityOrder = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3 };
    openIssues.sort((a, b) => (priorityOrder[a.priority] ?? 3) - (priorityOrder[b.priority] ?? 3));
    
    closedIssues.sort((a, b) => {
        const ta = a.resolved_at || a.updated_at || '';
        const tb = b.resolved_at || b.updated_at || '';
        return tb.localeCompare(ta);
    });
    
    return [...openIssues, ...closedIssues];
}
```

### 需求页排序（若加 priority）
```javascript
function sortRequirements(reqs) {
    const openReqs = reqs.filter(r => r.status !== 'done');
    const doneReqs = reqs.filter(r => r.status === 'done');
    
    const priorityOrder = { 'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3 };
    openReqs.sort((a, b) => (priorityOrder[a.priority] ?? 3) - (priorityOrder[b.priority] ?? 3));
    
    doneReqs.sort((a, b) => {
        const ta = b.completed_at || b.updated_at || '';
        const tb = a.completed_at || a.updated_at || '';
        return ta.localeCompare(tb); // 新→旧
    });
    
    return [...openReqs, ...doneReqs];
}
```

---

## 7. 结论

**评审结果: PASS ✅**

需求合理、技术可行、风险可控。建议 design 阶段明确：
1. 是否给需求模型添加 `priority` 字段（推荐添加，否则需求页"开启中"无法按优先级排序）
2. 若不加 priority，需求页"开启中"的 fallback 排序策略（建议按 `created_at` 新→旧）
