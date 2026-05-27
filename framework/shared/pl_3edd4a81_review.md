# Review 阶段审查报告 — pl_3edd4a81

**需求标题**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序

**审查日期**: 2026-05-27
**审查人**: 毒刺 🦂

---

## 0. 上次 REJECT 回溯

上次审查基于 validate 文件（design 尚不存在），三个 REJECT 理由：

| # | 原因 | Design 回应 | 本次判定 |
|---|------|------------|---------|
| 1 | 需求数据模型缺 priority 字段 | ✅ §3.3 明确添加 priority，默认 P3，含表单/后端/展示全链路 | 已闭环 |
| 2 | 排序位置未定（前端 vs 后端） | ✅ §3.1 选定前端排序，给出取舍分析 | 已闭环，见 §1.1 保留意见 |
| 3 | 异常状态归类未定义 | ✅ §3.4 明确 done/cancelled/timed_out/escalated 均归入"已关闭"组 | 已闭环 |

三个核心阻塞点全部回应，本次审查重点转向设计细节。

---

## 1. 架构合理性

### 1.1 前端排序选择 — 可接受，但有保留意见

Design §3.1 选择前端排序，理由是"纯展示层逻辑，实现代价低，数据量小无差异"。

**认可部分**：
- 当前数据规模（issues <50, requirements=16）前端排序确实无性能差异
- 前端排序改动范围最小，6 处改动全部在现有文件内

**保留意见**：
- `_handle_issues_get()` 移除后端排序行意味着 API 返回顺序变为**无保证**（JSON 文件读取顺序 = 插入顺序，即 created_at 升序）。前端需要处理这个隐含变化
- 后端筛选器（status/priority/search）仍在运行，返回数据已经过后端过滤。排序和过滤的职责被拆分到两端，增加了认知成本
- 若未来加排序参数（如用户想切"按创建时间"排序），后端排序更易扩展

**结论**：当前可接受，但建议在代码注释中标记 `TODO: 考虑后端排序` 以备扩展。

### 1.2 分组模型 — 合理

两组模型（开启中按 priority / 已关闭按时间倒序）与用户心智模型一致：先看要做什么（按紧急度），再看做完了什么（按时间线）。

### 1.3 终端状态归一 — 合理

`cancelled`/`timed_out`/`escalated` 归入"已关闭"组。语义正确——这些状态不再需要人工操作，与 `done` 同组展示合理。

---

## 2. 安全风险

| 风险 | 等级 | 审查细节 |
|------|------|----------|
| Priority 值注入 | 中 | Design §4.1 定义 priority 为 `P0\|P1\|P2\|P3`，但 `_handle_requirements_post()` **未提白名单校验**。当前 issue 创建仅做 `.upper()`，攻击者可提交 `priority: "../../etc"` 虽不造成 XSS（前端有映射 fallback），但会污染数据。**必须加白名单校验** |
| 前端 XSS via priority | 低 | Design §4.5 的渲染代码 `priority-${priorityClasses[r.priority] \|\| 'p3'}` 中 class 名构建：若 priority 为非法值，`priorityClasses` 映射返回 `undefined`，fallback `'p3'` 生效。文本部分 `${priorityLabels[r.priority] \|\| 'P3'}` 同理。安全 |
| 数据完整性 | 低 | 移除后端排序行不影响数据完整性，仅影响返回顺序 |

---

## 3. 遗漏检查

### 3.1 🔴 必须修：后端 priority 白名单校验缺失

Design 定义了接口 `priority: "string (optional, default 'P3')  # P0|P1|P2|P3"`，但**未在代码中体现白名单校验**。

`_handle_requirements_post()` 应增加：
```python
priority = (data.get('priority') or 'P3').upper()
if priority not in ('P0', 'P1', 'P2', 'P3'):
    priority = 'P3'
```

同理，`_handle_issues_put()` 中 priority 更新也需要校验。

### 3.2 🟡 应修：API 返回顺序变为隐含依赖

移除 `issues.sort(key=lambda x: x.get('updated_at', ''), reverse=True)` 后，`GET /api/issues` 返回顺序取决于 `_load_issues()` 从 JSON 文件读取的顺序（即数组存储顺序 = created_at 升序）。

前端 `sortIssuesForDisplay()` 会对返回数据重新排序，功能正确。但如果未来有其他消费者调用 `GET /api/issues`（如移动端），会依赖一个无文档保证的返回顺序。

**建议**：移除排序行的同时加注释说明排序已移至前端，或保留后端排序改为与前端一致的分组排序。

### 3.3 🟡 应修：历史数据 priority 回填方案不完整

Design §5 提到"旧数据保留无 priority"，§3.3 提到"默认 P3"。但 `requirements.json` 中 16 条现有数据均无 priority 字段，前端排序代码 `PRORITY_ORDER[a.priority] ?? 3` 通过 `?? 3` 兜底。

功能上可行，但存在不一致风险：
- 若某需求通过 PUT 更新其他字段时未携带 priority，后端不会写入 priority 字段，数据模型永远残缺
- 建议在 `_handle_requirements_post()` 中对所有读取的 requirements 补全 priority（或在首次读取时 lazy-fill）

### 3.4 🟢 已覆盖：筛选与排序交互

Design §6 Open Questions 明确"先筛选后排序"，与代码逻辑一致：前端 `loadIssues()` 先通过后端筛选获取数据，再 `sortIssuesForDisplay()` 排序。✅

### 3.5 🟢 已决策：看板页不改

Design §6 明确看板页不变，理由充分——看板是独立视图，需求描述仅针对列表页。✅

### 3.6 🟢 代码拼写

Design §4.3 排序函数中变量名 `PRORITY_ORDER` 应为 `PRIORITY_ORDER`。实现时需修正。

---

## 4. 改进建议

### 4.1 P0 — 后端 priority 白名单校验

在 `_handle_requirements_post()` 和 `_handle_issues_put()` 中增加 priority 白名单校验，仅允许 P0/P1/P2/P3，非法值 fallback P3。

### 4.2 P1 — 移除后端排序行时加注释

移除 `issues.sort(...)` 行时加注释：`# 排序已移至前端 sortIssuesForDisplay()，此处不再服务端排序`

### 4.3 P1 — 历史数据 lazy-fill

在 `_get_requirements()` 中读取后遍历补全缺失的 priority 字段并写回：
```python
for r in reqs:
    if 'priority' not in r:
        r['priority'] = 'P3'
```

### 4.4 P2 — 变量名修正

`PRORITY_ORDER` → `PRIORITY_ORDER`

---

## 5. 结论

**PASS ✅**（附条件）

上次 REJECT 的三个核心问题全部被 design 回应。设计整体合理，改动范围精确（6 处，无新增文件），分组排序模型与用户意图一致。

**附条件**：develop 阶段必须落实以下两点，否则 test 阶段直接 reject：

1. **后端 priority 白名单校验**（§3.1）— 安全底线
2. **变量名 PRORITY → PRIORITY 修正**（§3.6）— 虽为拼写但不修正会成为技术债

其余建议（§4.2 注释、§4.3 lazy-fill）为 P1/P2 改进，不阻塞。
