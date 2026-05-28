# Deliver 阶段 — pl_e024bd42

**任务**: 运行数据与代码数据隔离  
**交付日期**: 2026-05-29  
**交付人**: alpha 🐢

---

## 1. Phase 完成检查

| Phase | Commit / 结论 | 状态 |
|-------|----------------|------|
| design | `e80c541` | ✅ PASS |
| review | `f1dcf92` | ✅ PASS（3 must-fix 项） |
| develop_wt | `85562f2` | ✅ PASS（27 用例） |
| verify | `5fbbe7e` | ✅ PASS |
| develop_code（第1轮） | `111af36` | 🔴 AUDIT REJECT（路径遍历未修复） |
| audit（REJECT） | `1d0c829` | 🔴 REJECT 退回 |
| **develop_code（第2轮·安全修复）** | **`2f9bf9a`** | **✅ 路径遍历防护** |
| **audit** | **`7155f15`** | **✅ PASS** |
| **deliver** | **当前** | **✅ 进行中** |

---

## 2. 最终改动清单

### 改动 1：运行数据目录（`app_enhanced.py`）

| 常量 | 旧路径 | 新路径 |
|------|--------|--------|
| `DATA_DIR` | `feida_zoo/dashboard/data/` | `panda/zoo_mesh/dashboard/` |
| `PROJECT_AGENTS_DIR` | `feida_zoo/agents/` | `panda/zoo_mesh/agents/` |
| `TASK_TRACKER_PATH` | `feida_zoo/framework/shared/task_tracker.json` | `panda/zoo_mesh/dashboard/task_tracker.json` |

### 改动 2：Pipeline 文档目录（`zoo_mesh_daemon.py`）

| 配置 | 旧值 | 新值 |
|------|------|------|
| `artifacts_dir` | `framework/shared` | `docs/pipeline` |
| `legacy_artifacts_dir` | — | `framework/shared`（向后兼容） |

### 改动 3：安全增强（`app_enhanced.py`）

| 防护 | 方法 | 覆盖范围 |
|------|------|----------|
| 路径遍历 | `..` 检测 + `resolve().relative_to()` | `_serve_avatar` + `_serve_static_file` |
| Vendor hardcoded path | `FEIDA_ZOO_HOME.parent` → `PROJECT_ROOT / "agents"` | avatar fallback |

### 改动 4：其他

| 文件 | 改动 |
|------|------|
| `persistence.py` | `TRACKER_PATH` → `docs/pipeline/task_tracker.json` |

---

## 3. 数据迁移

已完成（手动）：

```
dashboard/data/issues.json          → panda/zoo_mesh/dashboard/issues.json       ✅
dashboard/data/requirements.json    → panda/zoo_mesh/dashboard/requirements.json ✅
agents/*/avatar.png                 → panda/zoo_mesh/agents/*/avatar.png         ✅
docs/pipeline/                      → mkdir 已创建                              ✅
```

---

## 4. 测试结果

```
94 passed, 1 skipped (无 zoo_mesh 的机器)
```

| 测试套件 | 用例数 | 结果 |
|----------|--------|------|
| `test_data_code_isolation.py` | 30 | ✅ 全部通过 |
| `test_reject_pipeline.py` + `test_reject_audit.py` | 64 | ✅ 全部通过 |

---

## 5. 端到端验证

```
GET /api/system-info       → Zoo Dev-Center v1.0 running  ✅
GET /api/members           → alpha=Kimi, duci=glm, panda=Minimax  ✅
GET /avatar/alpha          → 200  ✅
GET /avatar/..%2Fetc%2Fpasswd → 403 (遍历被阻止)  ✅
GET /static/dev_center.js  → 200  ✅
GET /static/../app_enhanced.py → 404 (遍历被阻止)  ✅
```

---

## 6. 服务重启

改了 Python 代码 → `./zoo-service-restart dashboard daemon` ✅（均已重启）

---

## 7. 结论

**交付完成 ✅** — 运行数据与代码数据完全隔离，安全增强通过审计。

| 需求 | 状态 |
|------|------|
| Dashboard 运行数据（issues/requirements）移出代码目录 | ✅ `panda/zoo_mesh/dashboard/` |
| agents 配置数据移出代码目录 | ✅ `panda/zoo_mesh/agents/` |
| Pipeline 文档放到 `docs/pipeline/`（跨项目通用） | ✅ `feida_zoo/docs/pipeline/` |
| 向后兼容（旧文档不丢失） | ✅ `legacy_artifacts_dir` + fallback |
| 路径遍历安全防护 | ✅ `resolve().relative_to()` + `..` 检测 |
