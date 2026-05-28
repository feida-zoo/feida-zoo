# Review 设计评审报告
## pl_b9a4d0e1 — 驳回已解决的问题后未触发 Pipeline

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: ea1671d

---

## 总体评定：✅ PASS（2 个必须修复项 + 1 个建议项）

设计精准定位了根因（`_handle_audit_callback` 中 `audit_approved` 分支缺少 Pipeline 创建），方案 A（抽取 `_dispatch_pipeline_for_issue` 公共方法）正确。但有 2 个必须在 develop_code 阶段修正的设计遗漏。

---

## 1. 架构合理性

### 1.1 方案选择：✅ 正确

方案 A（抽取公共方法复用 `_handle_issues_post` 的 Pipeline 创建逻辑）最优。方案 B 代码重复，方案 C 依赖 Duci 行为不可控。

### 1.2 🔴 必须修复：Requirement 驳回未覆盖

设计文档 §2.7 明确说"本设计仅覆盖 Issue 驳回场景"，理由是"Requirement 驳回已有 Pipeline ID"。

但这个理由**站不住脚**：

1. Requirement 驳回后状态变为 `develop_code`（第 1067 行），但原有 Pipeline 已 `done`，不会再处理此阶段
2. 用户看到的交互是：需求被驳回 → 状态变为 `develop_code` → **但没有人来做开发**
3. Issue 和 Requirement 驳回的痛点完全相同——都是"驳回了但没有开发任务流转"

**修复建议**：`_dispatch_pipeline_for_issue` 应泛化为 `_dispatch_pipeline`，支持 `target_type` 参数。Requirement 驳回审计通过时也创建新 Pipeline，title 前缀同样加 `[驳回重开]`，`source` 设为 `requirement_reject`。

### 1.3 🟡 必须修复：重复 Pipeline 防护不足

设计文档 §1.4 提到"创建前检查 `issue.get('pipeline_id')` 是否存在"，但实际执行方案（§2.4）中未体现此检查。

当前 Issue 数据结构中 `pipeline_id` 是**首次创建时写入的**，驳回后不会清除。如果不做处理，审计通过时 `_dispatch_pipeline_for_issue` 会无条件创建新 Pipeline。

**修复建议**：
- 方案 A（推荐）：驳回时不清除 `pipeline_id`，新 Pipeline 使用新 ID，存入 `reject_pipeline_id` 字段（保留原 `pipeline_id` 用于追溯）
- 方案 B：驳回时覆盖 `pipeline_id` 为新值，将原值存入 `original_pipeline_id`
- 方案 C：新增 `pipeline_ids` 数组字段，追加式存储

---

## 2. 安全风险

### 2.1 ✅ 无新增安全风险

- `_dispatch_pipeline_for_issue` 调用 `requests.post(ZOO_MESH_HTTP)` 通知 Panda，与现有 `_handle_issues_post` 模式一致
- 回调已有 IP 鉴权，Pipeline 创建在鉴权通过后执行
- Pipeline payload 不含用户敏感信息

### 2.2 🟢 提示：Pipeline payload 含驳回原因

```python
"description": f"驳回原因: {issue.get('reject_reason', '')}\n\n{issue.get('description', '')}",
```

驳回原因由用户输入，会进入 Pipeline payload 并通过 `@panda` 消息传递。需确认 Panda 消费者能正确处理含换行/特殊字符的 payload。当前 `json.dumps(ensure_ascii=False)` 已处理 JSON 序列化，风险低。

---

## 3. 遗漏检查

### 3.1 🟡 `_handle_issues_post` 重构的影响范围

设计文档 §2.6 提到" `_handle_issues_post` 改为调用 `_dispatch_pipeline_for_issue()` 消除重复"。这是一个**重构操作**，需注意：

1. `_handle_issues_post` 中的 Pipeline 推送逻辑（第 1221-1260 行）包含**二次保存**和**失败降级**（`push_failed` 时 pop `pipeline_id`）
2. 抽取为公共方法后，调用方的二次保存逻辑必须保留
3. 当前 `_handle_issues_post` 的推送在 `issues.append(issue)` + `_save_issues(issues)` 之后执行，而 `_handle_audit_callback` 中 issue 已存在于列表中——两者调用上下文不同

**建议**：`_dispatch_pipeline_for_issue` 应仅负责 Pipeline 创建和推送，返回 `pipeline_id` 和 `pipeline_status`。调用方负责写入 issue 字段并保存。不要让公共方法承担数据持久化职责。

### 3.2 🟢 旧 Pipeline ID 追溯

驳回后创建新 Pipeline，旧的 `pipeline_id` 保留在 issue 中（若采用方案 A/B）。前端 `loadIssues()` 当前如何展示 `pipeline_id`？是否需要区分"原始 Pipeline"和"驳回重开 Pipeline"？

---

## 4. 改进建议

| # | 优先级 | 问题 | 建议 |
|---|--------|------|------|
| 1 | 🔴 P0 | Requirement 驳回未覆盖 | `_dispatch_pipeline` 支持 requirement，审计通过时也创建新 Pipeline |
| 2 | 🟡 P1 | 重复 Pipeline 防护缺失 | 新 Pipeline ID 存入 `reject_pipeline_id`，保留原 `pipeline_id` |
| 3 | 🟢 P2 | 公共方法职责边界不清 | 仅负责创建+推送，返回结果，不负责持久化 |

---

## 5. 结论

根因分析准确，方案选择正确，代码复用思路清晰。2 个必须修复项（Requirement 覆盖 + 重复 Pipeline 防护）均可在 develop_code 阶段修正，不阻塞进入开发。

**判定：PASS** 🦂
