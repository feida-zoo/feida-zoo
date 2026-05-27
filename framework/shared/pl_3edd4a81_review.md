# Review 阶段审查报告 — pl_3edd4a81

**需求标题**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序

**审查日期**: 2026-05-27
**审查人**: 毒刺 🦂

---

## 1. 架构合理性

### 1.1 排序策略：前端 vs 后端

**当前后端排序**（`app_enhanced.py:897`）：
```python
issues.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
```
后端对所有 issues 做统一 `updated_at` 降序，无分组排序逻辑。

**当前前端排序**（`dev_center.js:1560`）：
```javascript
reqs.slice().reverse().map(r => ...)
```
需求列表直接 `.reverse()`，即按 JSON 数组顺序的逆序渲染，无任何语义排序。

**评审结论**：排序逻辑应放在**后端**。理由：
1. 前端排序意味着每次打开页面都要对全量数据做客户端分组排序，数据量增长后影响体验
2. 后端排序保证 API 返回即有序，前端无需关心排序策略，且支持未来分页
3. 问题管理页当前筛选器（status/priority/search）已是后端过滤，排序放在后端逻辑更一致

### 1.2 分组-排序模型

validate 阶段提出的分组-排序模型合理：

| 页面 | 分组 | 排序键 |
|------|------|--------|
| 问题管理 | open/in_progress → priority asc; resolved/closed → resolved_at desc | ✅ |
| 需求管理 | 非done → priority asc; done/cancelled/timed_out/escalated → completed_at desc | ⚠️ 见下文 |

**问题**：需求管理页"开启中"按 priority 排序，但 `requirements.json` 数据模型**没有 priority 字段**。这是核心架构缺口。

---

## 2. 安全风险

| 风险 | 等级 | 说明 |
|------|------|------|
| 后端排序 SQL/NoSQL 注入 | 无 | 当前为 JSON 文件存储，不涉及查询注入 |
| 前端 XSS via priority 值 | 低 | `loadIssues()` 中 priority 用于构建 class 名 (`priority-${issue.priority}`) 和 innerHTML 文本，但有 `escapeHtml` 保护文本部分；class 名部分若 priority 含特殊字符可破坏 HTML 结构，但现有 `priorityClasses` 映射会 fallback 到 `'p3'`，风险可控 |
| 需求 priority 字段注入 | 低 | 新增 priority 字段需做白名单校验（仅允许 P0/P1/P2/P3），当前 issue 的 priority 处理已有 `.upper()` 但无白名单校验 |

---

## 3. 遗漏检查

### 3.1 🔴 关键遗漏：需求数据模型缺 `priority` 字段

当前 `requirements.json` 的字段：`id, title, description, assignee, status, phase, created_at, pipeline_id, source, updated_at, completed_at`

**无 `priority` 字段**。需求管理页要实现"开启中按优先级排序"，必须先有 priority。

涉及改动：
1. `_handle_requirements_post()` — 新建需求时接受并存储 priority
2. `dev_center.html` — 需求创建表单加 `<select id="req-priority">`
3. `dev_center.js` — `submitRequirement()` 发送 priority
4. 历史数据回填 — 16 条现有需求全部缺 priority，需默认 P3

### 3.2 🟡 中等遗漏：需求异常终止状态归类未确认

需求状态包括 `cancelled`、`timed_out`、`escalated`。这些属于"开启中"还是"已关闭"？

从语义看：`cancelled`/`timed_out`/`escalated` 都是非活跃状态，用户不会继续处理，应归入"已关闭"组按时间排序。但需求描述原文仅提"已解决或已关闭"，未明确这些状态。

### 3.3 🟡 中等遗漏：看板页排序未提及

`_get_kanban_data()` 中 `createKanbanColumn` 的卡片排序逻辑也受影响。需求描述虽仅提"需求管理页"和"问题管理页"，但看板页的同源数据排序应保持一致，否则用户体验割裂。

### 3.4 🟢 低遗漏：后端 `_handle_issues_put()` 未设置 `closed_at`

当 issue 状态变为 `closed` 时，仅设置 `updated_at`，无 `closed_at` 字段。当前排序用 `resolved_at` fallback `updated_at`，但若 resolved→closed 之间有更新，`resolved_at` 不变而 `updated_at` 变化，用 `resolved_at` 排序逻辑正确。此处不是问题，但 `closed_at` 缺失意味着未来按关闭时间统计会不准确。

### 3.5 🟢 低遗漏：前端排序与筛选器交互

当用户选择 status 筛选器（如只看 "open"），排序逻辑仍应生效。validate 阶段已提到"分组排序应在过滤后执行"——若排序移到后端，则后端先过滤再排序，逻辑自然正确；若留前端，需确保排序在筛选后执行。

---

## 4. 改进建议

### 4.1 排序移至后端（P0 必须做）

在 `app_enhanced.py` 的 `_handle_issues_get()` 和 `_get_requirements()` 中实现分组排序，替换当前单一排序。前端仅渲染。

### 4.2 需求模型添加 priority（P0 必须做）

- 数据模型加 `priority` 字段，默认 `P3`
- 表单加优先级选择
- 后端 POST 处理加 priority
- 白名单校验：仅接受 P0/P1/P2/P3

### 4.3 异常终止状态归类（P1 建议做）

明确定义 `cancelled`/`timed_out`/`escalated` 归入"已关闭"组，与 `done` 同组按时间降序排列。

### 4.4 看板页排序同步（P1 建议做）

看板页同一列内的卡片排序逻辑应与管理页一致：活跃项按优先级，已完成按时间。

### 4.5 前端 `.reverse()` 移除（P0 必须做）

`loadRequirementsList()` 中 `reqs.slice().reverse()` 是无语义的 hack，排序后端化后应移除。

---

## 5. 结论

**REJECT ❌**

原因：

1. **核心数据模型缺失**：需求无 `priority` 字段，无法实现"开启中按优先级排序"。这不是实现细节，是功能前提不成立。
2. **排序位置未确定**：validate 阶段建议前端排序，但从架构合理性看应后端排序。design 阶段必须明确，不应留模糊空间。
3. **异常状态归类未定义**：`cancelled`/`timed_out`/`escalated` 属开启还是关闭，直接影响排序逻辑，不能实现时再定。

**建议**：design 阶段必须产出：
- 需求 priority 字段的完整数据模型变更方案
- 后端分组排序的精确算法（含异常状态归类）
- 看板页是否同步改动的明确决策
