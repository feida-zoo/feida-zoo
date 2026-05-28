# Deliver 最终验收交付
## pl_b9a4d0e1 — 驳回已解决的问题后未触发 Pipeline

**交付人**: Alpha 🐢 | **日期**: 2026-05-28 | **上游 commit**: 1684c90

---

## 1. 交付检查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| ✅ Design 完成 | DONE | `ea1671d` — 架构设计+UI设计+执行计划 |
| ✅ Review 完成 | PASS | 2 个 must-fix 均已纳入 develop_code 实现 |
| ✅ Develop WT 完成 | DONE `1320f0c` | 26 用例，9 个测试类 |
| ✅ Verify 完成 | PASS | 26/26 pass（附质量警告） |
| ✅ Develop Code 完成 | DONE `7fd810d` | `_dispatch_pipeline` 实现 + `_handle_issues_post` 重构 |
| ✅ Audit 完成 | PASS | 2 个 Review must-fix 全确认 |
| ✅ 工作树干净 | CLEAN | 无未提交改动 |
| ✅ 服务重启 | RESTARTED | Dashboard 已验证 |

---

## 2. 最终实现概览

### 核心改动：`_dispatch_pipeline` 公共方法

```python
def _dispatch_pipeline(self, target, target_type, source) -> dict:
```

**被调用于：**

| 调用点 | 状态 | 说明 |
|--------|------|------|
| `_handle_issues_post` | 新建 issue → 首次 Pipeline | 重构消除 33 行重复代码 |
| `_handle_audit_callback` issue audit_approved | **🎯 本 Pipeline 目标** — 驳回审计通过后创建新 Pipeline | 存入 `reject_pipeline_id` |
| `_handle_audit_callback` requirement audit_approved | Review must-fix 1 — Requirement 驳回也触发 Pipeline | 存入 `reject_pipeline_id` |

### 文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `dashboard/app_enhanced.py` | 修改 | +70/-33 行 — 新增 `_dispatch_pipeline` + 3 处调用 |
| `framework/tests/ut/test_reject_pipeline.py` | 新增 | 483 行，26 用例 — pl_b9a4d0e1 测试套件 |

### 安全与防护

| 机制 | 说明 |
|------|------|
| ✅ 重复 Pipeline 防护 | `reject_pipeline_id` 存在时返回 `skip_duplicate` |
| ✅ 原始 pipeline_id 保留 | 新 ID 存放于 `reject_pipeline_id`，不覆盖 |
| ✅ payload `[驳回重开]` 前缀 | 驳回重开场景特有明显标识 |
| ✅ 推送失败降级 | `requests.post` 超时/异常时返回 `push_failed`，不影响数据状态 |
| ✅ 调用方负责持久化 | `_dispatch_pipeline` 仅返回结果不写数据 |

---

## 3. 端到端验证

### 3.1 服务健康

```
Dashboard: Zoo Dev-Center v1.0 running  ✅
Daemon health: OK                        ✅
```

### 3.2 路由可达性

| 端点 | 预期 | 结果 |
|------|------|------|
| `GET /api/system-info` | 200 + status | ✅ |
| `POST /api/issues` | 新建 issue + Pipeline | ✅（测试 64/64 pass） |
| `POST /api/audit-callback` | 审计回调 + Pipeline 创建 | ✅（路由验证通过） |
| `PUT /api/issues/:id` | 驳回 issue | ✅（来自 pl_a2dd7ccc） |
| `PUT /api/requirements/:id` | 驳回 requirement | ✅ |

### 3.3 测试

```
64 passed (reject_pipeline 26 + reject_audit 38)  ✅
Python syntax OK                                     ✅
```

---

## 4. 交付声明

需求 "驳回已解决的 issue 后未触发 pipeline" 已修复。

**实现后流程：**
```
resolved → rejected (pending audit)
                    ↓ Duci 审计通过
              audit_approved
                    ↓
              in_progress + 新 Pipeline → Panda → 开发流转
                    ↓
              开发者看到 [驳回重开] 任务，开始修复
```

---

*交付版本: v1.0 | Alpha 🐢 | 2026-05-28*
