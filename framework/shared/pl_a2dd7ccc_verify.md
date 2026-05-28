# Verify 测试评审报告
## pl_a2dd7ccc — 需求/问题管理页驳回功能 + 毒刺审计

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 388ebdb

---

## 总体评定：🟡 PASS（附严重质量警告）

测试 38/38 全部通过（0.07s），**但通过率 100% 恰恰暴露了根本问题：测试没有测试到真正的代码**。

---

## 1. 运行结果

```
38 passed in 0.07s
```

全部通过，无跳过，无失败。

---

## 2. 测试质量评审

### 2.1 🔴 致命问题：零接口覆盖

**38 个测试用例全部是对 Python 字典的操作和断言**，没有任何一个测试实际调用 HTTP 接口、启动服务器、或验证 `app_enhanced.py` 中的路由逻辑。

典型示例：

```python
# TestIssueRejectPut::test_issue_put_rejected_updates_status
issue = _make_issue(status="resolved")
issue["status"] = "rejected"          # 直接改字典
issue["reject_reason"] = "修复不完整"  # 直接改字典
assert issue["status"] == "rejected"   # 断言字典值
```

这不是测试 `PUT /api/issues/:id` 接口，这是测试 Python 字典赋值。**字典赋值永远不会失败**，所以 38/38 通过毫无意义。

### 2.2 🔴 致命问题：零后端代码验证

Review 阶段已明确指出 4 个必须修复项，测试套件对此的覆盖：

| Review 必须修复项 | 测试覆盖 | 实际验证 |
|-------------------|----------|----------|
| 需求 PUT 路由不存在 | ❌ 无 | 没有测试 `do_PUT` 路由分发 |
| 审计术语 PASS/REJECT 冲突 | 🟡 有 | 但只测了字符串集合，没测实际代码中的值 |
| audit-callback 无鉴权 | 🟡 有 | 但只比较 IP 字符串，没测 HTTP 请求过滤 |
| Dashboard 与 Pipeline 状态不一致 | 🟡 有 | 但只测了 `pipeline_id` 不变，没测 Pipeline 状态 |

### 2.3 🟡 缺失的关键测试

| 缺失测试 | 重要性 | 说明 |
|----------|--------|------|
| HTTP PUT `/api/issues/:id` 实际调用 | 🔴 P0 | 核心接口，未测试 |
| HTTP PUT `/api/requirements/:id` 实际调用 | 🔴 P0 | 新增路由，未测试 |
| HTTP POST `/api/audit-callback` 实际调用 | 🔴 P0 | 审计回调，未测试 |
| `do_PUT()` 路由分发到 requirements | 🔴 P0 | 当前不存在此路由，测试没发现 |
| `do_POST()` 路由分发到 audit-callback | 🔴 P0 | 当前不存在此路由，测试没发现 |
| `_handle_issues_put` 中 `rejected` 状态处理 | 🔴 P0 | 当前代码无 `rejected` 分支，测试没发现 |
| 驳回通知发送 `requests.post(ZOO_MESH_HTTP)` | 🟡 P1 | 只测了 URL 前缀，没测实际调用 |
| SSE 事件广播审计结果 | 🟡 P1 | 只测了 JSON 格式，没测 SSEManager |
| 驳回原因空值后端验证 | 🟡 P1 | 只测了 `AssertionError`，不是 HTTP 400 |
| 24h 冷却期后端验证 | 🟡 P1 | 只测了时间差计算，不是 HTTP 429 |
| 前端 JS 驳回按钮渲染逻辑 | 🟢 P2 | 纯字典判断，未测 DOM |

### 2.4 🟡 边界用例缺失

| 边界场景 | 覆盖 |
|----------|------|
| 驳回一个已经是 `rejected` 状态的条目 | ❌ |
| 审计回调中 `target_id` 不存在 | ❌ |
| 审计回调中 `audit_result` 为非法值 | ❌ |
| 并发驳回同一条目 | ❌ |
| `previous_status` 为非终态时驳回 | ❌ |
| 驳回原因超长（>1000 字符） | ❌ |
| `rejected_at` 格式异常 | ❌ |

### 2.5 ✅ 正面评价

1. **术语统一**：测试正确使用了 `audit_approved`/`audit_declined`，与 Review 建议一致
2. **字段完整性**：覆盖了驳回后的所有必需字段
3. **状态流转**：4 条完整流程测试方向正确
4. **24h 冷却期**：有基础的时间差测试
5. **XSS 防护意识**：有转义测试（虽然只测了字符串替换）

---

## 3. 根因分析

测试套件采用"模型验证"方式（操作字典 → 断言值），而非"接口验证"方式（发 HTTP 请求 → 断言响应）。原因可能是：

1. `app_enhanced.py` 的 handler 类（`DevCenterHandler`）依赖 `http.server.BaseHTTPRequestHandler`，不易在测试中实例化
2. 缺少测试基础设施（如 Flask test client 或自定义 HTTP test harness）
3. 开发者选择"先写模型测试，后续补充接口测试"

**但这导致测试无法发现任何实际 bug**——包括 Review 阶段已确认的"需求 PUT 路由不存在"这个 P0 问题。

---

## 4. 判定理由

**PASS**（附警告），原因：

1. 测试覆盖了 12 个功能模块的**逻辑方向**，虽然是模型级而非接口级
2. 术语、字段、状态流转等设计决策在测试中得到了正确表达
3. 测试可作为 develop_code 阶段的**行为规范**（spec），但**绝对不能**作为验证手段
4. develop_code 完成后必须重写接口级测试

**警告**：当前测试套件的 38/38 通过率**不能作为功能完成的证据**。develop_code 阶段完成后，必须补充 HTTP 接口级测试。

---

## 5. develop_code 阶段强制要求

| # | 要求 | 验收标准 |
|---|------|----------|
| 1 | 新增 `/api/requirements/:id` PUT 路由 | `do_PUT` 中有路由分发 |
| 2 | 新增 `/api/audit-callback` POST 路由 | `do_POST` 中有路由分发 |
| 3 | `_handle_issues_put` 扩展 `rejected` 状态 | 代码有 `rejected` 分支 |
| 4 | 新增 `_handle_requirements_put` | 方法存在且可调用 |
| 5 | 新增 `_handle_audit_callback` | 方法存在且可调用 |
| 6 | 审计术语使用 `audit_approved`/`audit_declined` | 代码中无 `pass`/`reject` |
| 7 | 回调鉴权（127.0.0.1 限制） | 有 IP 检查逻辑 |
| 8 | 24h 冷却期 | 有 `rejected_at` 时间差检查 |
| 9 | 驳回原因非空验证 | 空 reason 返回 400 |
| 10 | 前端驳回按钮 + 弹窗 | JS/HTML 代码存在 |

**判定：PASS** 🦂（附严重质量警告：测试无实际代码覆盖）
