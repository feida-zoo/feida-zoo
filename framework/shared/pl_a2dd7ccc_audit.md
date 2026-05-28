# Audit 代码审计报告
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 0268ba4

---

## 总体评定：✅ PASS

上轮 REJECT 的 3 项（P0 previous_status、P1 XSS、P2 rejected_by）全部修复确认。额外清理了 2 项代码质量问题。无新问题引入。

---

## 1. 上轮 REJECT 项逐项验证

### 1.1 🔴→✅ P0：`previous_status` 赋值顺序修复

**Issue 端**（第 1314-1315 行）：
```python
# 先保存原状态，再改为 rejected
issue['previous_status'] = issue.get('status', 'resolved')  # ✅ 先保存
issue['status'] = 'rejected'                                 # ✅ 再修改
```

**Requirement 端**（第 900-901 行）：
```python
# 先保存原状态，再改为 rejected
req['previous_status'] = req.get('status', 'done')  # ✅ 先保存
req['status'] = 'rejected'                            # ✅ 再修改
```

**验证**：
```
Issue: previous_status='resolved', status='rejected' ✅
Req:   previous_status='done',     status='rejected' ✅
```

### 1.2 🟡→✅ P1：前端 XSS 修复

**escapeHtml 补充单引号转义**（第 1262 行）：
```javascript
return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;');
```

**onclick 中 title 使用 escapeHtml**（第 1343、1658 行）：
```javascript
onclick="showIssueRejectModal('${issue.id}', '${escapeHtml(issue.title)}')"
onclick="showReqRejectModal('${r.id}', '${escapeHtml(r.title)}')"
```

**验证**：`test'); alert('xss'); //` → `test&#39;); alert(&#39;xss&#39;); //`，单引号已转义 ✅

### 1.3 🟡→✅ P2：`rejected_by` 硬编码

两处均已改为 `'dashboard_user'`，不再从 `data.get('rejected_by')` 读取 ✅

---

## 2. 额外修复确认

| 清理项 | 原代码 | 修复后 |
|--------|--------|--------|
| 函数内重复 `import` | `from datetime import datetime as dt` | 直接用顶层 `datetime.fromisoformat()` ✅ |
| 冗余变量 | `now_iso = now` | 删除，直接用 `now` ✅ |
| 无用注释 | `# 立即使状态变为 rejected（上面已赋值）` | 删除 ✅ |

---

## 3. 残余非阻塞项（上轮已标注 P3，不阻塞 PASS）

| # | 项 | 说明 |
|---|-----|------|
| 1 | `_handle_issues_put` 与 `_handle_requirements_put` rejected 分支 45 行重复 | 可后续抽取共用方法 |
| 2 | `_handle_audit_callback` 中 issue/requirement 分支重复 | 同上 |
| 3 | SSE broadcast 中 `new_status` 硬编码判断与回调逻辑重复 | 可后续统一 |
| 4 | JSON 文件读写无锁 | 单线程 server 下无问题 |
| 5 | Dashboard/Pipeline 状态不一致无 UI 提示 | 非核心功能 |

---

## 4. 结论

上轮 3 项 REJECT 全部修复，验证通过。额外清理了 2 项代码质量残余。无新问题引入。

**判定：PASS** 🦂
