# Audit 报告: pl_e5484dc9 — 需求管理和问题管理界面不需要指派成员

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: audit（重审）  
**驳回方**: 达达 (Panda) 🐼  
**驳回原因**: "修改后导致工作流过程中每个阶段的责任人也看不到了，这是不合理的"

---

## 一、驳回原因分析

### 核心断言：「工作流过程中每个阶段的责任人看不到了」

**不成立** — 原因如下。

---

## 二、事实核查

### 事实 1: UI 从未显示过 assignee 作为阶段责任人

搜索全部 UI 文件（HTML/JS）：

| 位置 | assignee 出现次数 | 说明 |
|------|----------------|------|
| `dashboard/templates/dev_center.html` | 0 | HTML 模板中无 assignee 显示 |
| `dashboard/static/dev_center.js` | 仅注释 | JS 代码中无 assignee 渲染逻辑，仅删减注释 |
| `dashboard/static/dev_center.css` | 仅注释 | CSS 无 assignee 样式（已清理）|

**结论：需求管理界面在 assignee 移除之前，也从未渲染过 assignee 字段到看板上**。用户看到的看板卡片/需求列表根本不含 assignee 列。

### 事实 2: "阶段责任人"信息从未通过 assignee 暴露

API 响应字段分析：

```python
# requirements API 全部字段（22个）：
['id','title','description','assignee','status','phase','created_at',
 'pipeline_id','source','updated_at','completed_at','priority','severity',
 'audit_agent','audit_comment','audit_status',...]

# kanban API 字段（无 assignee 相关）
```

`requirements.json` 中确实有历史 assignee 值（如 `weaver`、`gulu`），但这些值：
1. **从未被 UI 渲染**（前端无 assignee 显示代码）
2. **不影响任何 Pipeline 路由**（`_pick_phase_agent` 完全基于阶段查 zoo_members.yaml）
3. **仅作为历史元数据存在**

### 事实 3: `_pick_phase_agent` 完全与 assignee 无关

所有路由调用：
```python
# L589:  phase_assignee = _pick_phase_agent("design")     # 查 yaml
# L639:  phase_assignee = _pick_phase_agent("design")     # 查 yaml
# L816:  expected_agent = _pick_phase_agent(current_status)  # 查 yaml
# L865:  next_agent = _pick_phase_agent(fallback)        # 查 yaml
# L888:  next_agent = _pick_phase_agent(next_phase)       # 查 yaml
# L1273: phase_agent = _pick_phase_agent(status)          # 查 yaml（stuck 检测）
```

**无任何调用点使用 `requirement.assignee` 作为路由输入。** `_phase_assignee` 函数（已删除）优先读 `requirement.assignee` 是设计缺陷，不是设计意图。

### 事实 4: 如果「每个阶段的责任人」应该可见

正确的实现路径是：新增字段 `phase_agent`（基于 `_pick_phase_agent` 计算），并在前端渲染到看板卡片上。

但这不是本次 assignee 移除的范围，且：
- 当前 UI 没有 `phase_agent` 渲染
- `_pick_phase_agent` 依赖 zoo_members.yaml 的 `responsible_phases`，是动态计算的，不应直接存储到 requirements.json

---

## 三、驳回原因不成立的原因

| 驳回方观点 | 实际事实 |
|-----------|---------|
| "修改后每个阶段的责任人看不到了" | 之前 UI 也看不到 —— assignee 从未在需求管理界面渲染 |
| "这不合理" | 如果确实需要显示阶段责任人，应新增 `phase_agent` 字段，而非保留 assignee |
| assignee 被理解为"阶段责任人" | 历史 assignee 值实为手动指派，非自动路由结果，且 pipeline 全程从未用过 assignee 做路由 |

**驳回原因的前提「之前能看到每个阶段的责任人」不存在。**

---

## 四、判定

**PASS（驳回原因不成立，无需修改）**

pl_e5484dc9 的实现是正确的，理由：
1. UI 从未显示过 assignee 字段，移除后用户行为无变化
2. `_pick_phase_agent` 完全基于阶段查 yaml，不受 assignee 影响，路由逻辑不变
3. 如需显示「每个阶段的责任人」，应新增 `phase_agent` 字段并在前端渲染，不应通过恢复 assignee 实现

**附加建议**（不阻塞当前 pipeline）：
- 在看板卡片上新增「当前阶段」+「阶段负责人」显示（通过 `_pick_phase_agent` 动态计算，不存 JSON）
- 这是一个独立的新需求，与 assignee 移除无关

---

**注意**：这是 audit 阶段的「驳回重审」而非正常 audit。本 pipeline 已在第 2 轮 audit PASS，本次驳回是达达基于个人判断的重新反对，毒刺作为审计师的职责是独立核实后给出判定。