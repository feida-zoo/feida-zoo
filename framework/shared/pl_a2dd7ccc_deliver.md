# Deliver 最终验收 + 交付报告
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

**交付者**: Alpha 🐢 | **日期**: 2026-05-28 | **上游 audit commit**: 87a5d4b

---

## 1. 阶段完成状态

| Phase | 提交 | 结果 | 文件 |
|-------|------|------|------|
| ✅ design | e1e36cc | pass | pl_a2dd7ccc_design.md |
| ✅ review | 3991ee0 | PASS (4 must-fix) | pl_a2dd7ccc_review.md |
| ✅ develop_wt | 388ebdb | pass | test_reject_audit.py |
| ✅ verify | 8896317 | PASS (quality warning) | pl_a2dd7ccc_verify.md |
| ✅ develop_code (1) | 500edc6 | REJECT → 修复 | app_enhanced.py, dev_center.js, dev_center.css |
| ✅ develop_code (2) | 0268ba4 | PASS | 3 bugs fixed |
| ✅ audit | 87a5d4b | PASS | pl_a2dd7ccc_audit.md |
| ✅ deliver | — | 进行中 | pl_a2dd7ccc_deliver.md |

---

## 2. 代码改动总览

### 2.1 后端 API（app_enhanced.py）

| Route | Method | 功能 | 路径 |
|-------|--------|------|------|
| `/api/issues/:id` | PUT | 扩展 status=rejected（含驳回原因校验、24h冷却期、previous_status 保存） | 1300-1328 |
| `/api/requirements/:id` | PUT | **新增**—需求状态更新（含驳回） | 855-915 |
| `/api/audit-callback` | POST | **新增**—毒刺审计回调（仅 127.0.0.1，含 SSE 推送） | 920-995 |

### 2.2 前端交互（dev_center.js + dev_center.css）

| 功能 | 位置 | 说明 |
|------|------|------|
| Issue 驳回按钮 | dev_center.js:1343 | 仅 resolved/closed 显示 |
| 需求驳回按钮 | dev_center.js:1658 | 仅 done 显示，含标题行布局 |
| 驳回弹窗 | dev_center.js:1700-1755 | 动态创建，textContent 防 XSS |
| 提交驳回 | dev_center.js:1757-1787 | 异步 PUT 请求 + 刷新 |
| CSS 样式 | dev_center.css | .issue-btn-reject, .req-btn-reject, .req-title-row |

### 2.3 状态流转

```
Issue:
  resolved ─┬→ closed
             │
             └→ [驳回] → rejected(pending_audit)
                 ├─ audit_approved → in_progress (重新修复)
                 └─ audit_declined → resolved (恢复)

Requirement:
  done ─┬→ cancelled/timed_out/escalated
         │
         └→ [驳回] → rejected(pending_audit)
             ├─ audit_approved → develop_code (重新修复)
             └─ audit_declined → done (恢复)
```

### 2.4 安全措施

| 措施 | 说明 |
|------|------|
| 驳回原因非空校验 | 后端 + 前端双重检查，空值返回 400 |
| 24h 冷却期 | 同一需求/issue 24h 内仅允许驳回答一次，超频返回 429 |
| 回调 IP 鉴权 | `/api/audit-callback` 仅接受 127.0.0.1/::1/localhost |
| 审计状态防重入 | `audit_status != 'pending'` 时返回 409 |
| `previous_status` 顺序 | 先保存原状态再改为 rejected，确保可恢复 |
| `rejected_by` 服务端硬编码 | 设置为 'dashboard_user'，不信任客户端 |
| XSS 防护 | `escapeHtml` 补充单引号转义；弹窗使用 textContent |

---

## 3. 服务重启验证

### 3.1 改动类型

同时改了：
- **Python 后端** → app_enhanced.py
- **JS/HTML/CSS 前端** → dev_center.js, dev_center.css

需重启 **dashboard**。

### 3.2 执行重启

```bash
./scripts/zoo-service-restart
```

### 3.3 端到端验证

```bash
# Dashboard 运行状态
curl http://127.0.0.1:18792/api/system-info

# Issue PUT 驳回（404 验证路由可达）
curl -X PUT http://127.0.0.1:18792/api/issues/nonexistent \
  -H "Content-Type: application/json" \
  -d '{"status":"rejected","reject_reason":"test"}'

# Requirement PUT 驳回
curl -X PUT http://127.0.0.1:18792/api/requirements/nonexistent \
  -H "Content-Type: application/json" \
  -d '{"status":"rejected","reject_reason":"test"}'

# Audit 回调
curl -X POST http://127.0.0.1:18792/api/audit-callback \
  -H "Content-Type: application/json" \
  -d '{"target_id":"x","target_type":"issue","audit_result":"audit_approved"}'
```

---

## 4. 交付成果清单

| 文件 | 说明 |
|------|------|
| `framework/shared/pl_a2dd7ccc_design.md` | 设计文档 |
| `framework/shared/pl_a2dd7ccc_review.md` | 设计评审 |
| `framework/shared/pl_a2dd7ccc_verify.md` | 测试评审 |
| `framework/shared/pl_a2dd7ccc_audit.md` | 代码审计 |
| `framework/shared/pl_a2dd7ccc_deliver.md` | 交付报告 |
| `framework/tests/ut/test_reject_audit.py` | 测试套件（38 用例） |
| `dashboard/app_enhanced.py` | 后端（3 新路由 + 3 新方法） |
| `dashboard/static/dev_center.js` | 前端（驳回按钮 + 弹窗 + 提交） |
| `dashboard/static/dev_center.css` | 样式 |

---

## 5. 结论

**所有 8 个 phase 闭环，代码审计 PASS，服务已重启验证。**

- ✅ design → review → develop_wt → verify → develop_code → audit → deliver
- ✅ 3 个安全漏洞全部修复（previous_status order / XSS / rejected_by）
- ✅ 38/38 测试通过
- ✅ 3 个新路由可调用
- ✅ 驳回 → 审计 → 恢复/重开 全链路就绪

**交付通过。** 🐢
