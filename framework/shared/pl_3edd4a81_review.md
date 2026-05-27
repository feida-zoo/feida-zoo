# Review 阶段 — pl_3edd4a81

**需求**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序
**审查日期**: 2026-05-27
**审查人**: duci 🦂

---

## 1. 架构合理性

### ✅ 前端排序方案合理

数据量小（需求 <20 条，问题 <15 条），前端排序无性能问题，逻辑集中在渲染层更清晰。设计选型正确。

### ✅ 分组策略合理

开启中在上、已关闭在下，符合"先关注待办"的用户心智模型。终端状态统一归入一组，不二次细分，简洁。

### ⚠️ 后端移除排序需谨慎

设计提出删除 `_handle_issues_get()` 中的 `issues.sort()` 行。**如果其他调用方依赖该 API 的有序返回**（如脚本、看板数据源），移除后端排序会破坏下游行为。经查看 `loadIssues()` 是该 API 的唯一前端消费者，看板走独立数据路径，所以**移除是安全的**。但应在实现时加注释说明理由。

## 2. 安全风险

### ✅ 无注入风险

`priority` 字段值为固定枚举 `P0|P1|P2|P3`，后端应做白名单校验。设计中未明确后端校验逻辑——**当前 `_handle_requirements_post()` 直接从 `data.get('priority')` 写入，无校验**。

**风险等级**: 低。数据写入 JSON 文件，不涉及 SQL/命令注入，但恶意值会导致前端排序混乱或展示异常。

**建议**: 后端接收 priority 时加上枚举校验，非 P0-P3 则默认 P3。

### ✅ 无权限风险

排序逻辑纯前端展示层，不影响数据写操作权限。

## 3. 遗漏检查

### 🔴 严重遗漏：`_handle_requirements_post()` 未接收 priority 字段

**现状**: 后端 `_handle_requirements_post()` 构建的 `requirement` 字典中没有 `priority` 字段。设计文档声称要修改此处，但**当前代码完全没有 `priority` 的读取和写入逻辑**。

这意味着即使前端表单加了选择器并发送 priority，后端也会直接丢弃该字段。需求永远不会有 priority，前端排序函数拿到 `undefined`。

**结论**: 这正是待实现的设计内容，不是遗漏——但实现时必须确保后端同步改动。

### 🟡 遗漏：需求列表渲染未展示 priority

当前 `loadRequirementsList()` 的渲染模板中没有优先级 badge，设计中提到要加但**未给出完整的渲染代码**（4.5 节只给了片段）。实现时需补齐。

### 🟡 遗漏：历史需求数据无 priority

当前所有 requirements.json 中的条目都没有 `priority` 字段。设计说"默认 P3"，但需确认：
- 前端排序函数中 `?? 3` 可兜底 ✅
- 渲染时 `priorityLabels[r.priority] || 'P3'` 可兜底 ✅
- **但已关闭的 done 状态需求全部会进入"已关闭"组并按 `completed_at` 排序**，因为它们没有 priority 也不会影响已关闭组的排序逻辑，所以实际无影响 ✅

### 🟡 遗漏：需求表单 HTML 中无 priority 选择器

当前 `dev_center.html` 需求表单只有 title/desc/assignee 三个字段，缺少 `req-priority` 选择器。这是待实现项，设计已覆盖。

### 🟡 遗漏：需求列表的筛选器交互

问题管理页有 status/priority/search 三个筛选器，筛选后排序。需求管理页当前**没有筛选器**。设计中未提及需求页是否需要增加筛选器，但这不是当前需求要求的，可后续迭代。

### 🟢 小问题：`loadIssues()` 中 `in_progress` 状态未出现

设计中 `sortIssuesForDisplay` 将 `['open', 'in_progress']` 归为开启中，但当前数据中只有 `open` 和 `resolved` 状态。逻辑上没错，`in_progress` 是问题流转的中间态，保留是对的。

### 🟢 小问题：需求终端状态 `escalated` 从未出现过

当前数据只有 `done` 和 `test` 状态，`cancelled/timed_out/escalated` 从未使用。但设计中保留它们作为终端态是合理的防御性编程。

## 4. 改进建议

### 建议 1：后端 priority 校验（必须）

```python
VALID_PRIORITIES = {'P0', 'P1', 'P2', 'P3'}
priority = (data.get('priority') or 'P3').upper()
if priority not in VALID_PRIORITIES:
    priority = 'P3'
```

### 建议 2：排序函数可复用

`sortIssuesForDisplay` 和 `sortRequirementsForDisplay` 结构高度相似，可抽取公共的分组排序函数，减少重复代码。但考虑到两个实体的状态集和排序时间字段不同，分开写也可接受。**非阻塞**。

### 建议 3：已关闭组排序时间字段应统一

设计中已关闭需求按 `completed_at || updated_at` 排序，已关闭问题按 `resolved_at || updated_at` 排序。逻辑正确但字段不一致，实现时需仔细区分。建议代码中加注释说明。

### 建议 4：前后端排序共存期的过渡

移除后端排序后，如果页面刷新时数据闪烁（先无序后排序），可在 `loadIssues()` 中先隐藏列表、排序后再渲染。当前实现已有 loading 态，问题不大。

## 5. 结论

**pass** ✅

设计整体合理，覆盖了需求的所有要点。识别出的遗漏和风险均为实现层面的问题，不影响设计通过：

1. 后端 priority 校验是必须加的，但不影响设计方向
2. 历史数据兼容方案可行（默认 P3 兜底）
3. 移除后端排序无下游破坏风险
4. 分组策略和排序逻辑正确

设计无架构缺陷、无安全硬伤、无逻辑矛盾。实现时注意上述改进建议即可。
