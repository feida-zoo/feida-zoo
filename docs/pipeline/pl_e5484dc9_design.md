# Design 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」（第 2 版）

**阶段**: design  
**设计人**: 阿尔法 (Alpha) 🐢  
**日期**: 2026-05-29  
**版本**: v2 — 按 review REJECT 全面补充  

---

## 一、需求评审

### 1.1 问题陈述
1. 需求和问题是 Pipeline 自动派发的，新建时指派成员没有意义
2. 完成后所有需求/问题都挂在阿尔法名下（dev 阶段执行者），assignee 字段失真
3. 建议直接删除 assignee 界面元素和相关逻辑

### 1.2 可行性评估 ✅
- **可行**: 仅删除 UI 字段和无关路由依赖，不破坏 Pipeline 核心
- **依赖**: `_phase_assignee` / `_pick_phase_agent` / `stuck 检测` 三处需改为纯自动路由
- **风险**: 低
- **优先级**: P1（界面整洁/语义正确性）

### 1.3 需求合理性判定
**判定: 合理** ✅

---

## 二、架构设计

### 2.1 What — 改动总览

| # | 位置 | 改动内容 | 优先级 |
|---|------|----------|--------|
| 1 | `dashboard/templates/dev_center.html` | 删除需求表单和问题表单的 assignee 下拉框 | P1 |
| 2 | `dashboard/static/dev_center.js` | 删除 assignee 相关的表单读取、看板显示、任务详情 | P1 |
| 3 | `dashboard/static/dev_center.css` | 删除 `.task-assignee` / `.assignee-avatar` 等死类 | P2 |
| 4 | `dashboard/app_enhanced.py` | 删除 assignee 表单处理、通知、响应体 | P1 |
| 5 | `framework/core/mesh/zoo_mesh_daemon.py` | 删除 `_phase_assignee` 函数，全量替换为 `_pick_phase_agent` | P0 |
| 6 | `framework/core/mesh/zoo_mesh_daemon.py` | L602：创建 pipeline 时不从 payload 读 assignee | P1 |
| 7 | `framework/core/mesh/zoo_mesh_daemon.py` | L624-625：停止向 requirement 写入 assignee | P1 |
| 8 | `framework/core/mesh/zoo_mesh_daemon.py` | L638：创建 JSON 不含 assignee | P1 |
| 9 | `framework/core/mesh/zoo_mesh_daemon.py` | L884/L909：驳回/推进路由移除 `cur_req.get("assignee")` 兜底 | P1 |
| 10 | `framework/core/mesh/zoo_mesh_daemon.py` | L1421：stuck 检测移除 `req.get("assignee", "")` 兜底 | P2 |
| 11 | `dashboard/test_p0_pipeline_push.py` | 删除测试中 `assignee` 参数 | P2 |
| 12 | `dashboard/test_priority_sort.py` | 删除测试中硬编码 `assignee` | P2 |

### 2.2 Why

**核心矛盾**: `_phase_assignee` 优先读 `requirement.assignee`（用户填写）→ 用户填的总和实际执行者不一致 → 数据污染。

**修复后数据流**:
```
需求创建 → Pipeline 启动 → _pick_phase_agent(phase) → 纯自动路由
                                                            ↓
                                          根据 zoo_members.yaml 的 responsible_phases
                                          选择正确 Agent
```

### 2.3 详细改动说明

#### #5: `_phase_assignee` 函数 → 删除

```python
# 删除此函数
def _phase_assignee(phase, requirement):
    assignee = requirement.get("assignee", "")
    if assignee:
        return assignee
    return ZooRegistry().get_phase_agent(phase)

# 所有调用点替换为:
ZooRegistry().get_phase_agent(phase)
```

#### #9: L884/L909 — 路由兜底改为纯自动

```python
# 当前（受影响）:
next_agent = cur_req.get("assignee") or _pick_phase_agent(fallback)

# 改为:
next_agent = _pick_phase_agent(fallback)
```

#### #10: L1421 — stuck 检测

```python
# 当前:
assignee = phase_agent or req.get("assignee", "")

# 改为:
assignee = phase_agent or "panda"
```

#### #6: L602 — 创建 pipeline 时

```python
# 当前:
assignee = payload.get("assignee") or _pick_phase_agent("design")

# 改为:
phase_assignee = _pick_phase_agent("design")
```

#### #7: L624-625 — 停止写入 requirement

```python
# 删除:
if not cur_req.get("assignee"):
    cur_req["assignee"] = assignee
```

#### #14: SSE 通知中的 assignee

```python
# 删除 app_enhanced.py L743-750:
# 通知 assignee 的逻辑（整个 if 块）:
if assignee and assignee != 'panda':
    ...
```

### 2.4 Tradeoff

| 选项 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 保留 `_phase_assignee` 但改空 | 函数名保留 | 和 `_pick_phase_agent` 重复 | ❌ |
| 删除 `_phase_assignee`（✅） | 无重复 | 需改 5 个调用点 | ✅ |
| 保留 L884/L909 的 assignee 兜底 | 兼容历史数据 | assignee 字段继续干扰路由 | ❌ |
| 强制纯自动路由（✅） | 路由准确 | 历史数据的 assignee 无视（保留不删） | ✅ |

### 2.5 文件清单

| 文件 | 操作 | 改动量估计 |
|------|------|-----------|
| `dashboard/templates/dev_center.html` | 修改 | ~4 行删除 |
| `dashboard/static/dev_center.js` | 修改 | ~30 行删除 |
| `dashboard/static/dev_center.css` | 修改 | ~15 行删除 |
| `dashboard/app_enhanced.py` | 修改 | ~20 行删除 |
| `framework/core/mesh/zoo_mesh_daemon.py` | 修改 | ~8 处修改 |
| `dashboard/test_p0_pipeline_push.py` | 修改 | ~2 行修改 |
| `dashboard/test_priority_sort.py` | 修改 | ~2 行修改 |

---

## 三、UI 设计

### 3.1 删除内容（需求表单）

```
当前:                         删除后:
┌─ 创建新需求 ──────┐         ┌─ 创建新需求 ──────┐
│ 标题            │         │ 标题            │
│ 描述            │         │ 描述            │
│ 优先级          │         │ 优先级          │
│ 指派给 [删除] ✂️  │         │ [提交需求]       │
│ [提交需求]       │         └──────────────────┘
└──────────────────┘
```

### 3.2 删除内容（问题表单）

```
当前:                         删除后:
┌─ 创建问题 ────────┐         ┌─ 创建问题 ────────┐
│ 标题            │         │ 标题            │
│ 描述            │         │ 描述            │
│ 优先级          │         │ 优先级          │
│ 指派给 [删除] ✂️  │         │ [创建问题]       │
│ [创建问题]       │         └──────────────────┘
└───────────────────┘
```

### 3.3 删除内容（看板详情中的 assignee）

看板 item 当前显示 `<span class="detail-value">🐢 alpha</span>` → 删除

### 3.4 删除内容（问题列表中的 assignee）

问题列表当前显示 `<span class="issue-assignee"><i class="fas fa-user"></i> 🐢 阿尔法</span>` → 删除

### 3.5 看板创建需求的下拉框

`request-assignee-select`（JS L684, L1588-1601）→ 同步删除

### 3.6 不受影响

- `_pending_queue` 中的 assignee 字段（是阶段执行者，语义不同，保留）
- requirements.json 历史 assignee 值（保留不删）

---

## 四、实施步骤

1. 先改 `zoo_mesh_daemon.py`（最核心）
2. 再改 `app_enhanced.py`
3. 再改 HTML + JS + CSS
4. 再改测试文件
5. 重启服务和验证
