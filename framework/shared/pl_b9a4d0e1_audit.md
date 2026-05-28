# Audit 代码审计报告
## pl_b9a4d0e1 — 驳回已解决的问题后未触发 Pipeline

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 7fd810d

---

## 总体评定：✅ PASS

103 行改动，Review 2 个必须修复项（Requirement 覆盖 ✅、重复 Pipeline 防护 ✅）全部完成。无安全漏洞，代码质量良好。无 REJECT 项。

---

## 1. 安全审计

### 1.1 ✅ 无新增安全风险

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 注入风险 | ✅ | `_dispatch_pipeline` 使用 `requests.post` 传 JSON，`json.dumps(ensure_ascii=False)` 序列化，无字符串拼接 |
| XSS | ✅ | 无用户输入写入页面 |
| 硬编码密钥 | ✅ | 无新增密钥/凭证 |
| 权限控制 | ✅ | `_handle_audit_callback` IP 鉴权（127.0.0.1）保持不变 |
| 敏感信息泄露 | ✅ | `reject_reason` 进入 Pipeline payload，但驳回原因本就是用户可控输入，不是额外泄露 |

---

## 2. 代码质量

### 2.1 ✅ `_dispatch_pipeline` 抽取质量

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 职责单一 | ✅ | 仅负责 Pipeline 创建+推送，不涉及数据持久化 |
| 重复防护 | ✅ | `target.get('reject_pipeline_id')` 检查后返回 `skip_duplicate` |
| 失败降级 | ✅ | 推送失败返回 `push_failed`，调用方负责写入字段 |
| 幂等性 | ✅ | 同一 target 多次调用不会创建多个 Pipeline |
| 错误处理 | ✅ | Timeout / 非200 / 异常均有处理 |

### 2.2 ✅ `_handle_issues_post` 重构正确

```python
# 重构前：40行重复代码
# 重构后：3行调用
dispatch = self._dispatch_pipeline(issue, 'issue', 'issue')
issue['pipeline_id'] = dispatch['pipeline_id']
issue['pipeline_status'] = dispatch['pipeline_status']
```

二次保存逻辑保留，降级处理保留。完全符合设计文档 §2.5 中"调用方负责将返回的 pipeline_id/pipeline_status 写入数据"的要求。

### 2.3 ✅ `_handle_audit_callback` 调用正确

两处 audit_approved 分支都调用了 `_dispatch_pipeline`：
- Issue（第 1057-1059 行）
- Requirement（第 1099-1101 行）

`reject_pipeline_id` / `reject_pipeline_status` 字段正确写入，数据保存后在 SSE 广播前完成。

### 2.4 🟡 `title_prefix` 判断逻辑多余但无害

```python
title_prefix = f"[驳回重开] " if target.get('audit_status') == 'approved' or source in ('issue_reject', 'requirement_reject') else ""
```

`audit_status == 'approved'` 分支永远为真，因为调用 `_dispatch_pipeline` 时 audit 刚通过。但当 `source='issue'`（普通新建 issue）时，`audit_status` 为 None/空，不会触发。逻辑多余但不会导致错误输出。

### 2.5 🟡 无 Pipeline 创建 SSE 推送

`_dispatch_pipeline` 创建新 Pipeline 后，未显式广播 `pipeline_status` SSE 事件。`audit_result` SSE 事件（包含 `new_status`）在 Pipeline 字段写入后、广播前发送，但 `audit_result` 的 `data` 不含 `reject_pipeline_id`。

**影响**：前端收到 `audit_result` 后刷新列表时可以看到 `reject_pipeline_id`（因为数据已保存），但没有实时 `pipeline_status` 事件通知。`loadIssues()` 刷新时展示 `reject_pipeline_id` 和 `reject_pipeline_status` 字段即可，当前 SSE 设计可接受。

---

## 3. 性能风险

无新增性能风险。`_dispatch_pipeline` 是普通 HTTP POST（5s 超时），单次调用，不会阻塞主线程。

---

## 4. Review 修复项验证

| Review 必须修复项 | 状态 | 验证 |
|-------------------|------|------|
| Requirement 驳回未覆盖 | ✅ 已修复 | 第 1099-1101 行：audit_approved 分支对 Requirement 也调用 `_dispatch_pipeline` |
| 重复 Pipeline 防护缺失 | ✅ 已修复 | 第 962-964 行：`reject_pipeline_id` 已存在时返回 `skip_duplicate` |
| dispatch 职责边界清晰 | ✅ 已确认 | 方法注释明确"不负责持久化，调用方负责写入数据" |
| 保留原始 `pipeline_id` | ✅ 已确认 | `reject_pipeline_id` 存入新 Pipeline ID，原始 `pipeline_id` 不被修改 |
| `_handle_issues_post` 兼容 | ✅ 已确认 | 重构后逻辑一致，二次保存保留 |

---

## 5. 结论

设计精准，代码实现正确。Review 2 个必须修复项全部完成，额外保持了 `_handle_issues_post` 的二次保存降级逻辑。`_dispatch_pipeline` 方法抽取质量良好。

**判定：PASS** 🦂