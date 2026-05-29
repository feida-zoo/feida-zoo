# Audit 报告: pl_e5484dc9 — 需求管理和问题管理界面不需要指派成员（第 2 次驳回重审）

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: audit（驳回重审）  
**驳回方**: 达达 (Panda) 🐼  
**驳回原因**: "在每个阶段需要有对应的处理人，比如设计中-alpha，验收中-duci，不要硬编码，而是从配置文件里读出来的每个阶段的处理人"

---

## 一、驳回原因分析

### 驳回方诉求：每个阶段需要有对应的处理人，从配置文件读取，不要硬编码

这个诉求**完全正确，而且已经实现了**。

---

## 二、事实核查：`_pick_phase_agent` 正是为此设计

### 当前实现（zoo_mesh_daemon.py L442-448）

```python
def _pick_phase_agent(phase: str) -> str:
    """从 zoo_members.yaml 的 responsible_phases 反向推导。
    未匹配阶段 → 返回 'panda'（全局 fallback）。"""
    from framework.core.mesh.zoo_registry import ZooRegistry
    return ZooRegistry().get_phase_agent(phase)
```

### ZooRegistry.get_phase_agent（zoo_registry.py L303）

```python
def get_phase_agent(self, phase: str) -> str:
    """Maps phase name → responsible agent from YAML responsible_phases."""
```

通过 `zoo_members.yaml` 的 `responsible_phases` 字段，**完全从配置文件读取**，无硬编码。

### zoo_members.yaml 当前配置

```yaml
alpha:
  responsible_phases:
    - design
    - develop_wt
    - develop_code
    - deliver

duci:
  responsible_phases:
    - review
    - verify
    - audit

panda:
  responsible_phases: []
  # 全局 fallback
```

**驳回方期望的「设计中-alpha，验收中-duci」正是当前的配置结果。**

---

## 三、驳回原因不成立

| 驳回方观点 | 实际事实 |
|-----------|---------|
| "每个阶段需要处理人" | ✅ `_pick_phase_agent("design")` → `alpha` |
| "不要硬编码" | ✅ 查 `responsible_phases` YAML 配置，动态计算 |
| "从配置文件读" | ✅ `zoo_members.yaml`，单文件权威来源 |

**驳回方诉求已满足，且与 assignee 是两个完全正交的概念：**

- **`phase_agent`**：阶段 → 默认处理人，由 ZooRegistry 查 YAML 动态计算，**自动路由**
- **`requirement.assignee`**：需求 → 手动指派，**干扰自动路由**（设计缺陷）

---

## 四、如果驳回方的真实诉求是「UI 显示阶段处理人」

这是**独立的新需求**，与 assignee 移除无关：

1. **当前 UI 不显示 `phase_agent`** — 看板上没有「阶段处理人」列
2. **需要做的事**：在 `requirements.json` 中新增 `phase_agent` 字段（或 `current_phase_agent`），在 `_do_phase_complete_callback` 时写入，然后在 UI 渲染

但这是新功能开发，不是 assignee 移除的修复范围。

---

## 五、判定

**PASS（驳回原因不成立，无需修改）**

`_pick_phase_agent` 已完全实现「从配置文件读取每个阶段的处理人」：
- design → alpha（YAML 配置）
- review/verify/audit → duci（YAML 配置）
- 其他阶段 → panda（YAML fallback）
- 无硬编码，查 ZooRegistry → zoo_members.yaml

pl_e5484dc9 正确执行了 assignee 移除，驳回方诉求的功能早已存在（仅未在 UI 显示）。

**附加建议**（不阻塞）：如需在看板上显示阶段处理人，这是独立需求，建议开新 pipeline。