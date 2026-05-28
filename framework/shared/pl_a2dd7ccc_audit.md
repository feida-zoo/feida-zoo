# Audit 代码审计报告
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 500edc6

---

## 总体评定：🔴 REJECT

455 行新增代码，3 个文件。Review 阶段 4 个必须修复项中完成了 3 个（需求 PUT 路由 ✅、审计术语 ✅、回调鉴权 ✅），但实现中引入 **1 个致命 bug + 1 个高危 XSS 漏洞 + 1 个中危权限问题**，必须修复。

---

## 1. 安全漏洞

### 1.1 🔴 P0：`previous_status` 永远等于 `rejected`（致命逻辑 bug）

**Issue 端**（第 1319-1320 行）：
```python
issue['status'] = 'rejected'                        # 先改了 status
issue['previous_status'] = issue.get('status', 'resolved')  # 此时 status 已经是 'rejected'
```

**Requirement 端**（第 899-900 行）：
```python
req['status'] = 'rejected'                          # 先改了 status
req['previous_status'] = req.get('status', 'done')  # 此时 status 已经是 'rejected'
```

**后果**：`previous_status` 永远存储 `'rejected'` 而非原状态。当 Duci 审计不通过（`audit_declined`）时，回调逻辑 `issue['status'] = issue.get('previous_status', 'resolved')` 会将状态恢复为 `'rejected'`——**驳回永远无法被撤销**。

**复现**：
```python
issue = {'status': 'resolved'}
issue['status'] = 'rejected'
issue['previous_status'] = issue.get('status', 'resolved')
# previous_status = 'rejected'  ← BUG，应为 'resolved'
```

**修复**：调换赋值顺序，先保存再修改：
```python
issue['previous_status'] = issue.get('status', 'resolved')  # 先保存
issue['status'] = 'rejected'                                 # 再修改
```

Issue 端和 Requirement 端都需要修复。

### 1.2 🟡 P1：前端 XSS — `onclick` 中注入未转义的 `title`

**Issue 驳回按钮**（dev_center.js 第 1343 行）：
```javascript
onclick="showIssueRejectModal('${issue.id}', '${issue.title}')"
```

**Requirement 驳回按钮**（第 1658 行）：
```javascript
onclick="showReqRejectModal('${r.id}', '${r.title}')"
```

`issue.title` 和 `r.title` 未经转义直接拼入 `onclick` 属性。若标题含单引号（如 `test'); alert('xss'); //`），攻击者可注入任意 JS。

**修复**：使用 `escapeHtml` 函数（代码中已有）转义 title，或改用 `data-*` 属性 + 事件绑定：
```javascript
// 方案 A：转义
onclick="showIssueRejectModal('${issue.id}', '${escapeHtml(issue.title)}')"

// 方案 B（推荐）：data 属性 + addEventListener
data-id="${issue.id}" data-title="${escapeHtml(issue.title)}"
```

注意：现有代码中 `escapeHtml` 只处理 `<>&"`，不处理单引号。需补充 `'` → `&#39;` 的转义。

### 1.3 🟡 P2：`rejected_by` 完全信任客户端

```python
issue['rejected_by'] = data.get('rejected_by', 'human')
```

`rejected_by` 从请求体直接写入，任何人可伪造为任意值（如 `'admin'`、`'duci'`）。

**修复**：服务端硬编码 `'dashboard_user'`，忽略客户端传入值；或后续接入认证时从 token 解析。

---

## 2. Review 修复项验证

| Review P0/P1 | 状态 | 验证 |
|--------------|------|------|
| 需求 PUT 路由不存在 | ✅ 已修复 | `do_PUT` 第 835 行新增 `/api/requirements/` 分发 |
| 审计术语 PASS/REJECT 冲突 | ✅ 已修复 | 回调仅接受 `audit_approved`/`audit_declined` |
| audit-callback 无鉴权 | ✅ 已修复 | IP 检查 `127.0.0.1`/`::1`/`localhost` |
| Dashboard/Pipeline 状态不一致 | 🟡 未处理 | 无 UI 提示，但非阻塞 |

---

## 3. 代码质量

### 3.1 ✅ 正面

1. **路由分发**：`do_PUT` 和 `do_POST` 路由新增逻辑清晰
2. **24h 冷却期**：正确实现，`except: pass` 处理了 `fromisoformat` 异常
3. **审计回调鉴权**：IP 限制 + `audit_status != 'pending'` 防重复处理 + 409 冲突响应
4. **SSE 推送**：复用已有 `sse_manager.broadcast`，正确
5. **通知降级**：`_notify_duci_audit` 的 `except` 不阻断主流程
6. **前端 XSS 防护**：`reject-target-info` 使用 `textContent` 渲染（第 1730 行）✅
7. **驳回原因校验**：前端 + 后端双重验证

### 3.2 🟡 待改进

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 1 | `from datetime import datetime as dt` 在函数内部重复导入 | 第 888、1307 行 | 已在文件顶部导入 `datetime`，应直接用 `datetime.fromisoformat()` |
| 2 | `now_iso = now` 冗余变量 | 第 1304 行 | 直接用 `now`，删掉 `now_iso` |
| 3 | `_handle_issues_put` 和 `_handle_requirements_put` 大量重复代码（rejected 分支 45 行几乎相同） | 两处 | 抽取 `_process_reject(target, data, now)` 共用方法 |
| 4 | `_handle_audit_callback` 中 issue/requirement 分支同样大量重复 | 两处 | 抽取 `_apply_audit_result(items, target_id, audit_result, audit_comment, now)` |
| 5 | `toast.innerHTML` 使用 innerHTML | 第 1772 行 | 该行不含用户输入，风险低；但最佳实践应使用 `textContent` |
| 6 | SSE broadcast 中 `new_status` 硬编码了逻辑判断 | 第 1087 行 | 与 `_handle_audit_callback` 中状态赋值逻辑重复，可能不一致 |

### 3.3 性能

- JSON 文件读写无锁保护：`_handle_requirements_put` 每次全量读写 `requirements.json`，并发驳回可能丢失数据。当前单线程 HTTP server 下无问题，但若未来改为多线程需加锁。
- 非阻塞问题，暂不修复。

---

## 4. 致命 bug 影响分析

`previous_status = 'rejected'` bug 的完整影响链：

```
1. 用户驳回 issue（status: resolved → rejected）
2. previous_status 被错误记录为 'rejected'（应为 'resolved'）
3. Duci 审计不通过，调用 audit-callback (audit_result: audit_declined)
4. 回调逻辑: issue['status'] = issue.get('previous_status', 'resolved')
5. status 变为 'rejected'（而非恢复为 'resolved'）
6. 结果：驳回永远无法被撤销，issue 永远卡在 rejected 状态
```

这是一个**破坏性 bug**——它使驳回操作变为不可逆，直接违反需求中"如果驳回不合理，则恢复原状态"的核心要求。

---

## 5. 修复清单

| # | 优先级 | 修复 | 工作量 |
|---|--------|------|--------|
| 1 | 🔴 P0 | `previous_status` 赋值顺序：先保存再修改（Issue + Requirement 两处） | 2 行 |
| 2 | 🟡 P1 | 前端 `onclick` 中 title 转义（`escapeHtml` 补充单引号 + 两处调用） | 4 行 |
| 3 | 🟡 P2 | `rejected_by` 硬编码为 `'dashboard_user'`，不取客户端值 | 2 行 |
| 4 | 🟢 P3 | 删除冗余 `now_iso`、移除函数内 `import` | 3 行 |

**总修复量：约 11 行，15 分钟。**

---

## 6. 结论

Review 阶段 4 个 P0/P1 项完成了 3 个，方向正确。但 `previous_status` 赋值顺序 bug 是致命的——它使驳回操作不可逆，直接违反需求核心逻辑。必须修复。

**判定：REJECT** 🦂

修复上述 3 项（P0 + P1 + P2）后可重新提交。
