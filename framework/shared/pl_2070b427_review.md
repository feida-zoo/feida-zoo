# Review Report — pl_2070b427

**Task**: 成员管理界面人数不对  
**Requirement**: 6587c35b-17d0-4361-bae4-5e04ecea31fa  
**Reviewer**: Duci (🦂)  
**Date**: 2026-05-26  
**Input**: `pl_2070b427_design.md` + `pl_2070b427_ui_design.md` + source code

---

## 架构合理性：✅ 通过

**设计选择合理。** 后端过滤而非前端过滤，数据权威源在 `zoo_members.yaml`，过滤逻辑在展示层（`_get_member_data()`），ZooRegistry 保持完整性——符合单一权威源原则。

**默认值设计正确。** 无 `metadata.status` 字段的成员默认视为 `"active"` 不跳过——对新增成员是安全的，不会误杀。

**方案优先级合理。** 路径 A（后端过滤）作为核心方案，路径 D（非活跃折叠区）作为可选增强——单次修改最小回归面，完工性补充可后期迭代。

---

## 安全风险：✅ 低风险

**无安全性问题。** 这是一个数据过滤 bug，不涉及权限、认证、输入验证或数据泄露。

**API 响应变化安全。** `GET /api/members` 减少返回条目，不涉及敏感信息泄漏。

**无注入风险。** 过滤基于 YAML 中已存在的布尔值字段，不涉及用户输入。

---

## 遗漏检查（关键发现）

### 🔴 Issue 1：Fallback 路径缺少相同的 status 过滤

**位置**: `_get_member_data()` L1208~L1240（ZooRegistry 异常时的 fallback 分支）

**问题**: fallback 直接遍历 `members_data.items()`，没有 `metadata.status == "active"` 过滤。若 ZooRegistry 抛出异常，fallback 会返回全部 6 个成员（包括 inactive），重新触发原 bug。

```python
# fallback 路径（当前）
for member_id, info in members_data.items():
    # 缺少: if info.get("metadata", {}).get("status") != "active": continue
```

**修复建议**: 在 fallback 的 for 循环内加入相同的 status 检查：
```python
meta = info.get("metadata", {}) or {}
mstatus = meta.get("status", "active") if isinstance(meta, dict) else "active"
if mstatus != "active":
    continue
```

**严重程度**: 高 — 这是原 bug 在 fallback 路径的复现

---

### 🟡 Issue 2：`_update_status()` 未跳过 inactive 成员

**位置**: `MemberStatusManager._update_status()` L225

**问题**: 状态监控轮询所有 6 个成员（包括 inactive），每个成员调用一次 `pgrep -f openclaw.*<member_id>`。对 inactive 成员重复检查无意义的进程，浪费资源（每次 ~3s timeout × 3 个 inactive = 9s/轮询周期）。

**当前行为**: 
```python
for member_id in agent_ids:  # 包含 panda/alpha/duci/weaver/aeterna/gulu
    new_status[member_id] = self._detect_member_active_status(member_id)
    # inactive 成员的进程检测必然失败（进程不存在）
```

**修复建议**: 在 `_update_status()` 的 for 循环中加入 status 过滤：
```python
full = reg.get_full_info(member_id) or {}
meta = full.get("metadata", {}) or {}
mstatus = meta.get("status", "active") if isinstance(meta, dict) else "active"
if mstatus != "active":
    continue  # 不检测非活跃成员的进程状态
```

**严重程度**: 中 — 功能不影响（检测失败显示 offline 是预期行为），但浪费资源

---

### 🟢 Issue 3：看板 assignee 下拉列表

**位置**: `dev_center.js` 或 HTML 模板中的 assignee 下拉（硬编码）

**说明**: 当前 HTML 硬编码 3 个活跃成员，不受 `/api/members` 影响。但设计文档 open question #2 提到此问题，建议后续将 assignee 下拉改为动态获取（从 `/api/members` 取活跃成员列表），避免新成员加入时需要手动改 HTML。

**严重程度**: 低 — 不在本次修复范围内，但建议记录为 tech debt

---

### 🟢 Issue 4：统计页「成员状态」区同步

**位置**: `renderMemberStatus()` 统计区

**说明**: 设计文档 open question #1 确认需同步过滤。代码中 `renderMemberStatus()` 使用 `_get_member_data()`，改后自动同步。但需验证统计页 UI 显示逻辑是否依赖硬编码 6 人（经验证：无，依赖 API）。

**严重程度**: 低 — 已通过设计确认

---

## 改进建议

1. **必须修复**: Issue 1（fallback 路径缺 status 过滤）— 这会导致 ZooRegistry 异常时原 bug 复现
2. **建议修复**: Issue 2（`_update_status()` 过滤 inactive）— 减少无意义的进程检测
3. **后续跟进**: Issue 3（assignee 下拉动数据化）— tech debt，不阻塞本次

---

## 结论：**pass**

**理由**：
- 设计核心逻辑正确，后端过滤方案合理
- 修复范围明确，影响面可控
- 默认值设计安全，新增成员不会被误杀
- API 契约（核心方案）保持不变

**必须修复后方可进入 implement 阶段**：Issue 1（fallback 路径缺 status 过滤）必须在 `_get_member_data()` 的 fallback 分支中加入相同的 `status == "active"` 过滤。这是设计文档中明确要求但未在代码层面体现的关键遗漏。

---

## 审查摘要

| 检查项 | 结论 |
|--------|------|
| 架构合理性 | ✅ 通过 |
| 安全风险 | ✅ 低风险 |
| 设计覆盖完整性 | ⚠️ 遗漏 Issue 1（fallback 路径） |
| 回归风险 | ✅ 低（仅成员管理 Tab 受影响） |
| 接口契约 | ✅ 核心方案不变 |
| 最终结论 | **pass**（修复 Issue 1 后） |