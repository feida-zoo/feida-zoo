# Review 设计评审报告
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: e1e36cc

---

## 总体评定：✅ PASS（4 个必须修复项 + 2 个建议项，均可在 develop_code 阶段修复）

设计方向正确（方案 A+D 组合），与现有架构兼容。但存在 1 个关键架构遗漏、2 个安全风险、1 个逻辑矛盾，必须在 develop_code 阶段修正。

---

## 1. 架构合理性

### 1.1 方案选择：✅ 正确

A+D（前端状态标记 + 异步审计回调）是最优解。深度集成 Pipeline 状态机（方案 B）改动量大且无必要——驳回是 Dashboard 层面的质量控制，不是 Pipeline 流转。

### 1.2 🔴 关键遗漏：需求 PUT 路由不存在

当前 `app_enhanced.py` 的 `do_PUT()` 方法（第 826 行）**仅处理 `/api/issues/:id`**，不存在 `/api/requirements/:id` 的 PUT 路由。

设计文档 §2.5 声称"扩展 `_handle_requirements_put()`"，但该方法**根本不存在**。同样，设计中的 `POST /api/audit-callback` 路由也不存在。

**必须在 develop_code 阶段新增**：
1. `do_PUT()` 中添加 `/api/requirements/:id` 路由分发
2. 新增 `_handle_requirements_put()` 方法
3. 新增 `POST /api/audit-callback` 路由及 `_handle_audit_callback()` 方法

### 1.3 数据结构扩展：✅ 合理

`previous_status` 字段用于审计不通过时恢复状态，设计合理。但需注意：

- Issue 当前数据结构无 `previous_status` 字段（现有字段：id, title, description, priority, status, assignee, created_at, updated_at, resolved_at, source）
- Requirement 当前数据结构同样无此字段（现有字段：id, title, description, assignee, status, phase, priority, created_at, pipeline_id, source, updated_at, completed_at）
- 新字段需在首次驳回时动态添加，不影响已有数据

### 1.4 SSE 推送机制：✅ 可复用

现有 `SSEManager` 类（第 110 行）和前端 `EventSource` 连接（dev_center.js:962）可直接用于审计结果推送，无需额外轮询。

---

## 2. 安全风险

### 2.1 🟡 P1：`POST /api/audit-callback` 无鉴权

设计文档未提及 audit-callback 接口的鉴权机制。任何知道此端点的人都可伪造 Duci 审计结果，将驳回状态直接改回 `done`/`resolved`。

**修复建议**：
- 方案 A（推荐）：回调通过 ZooMesh 内部 HTTP 通知 Duci，Duci 审计完成后通过 `sessions_send` 更新 Dashboard 数据，而非暴露 HTTP 回调端点
- 方案 B：回调端点增加 token 验证（`X-Audit-Token` header，与 Duci 共享密钥）
- 方案 C：限制回调仅接受来自 127.0.0.1 的请求

### 2.2 🟡 P1：驳回操作无权限控制

设计文档 §1.3 提到"Dashboard 操作者即驳回人"，但当前 Dashboard 无任何用户认证。任何人打开页面即可驳回任何已完成的需求/问题。

**修复建议**：至少在驳回时记录 `rejected_by` 字段（当前设计已包含），后续可接入简单密码/token 验证。MVP 阶段可接受。

### 2.3 🟢 P3：驳回原因 XSS

驳回原因由用户输入后通过 API 存储并展示。前端需确保不使用 `innerHTML` 直接渲染，应使用 `textContent` 或转义。

---

## 3. 逻辑矛盾与遗漏

### 3.1 🔴 逻辑矛盾：审计"通过"=驳回"合理"

设计文档的状态流转图：

```
Duci audit PASS → in_progress (重新修复)
Duci audit REJECT → resolved (恢复)
```

这里的术语极其反直觉：**"audit PASS"意味着"驳回合理"**，**"audit REJECT"意味着"驳回不合理"**。

这与 Pipeline 中 audit phase 的语义完全相反（Pipeline 中 audit PASS = 代码没问题，audit REJECT = 代码有问题）。

**必须修正**：统一术语。建议改为：
- `audit_approved`（审计同意驳回） → 状态流转到 `in_progress`/`develop_code`
- `audit_declined`（审计不同意驳回） → 状态恢复原终态

或者保持 pass/reject 但在 UI 展示时转换为人类可读的中文。

### 3.2 🟡 遗漏：`rejected` 状态与 Pipeline `done` 的不一致处理

设计文档说"驳回状态仅用于 Dashboard 展示，不写入 Pipeline state_machine"。但需求（requirement）有 `pipeline_id` 字段，驳回后：
- Dashboard 显示 `rejected`
- Pipeline 仍显示 `done`

这会导致**数据不一致**。需明确：
- 驳回后是否需要调用 `zoo_mesh_daemon` 的 `pipeline_restart` 或类似接口？
- 还是仅在 Dashboard 层面标记，Pipeline 不感知？

**建议**：MVP 阶段仅 Dashboard 层面标记，但需在 UI 上明确提示"此需求已在 Dashboard 层面驳回，Pipeline 状态未变更"。

### 3.3 🟡 遗漏：Issue 没有 `pipeline_id` 字段

Issue 数据结构中无 `pipeline_id`，驳回后如何触发"返回开发阶段"？Issue 的开发流程与 Pipeline 无关，设计文档中 Issue 驳回后状态流转到 `in_progress`，但 `in_progress` 的 assignee 是谁？是否需要重新分配？

**建议**：驳回时保留原 `assignee`，无需重新分配。在 `in_progress` 状态下仍由原处理人修复。

### 3.4 🟡 遗漏：24h 冷却期实现方案

设计文档 §1.3 提到"同一需求 24h 内仅允许驳回一次"，但 §2.4 接口定义和 §3.4 交互逻辑中均未体现此约束的实现方案。

**建议**：后端在处理驳回请求时检查 `rejected_at` 字段，若距当前时间 < 24h 则返回 `429 Too Many Requests`。

---

## 4. 改进建议

| # | 优先级 | 问题 | 建议 |
|---|--------|------|------|
| 1 | 🔴 P0 | 需求 PUT 路由不存在 | develop_code 阶段必须新增 |
| 2 | 🔴 P0 | 审计术语 PASS/REJECT 与 Pipeline 语义冲突 | 改用 `audit_approved`/`audit_declined` |
| 3 | 🟡 P1 | audit-callback 无鉴权 | 限制 127.0.0.1 或 token 验证 |
| 4 | 🟡 P1 | Dashboard 与 Pipeline 状态不一致 | UI 提示 + MVP 不改 Pipeline |
| 5 | 🟡 P2 | 24h 冷却期未设计实现 | 后端检查 `rejected_at` |
| 6 | 🟢 P3 | 驳回原因 XSS | 前端 `textContent` 渲染 |

---

## 5. 文件清单验证

| 设计文档声称的改动 | 现状 | 差异 |
|---------------------|------|------|
| `_handle_issues_put()` 扩展 | ✅ 已存在（第 1021 行），仅处理 `resolved` | 需扩展 `rejected` 逻辑 |
| `_handle_requirements_put()` 扩展 | ❌ **不存在** | 必须新增 |
| `_handle_audit_callback()` | ❌ **不存在** | 必须新增 |
| `_notify_duci_audit()` | ❌ 不存在，但 `requests.post(ZOO_MESH_HTTP)` 模式已有 | 参考第 609/646/731 行 |
| `dev_center.js` loadIssues 驳回按钮 | ✅ 函数存在（第 1266 行），无驳回逻辑 | 需扩展 |
| `dev_center.js` loadRequirementsList 驳回按钮 | ✅ 函数存在（第 1610 行），无驳回逻辑 | 需扩展 |
| SSE 推送审计结果 | ✅ SSEManager + EventSource 均已就绪 | 复用即可 |

---

## 6. 结论

设计方向正确，方案选择合理，与现有架构兼容。**4 个必须修复项**（需求 PUT 路由缺失、审计术语冲突、回调鉴权、状态不一致）均可在 develop_code 阶段修正，不阻塞进入开发。

**判定：PASS** 🦂

develop_code 阶段须优先处理上述 P0/P1 项。
