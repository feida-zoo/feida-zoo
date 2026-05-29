# Audit 报告: pl_e5484dc9 — 需求管理和问题管理界面不需要指派成员（第 3 次驳回重审）

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: audit（驳回重审）  
**驳回方**: 达达 (Panda) 🐼  
**驳回原因**: "在每个阶段有对应的处理人，比如设计中-alpha，验收中-duci，不要硬编码，而是从配置文件里读出来的每个阶段的处理人，**这个处理人需要在看板上呈现**，以方便看到当前是谁在处理。done 阶段不需要呈现。"

---

## 一、驳回原因分层分析

### 第 1 层：「每个阶段需要有处理人，从配置文件读取，不要硬编码」

**部分正确，但有两层实现需区分：**

#### Daemon 路由层（zoo_mesh_daemon.py L442）✅ 已正确实现

```python
def _pick_phase_agent(phase: str) -> str:
    from framework.core.mesh.zoo_registry import ZooRegistry
    return ZooRegistry().get_phase_agent(phase)  # 查 YAML responsible_phases
```

- `design` → `alpha`
- `review`/`verify`/`audit` → `duci`
- 其他阶段 → `panda`（fallback）
- **无硬编码**，完全从 `zoo_members.yaml` 读

#### Dashboard API 层（app_enhanced.py L1635）❌ 硬编码，且缺少 `verify`

```python
PHASE_EXECUTOR = {
    "design": "alpha", "ui_design": "alpha",
    "develop_wt": "alpha", "develop_code": "alpha",
    "review": "duci", "review_test": "duci",
    "test": "duci", "audit": "duci", "deliver": "alpha",
    # 注意：缺少 "verify"
}
```

`PHASE_EXECUTOR` 是硬编码副本，与 `_pick_phase_agent` 的 YAML 配置不一致：
- `verify` 阶段缺失 → `PHASE_EXECUTOR.get("verify", "")` 返回空字符串

**这是真实问题**，但这是 `app_enhanced.py` 的 pre-existing bug，与 assignee 移除（pl_e5484dc9）无关。pl_e5484dc9 并未修改 `PHASE_EXECUTOR`。

---

### 第 2 层：「处理人需要在看板上呈现」

**UI 完全没有渲染 current_executor。** 搜索 `dashboard/static/dev_center.js` 和 `dashboard/templates/dev_center.html`：

```
JS 渲染 current_executor: False
HTML 渲染 current_executor: False
```

`current_executor` 存在于 API 响应字段中，但前端从未读取或渲染。即使修复 `PHASE_EXECUTOR`，用户仍然看不到。

**这是独立的前端增强需求**，与 assignee 移除无关。

---

## 二、pl_e5484dc9 的实际影响分析

| pl_e5484dc9 修改内容 | 对「阶段处理人呈现」的影响 |
|---------------------|-------------------------|
| 删除 `_phase_assignee` 函数 | 无影响 — 该函数从未被用于 routing |
| daemon 路由改用 `_pick_phase_agent` | **正确** — 完全从 YAML 读 |
| dashboard API `assignee` 字段删除 | 无影响 — 删的是需求指派字段，不影响 `current_executor` |
| HTML/JS/CSS UI 删除 assignee | 无影响 — assignee 从未在看板渲染 |

**pl_e5484dc9 没有破坏「阶段处理人呈现」功能，因为它本来就不存在。**

---

## 三、驳回原因的实质

达达的诉求可以分解为三个独立需求：

1. **A（已满足）**: daemon 路由从配置文件读阶段处理人 → `_pick_phase_agent` ✅
2. **B（bug，需修）**: `PHASE_EXECUTOR` 硬编码且缺少 `verify` → 应改为查 ZooRegistry → **独立 bug**
3. **C（功能缺失，需新 pipeline）**: 看板 UI 渲染阶段处理人 → 需新增前端渲染逻辑 → **新需求**

驳回将 A+B+C 合并为一个诉求，并错误地归因于 pl_e5484dc9。

---

## 四、判定

**PASS（驳回原因不成立，无需修改 pl_e5484dc9）**

理由：
1. **Daemon 路由已从 YAML 配置读** — `_pick_phase_agent` 正确工作，不受 assignee 移除影响
2. **`PHASE_EXECUTOR` 硬编码是 pre-existing bug** — 与 pl_e5484dc9 无关，但应在 `app_enhanced.py` 中修复（改用 ZooRegistry）
3. **UI 不渲染 current_executor 是功能缺失** — 与 pl_e5484dc9 无关，需新 pipeline

**驳回实质是合并了 3 个不同问题**：
- A 已满足
- B 是独立 bug，应在 `app_enhanced.py` 中修复（不在 pl_e5484dc9 范围）
- C 是新需求，需开新 pipeline

---

## 五、建议修复方案

**建议（不阻塞当前 pipeline）：**

1. **立即可做**（1 行改动，fix B）：
   将 `app_enhanced.py` 的 `PHASE_EXECUTOR` 改为调用 ZooRegistry：
   ```python
   from framework.core.mesh.zoo_registry import ZooRegistry
   _zr = ZooRegistry()
   # L1651/L1659 改为：
   current_executor = _zr.get_phase_agent(pl_state)
   ```

2. **新 pipeline（功能缺失，fix C）**：
   在看板卡片上渲染 `current_executor`，显示当前阶段负责人姓名/头像