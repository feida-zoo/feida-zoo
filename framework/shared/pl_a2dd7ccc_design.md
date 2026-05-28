# 需求评审 + 架构设计文档
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

---

## 1. 需求评审

### 1.1 总体可行性：✅ 通过

本需求为 **Dashboard 前端交互增强 + 后端状态流转扩展**，不涉及第三方依赖变更，不改动 Pipeline 核心引擎。所有改动可在现有 `app_enhanced.py` HTTP handler 和 `dev_center.js` 中扩展实现。**可行。**

### 1.2 依赖项

| 依赖 | 级别 | 说明 |
|------|------|------|
| Dashboard 现有 CRUD API | 已有 | `/api/issues/:id` PUT 已支持 status 更新 |
| ZooMesh 通知通道 | 已有 | `requests.post(ZOO_MESH_HTTP/api/chat)` 已用于 Panda 通知 |
| Duci session key | 已有 | `agent:duci:main` 已知，见 AGENTS.md |
| 需求/问题 JSON 数据结构 | 已有 | `status` 字段已存在，扩展即可 |

### 1.3 风险点

| 风险 | 等级 | 说明 | 缓解 |
|------|------|------|------|
| 状态流转与 Pipeline 状态机冲突 | 🟡 P1 | 驳回后的 "rejected" 状态不是 Pipeline 原生状态 | 驳回状态仅用于 Dashboard 展示，不写入 Pipeline state_machine；Pipeline 仍用 done/resolved |
| 毒刺审计异步流程 | 🟡 P2 | Duci 是异步 Agent，无法即时响应驳回请求 | 驳回后写入 "pending_audit" 状态，Duci 审计后回调更新；超时自动通过 |
| 重复驳回 | 🟡 P2 | 同一需求被多次驳回可能产生审计疲劳 | 每次驳回需不同原因；同一需求 24h 内仅允许驳回一次 |
| 权限控制 | 🟢 P3 | 谁可以驳回？当前无用户认证 | 简化：Dashboard 操作者即驳回人，记录 `rejected_by` 字段 |

### 1.4 优先级

| 优先级 | 项 | 理由 |
|--------|----|------|
| **P0** | 需求管理页驳回按钮 + 弹窗 | 核心交互 |
| **P0** | 问题管理页驳回按钮 + 弹窗 | 核心交互 |
| **P0** | 后端 PUT 接口扩展 reject 逻辑 | 数据持久化 |
| **P1** | 毒刺审计通知 + 回调处理 | 审计闭环 |
| **P1** | 驳回原因记录 + 历史展示 | 可追溯 |
| **P2** | 24h 冷却期防滥用 | 体验优化 |

---

## 2. 架构设计

### 2.1 What

在 Zoo Dev-Center 的 **需求管理页**和**问题管理页**中，为已完成（`done`/`resolved`/`closed`）的条目增加 **"驳回"** 操作：

1. 用户点击驳回 → 弹出原因输入框
2. 提交驳回 → 条目状态变为 `rejected`，记录驳回原因和驳回人
3. 自动通知 **毒刺（Duci 🦂）**进行审计
4. Duci 审计通过（reject 合理）→ 状态流转到开发阶段（`develop_code` 或 `in_progress`）
5. Duci 审计不通过（reject 不合理）→ 状态恢复为原终态（`done`/`resolved`）

### 2.2 Why

- 当前系统只有单向流转（创建→处理→完成），缺少**逆向质量控制**机制
- 已完成的需求/issue 若存在缺陷，需要一种**可追溯的驳回+重修复**流程
- 毒刺作为审计专家，其审计意见是驳回是否合理的权威判定

### 2.3 Tradeoff

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A: 纯前端状态标记**（推荐） | 最小改动，不碰 Pipeline 引擎 | 状态与 Pipeline 可能短暂不一致 |
| B: 深度集成 Pipeline 状态机 | 状态完全一致 | 改动量大，需修改 StateMachine + 所有 executor |
| C: 同步阻塞等待 Duci 审计 | 即时反馈 | Duci 响应时间不可控，用户体验差 |
| **D: 异步审计 + 回调更新**（推荐） | 非阻塞，符合现有通知模式 | 需要轮询或 SSE 更新状态 |

**结论**：采用 A + D 组合——前端状态标记 + 异步审计回调。驳回状态仅存在于 Dashboard 数据中，Pipeline 引擎不受影响。

### 2.4 接口定义

#### 2.4.1 后端 API 扩展

```
PUT /api/issues/:id
  Body: { "status": "rejected", "reject_reason": "...", "reject_action": "reject" }
  → 更新 issue 状态为 rejected，记录 reject_reason, rejected_by, rejected_at

PUT /api/requirements/:id
  Body: { "status": "rejected", "reject_reason": "...", "reject_action": "reject" }
  → 更新 requirement 状态为 rejected，记录同上

POST /api/audit-callback
  Body: { "target_id": "...", "target_type": "issue|requirement", 
          "audit_result": "pass|reject", "audit_comment": "..." }
  → Duci 审计完成后回调，更新状态
```

#### 2.4.2 数据结构扩展

**Issue 扩展字段：**
```json
{
  "id": "uuid",
  "status": "rejected",
  "reject_reason": "修复不完整，缺少边界测试",
  "rejected_by": "human",
  "rejected_at": "2026-05-28T20:00:00",
  "audit_status": "pending|pass|reject",
  "audit_comment": "",
  "audit_agent": "duci",
  "previous_status": "resolved"
}
```

**Requirement 扩展字段：**
```json
{
  "id": "uuid",
  "status": "rejected",
  "reject_reason": "UI 交互不符合设计稿",
  "rejected_by": "human",
  "rejected_at": "2026-05-28T20:00:00",
  "audit_status": "pending|pass|reject",
  "audit_comment": "",
  "audit_agent": "duci",
  "previous_status": "done"
}
```

#### 2.4.3 状态流转图

```
Issue 状态流转:
  open → in_progress → resolved ─┬→ closed
                                 │
                                 └→ [驳回] → rejected(pending_audit)
                                      ↓
                                 ┌─ Duci audit PASS → in_progress (重新修复)
                                 └─ Duci audit REJECT → resolved (恢复)

Requirement 状态流转:
  request → ... → done ─┬→ cancelled/timed_out/escalated
                          │
                          └→ [驳回] → rejected(pending_audit)
                               ↓
                          ┌─ Duci audit PASS → develop_code (重新修复)
                          └─ Duci audit REJECT → done (恢复)
```

### 2.5 文件清单

```
改动文件：

1. dashboard/app_enhanced.py
   - _handle_issues_put(): 扩展 status="rejected" 处理逻辑
   - _handle_requirements_put(): 新增或扩展 PUT 处理（如不存在）
   - 新增 _handle_audit_callback(): 处理 Duci 审计回调
   - 新增 _notify_duci_audit(): 通知 Duci 进行审计

2. dashboard/static/dev_center.js
   - loadIssues(): 为 resolved/closed 条目增加"驳回"按钮
   - loadRequirementsList(): 为 done 条目增加"驳回"按钮
   - 新增 showRejectModal(): 驳回原因输入弹窗
   - 新增 submitReject(): 提交驳回请求
   - 新增 closeRejectModal(): 关闭弹窗
   - 新增 handleAuditResult(): 处理审计回调刷新

3. dashboard/templates/dev_center.html
   - 新增"驳回原因"模态框（reject-modal）
   - 新增 CSS 样式（reject-btn, reject-modal 等）

4. dashboard/static/dev_center.css（如需要）
   - 驳回按钮样式、驳回状态标签样式

新增文件：无
```

### 2.6 环境变量 / 配置

无需新增环境变量。复用现有：
- `ZOO_MESH_HTTP` — 通知 Duci 的 HTTP API
- Duci session key 从 `zoo_members.yaml` 读取（已脱敏，但代码中通过 `agent:duci:main` 硬编码引用）

---

## 3. UI 设计

### 3.1 需求管理页 — 驳回交互

**触发条件**：仅当 `status === 'done'` 时显示"驳回"按钮。

**列表项布局变更：**
```
┌─────────────────────────────────────────────────────────────┐
│ [P1高] 需求标题                          [done]  阿尔法  时间 │
│                                                              │
│ 驳回原因: 修复不完整，缺少边界测试...                        │
│ [查看详情] [撤销驳回]                                        │
└─────────────────────────────────────────────────────────────┘
```

**驳回弹窗（reject-modal）：**
```
┌────────────────────────────────────────┐
│ 驳回需求 — 请填写驳回原因              │
├────────────────────────────────────────┤
│ 需求: #123 需求管理页排序功能          │
│                                        │
│ 驳回原因:                              │
│ ┌──────────────────────────────────┐   │
│ │                                  │   │
│ │ 修复不完整，缺少边界测试...      │   │
│ │                                  │   │
│ └──────────────────────────────────┘   │
│                                        │
│ [取消]              [提交驳回]         │
└────────────────────────────────────────┘
```

### 3.2 问题管理页 — 驳回交互

**触发条件**：仅当 `status === 'resolved' || status === 'closed'` 时显示"驳回"按钮。

**列表项布局变更：**
```
┌─────────────────────────────────────────────────────────────┐
│ [P0紧急] 问题标题                        [resolved] 时间   │
│                                                              │
│ 驳回原因: 修复未覆盖并发场景...                              │
│ [查看详情] [撤销驳回]                                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 状态标签定义

| 状态 | 中文 | CSS 类 | 颜色 |
|------|------|--------|------|
| rejected | 已驳回 | status-rejected | #e74c3c (红色) |
| pending_audit | 审计中 | status-pending-audit | #f39c12 (橙色) |

### 3.4 交互逻辑

```
用户点击"驳回"按钮
    ↓
显示 reject-modal（预填需求/问题标题）
    ↓
用户输入驳回原因，点击"提交驳回"
    ↓
PUT /api/issues/:id {status:"rejected", reject_reason:"..."}
    ↓
后端更新 JSON 文件，状态变为 rejected
    ↓
后端发送通知给 Duci（通过 ZooMesh HTTP API）
    ↓
前端刷新列表，显示"审计中"状态
    ↓
Duci 收到通知，进行审计
    ↓
Duci 回复 audit_result（pass/reject）
    ↓
后端回调更新状态（develop_code / 恢复原状态）
    ↓
前端 SSE 或轮询刷新显示最终结果
```

---

## 4. 执行计划

### Phase: develop_code

| 步骤 | 改动文件 | 工作量 |
|------|----------|--------|
| 1 | app_enhanced.py: _handle_issues_put 扩展 rejected 逻辑 | ~10分钟 |
| 2 | app_enhanced.py: 新增 _handle_requirements_put / _handle_audit_callback | ~15分钟 |
| 3 | app_enhanced.py: 新增 _notify_duci_audit 通知函数 | ~10分钟 |
| 4 | dev_center.js: loadIssues() 增加驳回按钮 + 弹窗调用 | ~15分钟 |
| 5 | dev_center.js: loadRequirementsList() 增加驳回按钮 + 弹窗调用 | ~15分钟 |
| 6 | dev_center.js: 新增 showRejectModal / submitReject / closeRejectModal | ~15分钟 |
| 7 | dev_center.html: 新增 reject-modal DOM | ~10分钟 |
| 8 | dev_center.css: 驳回按钮 + 状态标签样式 | ~10分钟 |
| 9 | 端到端测试：创建 issue → 完成 → 驳回 → 审计 → 验证 | ~15分钟 |
| **总计** | **~115分钟** | |

### Phase: review / audit

- 验证驳回按钮仅在 done/resolved/closed 状态显示
- 验证驳回后状态正确更新为 rejected
- 验证 Duci 收到审计通知
- 验证审计通过后状态流转到 develop_code/in_progress
- 验证审计不通过后状态恢复

---

*文档版本: v1.0 | 设计者: Alpha 🐢 | 日期: 2026-05-28*
