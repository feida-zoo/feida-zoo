# 需求评审 + 架构设计文档
## pl_b9a4d0e1 — 驳回已解决的问题后未触发 Pipeline

---

## 1. 需求评审

### 1.1 问题描述

用户进入了 pl_a2dd7ccc 的驳回流程：
1. 在问题管理页驳回了一个**已解决**的 issue（"成员管理界面优化"）
2. 状态从 `resolved` → `rejected`（pending_audit）
3. 毒刺审计通过后（`audit_approved`），状态变为 `in_progress`
4. **但没有触发新的 Pipeline**，所以没有开发任务流转

### 1.2 根因分析

当前 `_handle_audit_callback` 中 `audit_approved` 分支：
```python
if audit_result == 'audit_approved':
    issue['status'] = 'in_progress'
    issue['audit_status'] = 'approved'
    # 没有通知 Panda，没有创建 Pipeline
```

而 `_handle_issues_post` 在新建 issue 时会创建 Pipeline：
```python
# 生成 pipeline_id
pipeline_id = f"pl_{uuid.uuid4().hex[:8]}"
# 构建 payload
pipeline_payload = {
    "type": "pipeline_request",
    "task_id": pipeline_id,
    "requirement_id": issue["id"],
    "title": title,
    "description": issue["description"],
    ...
}
# 通知 Panda
requests.post(f"{ZOO_MESH_HTTP}/api/chat", json={
    'from': 'dashboard',
    'content': f"@panda 新Pipeline请求: {json.dumps(pipeline_payload, ensure_ascii=False)}"
})
```

驳回审计通过后缺少这步 Pipeline 创建。**可行。**

### 1.3 依赖项

| 依赖 | 级别 | 说明 |
|------|------|------|
| ZooMesh HTTP API (`/api/chat`) | 已有 | 用于通知 Panda |
| Panda 的 Inbox 消费者 | 已有 | 已能消费 `@panda 新Pipeline请求` 消息 |
| Duci 审计回调 | 已有 | `_handle_audit_callback` 已实现 |
| Issue 数据结构 | 已有 | 含 `pipeline_id`, `pipeline_status` 字段 |

### 1.4 风险点

| 风险 | 等级 | 说明 | 缓解 |
|------|------|------|------|
| 重复 Pipeline | 🟡 P1 | 驳回→审计通过→创建 Pipeline，若再次驳回会再创建，产生多条 | 创建前检查 `issue.get('pipeline_id')` 是否存在 |
| 原 Pipeline 状态冲突 | 🟡 P1 | 驳回的 issue 原本有 `pipeline_id` 指向已 done 的 Pipeline | 生成新的 `pipeline_id`（而非复用旧的） |
| 无 assignee 时缺省 | 🟢 P2 | 驳回后的 issue 可能没有 assignee | 缺省使用 `alpha`，与创建 issue 一致 |

### 1.5 优先级

| 优先级 | 项 | 理由 |
|--------|----|------|
| **P0** | 审计通过后创建新 Pipeline | 核心功能缺失 |
| **P1** | 避免重复创建 Pipeline | 非幂等风险 |
| **P1** | SSE 推送 pipeline 创建状态 | 前端实时反馈 |

---

## 2. 架构设计

### 2.1 What

在 `_handle_audit_callback` 的 `audit_approved` 分支中，增加 Pipeline 创建逻辑——当 Duci 审计认为驳回合理时，自动为 issue 创建新的 Pipeline，将开发任务重新派发。

### 2.2 Why

当前驳回→审计通过后仅将状态改为 `in_progress`，但没有给 Panda 下达开发任务。开发人员看到状态变了，但不知道要做什么。必须创建 Pipeline 才能进入正常的开发流转。

### 2.3 Tradeoff

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A: 复用 `_handle_issues_post` 的 Pipeline 创建逻辑**（推荐） | 代码复用，模式一致 | 需抽取公共方法 |
| B: 在 `_handle_audit_callback` 中独立写 Pipeline 创建 | 改动最小 | 代码重复 |
| C: 让 Duci 的审计回复触发 Panda | 松耦合 | 依赖 Duci 行为，不可控 |

**结论**：采用方案 A —— 抽取一个 `_dispatch_pipeline_for_issue(issue)` 公共方法，被 `_handle_issues_post` 和 `_handle_audit_callback` 复用。

### 2.4 接口定义

**新增方法**：
```python
def _dispatch_pipeline_for_issue(self, issue: dict) -> dict:
    """为 issue 创建并推送新 Pipeline。返回更新后的 issue（含 pipeline_id）。"""
```

**无新增 API 路由**。仅修改内部逻辑。

**Pipeline payload 结构**：
```python
{
    "type": "pipeline_request",
    "task_id": "pl_uuid8",          # 新生成的 pipeline_id
    "requirement_id": issue["id"],
    "title": f"[驳回重开] {issue['title']}",  # 加前缀标识
    "description": f"驳回原因: {issue.get('reject_reason', '')}\n\n{issue.get('description', '')}",
    "assignee": issue.get("assignee") or "alpha",
    "source": "issue_reject",
    "timestamp": now
}
```

### 2.5 执行流程

```
用户驳回 issue (resolved → rejected)
    ↓
_notify_duci_audit() 通知 Duci ──────────────┐
                                              │  No pipeline here
Duci 审计通过 (audit_approved)                │  (只通知，不创建)
    ↓                                         │
_handle_audit_callback()                      │
    ├─ issue.status = in_progress             │
    ├─ issue.audit_status = approved          │
    └─ NEW: _dispatch_pipeline_for_issue() ───┘  ← HERE
         └─ POST /api/chat → Panda
              └─ Panda 创建新 Pipeline
                   └─ 任务从 design 开始流转
```

### 2.6 文件清单

```
改动文件：

1. dashboard/app_enhanced.py
   - 抽取 _dispatch_pipeline_for_issue() 方法（复用 _handle_issues_post 中的 Pipeline 创建逻辑）
   - _handle_audit_callback 的 audit_approved 分支调用 _dispatch_pipeline_for_issue()
   - _handle_issues_post 改为调用 _dispatch_pipeline_for_issue() 消除重复

新增文件：无
```

### 2.7 Requirement 的特殊性

Requirement 驳回后（done → rejected → develop_code）有 `pipeline_id` 字段指向原有 Pipeline。但原始需求说"用户只说了驳回 issue 没触发 pipeline"，而 requirement 本身是通过 `_handle_requirements_post` 创建的、本身就有 Pipeline。

**决策**：本设计仅覆盖 **Issue 驳回**场景。Requirement 驳回已有 Pipeline ID 且 `develop_code` 阶段供外部交互，不创建新 Pipeline。

---

## 3. UI 设计

### 3.1 变更范围

**无前端 UI 变更**。后端 Pipeline 创建后：
- frontend 通过现有 SSE `pipeline_status` 事件获得推送（已有 `_start_pipeline_monitor`）
- `loadIssues()` 刷新时显示 `pipeline_id` 和 `pipeline_status`
- Issue 卡片的 meta 区域已支持显示 `pipeline_id`（参考现有 `_handle_issues_post` 的字段）

### 3.2 SSE 推送

审计回调结束时触发 SSE 推送（已有 `sse_manager.broadcast("audit_result", ...)`，无需新增）。但 Pipeline 创建后，Monitor 会自动探测变化并推送 `pipeline_status` 事件。

---

## 4. 执行计划

### Phase: develop_code

| 步骤 | 改动 | 位置 | 工作量 |
|------|------|------|--------|
| 1 | 抽取 `_dispatch_pipeline_for_issue()` | app_enhanced.py 新增方法 | ~10分钟 |
| 2 | `_handle_audit_callback` 调用新方法 | app_enhanced.py audit_approved 分支 | ~2分钟 |
| 3 | `_handle_issues_post` 复用新方法（消除重复代码） | app_enhanced.py | ~5分钟 |
| 4 | 端到端验证 | 创建 issue→解决→驳回→审计通过→检查 Pipeline | ~10分钟 |
| **总计** | | | **~27分钟** |

### Phase: review / audit

- 确认 `_dispatch_pipeline_for_issue()` 在 audit_approved 时被调用
- 确认新 Pipeline 的 pipeline_id 不冲突
- 确认 SSE 推送生效
- 确认 requirement 驳回不受影响

---

*文档版本: v1.0 | 设计者: Alpha 🐢 | 日期: 2026-05-28*
