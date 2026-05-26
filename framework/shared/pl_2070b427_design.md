# Design Report — pl_2070b427

**Task**: 成员管理界面人数不对  
**Requirement**: 6587c35b-17d0-4361-bae4-5e04ecea31fa  
**Designer**: Alpha (🐢)  
**Date**: 2026-05-26  
**Input**: `pl_2070b427_validate.md`  

---

## What — 具体改动

### 核心改动

**后端 `_get_member_data()` 增加 status 过滤**，仅在返回数据中包含 `metadata.status == "active"` 的成员。

`zoo_members.yaml` 当前状态：

| 成员 | metadata.status | 当前是否显示 | 改后是否显示 |
|------|----------------|-------------|-------------|
| panda | active | ✅ | ✅ |
| alpha | active | ✅ | ✅ |
| duci | active | ✅ | ✅ |
| weaver | inactive | ✅ 错误显示 | ❌ |
| aeterna | inactive | ✅ 错误显示 | ❌ |
| gulu | inactive | ✅ 错误显示 | ❌ |

### 补充改动

**新增前端「非活跃成员」分组**（可选完工性补充）：
- 在成员管理 Tab 底部增加「非活跃成员」折叠区，同样从 `/api/members` 获取
- 后端返回所有成员时标记 `is_active`，前端按此分组展示

---

## Why — 背景与解决的问题

### 问题影响
- 成员管理 Tab 显示 6 人，实际活跃成员仅 3 人
- 用户（园长）看到 6 个成员卡片但其中 3 个从不运作，产生困惑
- 统计页「成员状态」也存在同样问题

### 根因
`ZooRegistry.list_agents()` 返回 `zoo_members.yaml` 所有注册成员——包括 `metadata.status: inactive` 的 retired 成员。`_get_member_data()` 无过滤逻辑。

---

## Tradeoff — 方案权衡

| 方案 | 描述 | 优点 | 缺点 | 决策 |
|------|------|------|------|------|
| **A（采纳）** | 后端过滤 + 前端保留 | `_get_member_data()` 加 filter；前端无需改动。 | 后增加「显示非活跃」功能需要改后端。 | ✅ **最优**: 单点修改，回归面小 |
| B | 前端 JS 过滤 | JS 读取 `is_main_agent` 或新增字段过滤 | 前端硬编码 vs 后端权威数据源，维护逻辑分散。数据量变化时 CSS 布局也可能偏差。 | ❌ 放弃 |
| C | ZooRegistry 增加 `list_active_agents()` | 从注册表层分离 | 改动 ZooRegistry 影响面大（被多处 import）。适用多层语义。 | ❌ 放弃 |
| **D（可选增强）** | 后端 + 前端「非活跃分组」 | 向下兼容，历史成员依然可见 | 增加前端改动量约 60 行 | ⭕ 后置: 视需求决定是否包含 |

---

## 接口定义

### 后端修改

#### `app_enhanced.py` — `_get_member_data()` (L1169~L1240)

**改动点 1**: 在主流程 for 循环中加入 status 检查

```python
# 在 is_main 获取之后，判断是否活跃
member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
if member_status != "active":
    continue  # 跳过非活跃成员
```

**改动点 2**: 若实现方案 D，在 append 中加入 `is_active` 字段

```python
members.append({
    ...,
    "is_active": member_status == "active",
})
```

#### `app_enhanced.py` — `MemberStatusManager._update_status()` (L225)

**改动点 3**: 可选——状态监控也只跟踪活跃成员

```python
agent_ids = reg.list_agents()
for member_id in agent_ids:
    full = reg.get_full_info(member_id) or {}
    meta = full.get("metadata", {}) or {}
    mstatus = meta.get("status", "active") if isinstance(meta, dict) else "active"
    if mstatus != "active":
        continue
    ...
```

### 前端修改（仅方案 D）

#### `dev_center.js` — `renderMembersTab()` (L1136)

新增区分活跃和非活跃的分组逻辑，在 grid 之后追加折叠区。

### API 响应变更

**`GET /api/members` 返回** — 仅移除 `status != "active"` 的条目，字段不变。

若实施方案 D，每个成员对象新增 `is_active: bool`。

---

## 文件清单

### 必须修改

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `dashboard/app_enhanced.py` | ~5 行 | `_get_member_data()` 加 filter |
| `dashboard/app_enhanced.py` | ~8 行 | （可选）`MemberStatusManager._update_status()` 过滤 inactive |

### 可选修改（方案 D）

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `dashboard/static/dev_center.js` | ~60 行 | 非活跃成员折叠展示 |
| `dashboard/static/dev_center.css` | ~15 行 | 折叠区样式 |

### 不变文件

| 文件 | 原因 |
|------|------|
| `framework/core/mesh/zoo_registry.py` | 注册表应保持完整，过滤是展示层职责 |
| `framework/data/zoo_members.yaml` | 数据源正确，`inactive` 标记已有 |
| `dashboard/templates/dev_center.html` | 无需改模板，JS 驱动渲染 |

---

## Open Questions

1. **是否需要在「统计」Tab 的「成员状态」区也过滤 inactive？**  
   建议同步过滤——当前统计页的 `renderMemberStatus()` 硬编码了 3 个活跃成员的 fallback，但其真实的 `/api/members` 数据也包含了 inactive。该区域改后同样只显示活跃成员。

2. **看板负责人筛选的下拉列表（需求管理 / 问题管理）是否也应移除 inactive？**  
   目前 assignee 下拉是 HTML 硬编码的 3 项（alpha/duci/panda），不受影响。但建议后续统一从 API 动态拉取活跃成员列表，避免新成员加入时手动改 HTML。

3. **头像文件是否清理？**  
   `static/avatars/weaver.png`、`static/avatars/aeterna.png`、`static/avatars/gulu.png` 仍然存在，但不会被引用。建议保留（万一 reactivate 时恢复），只需移除引用。

---

## Next Action — 审计重点

请 **Duci** 重点审查以下三点：

1. **过滤条件的选择**：使用 `metadata.status == "active"` 而非硬编码成员列表——确保 YAML 中所有成员的 metadata 都有 `status` 字段（已有）。边界 case：新增成员没有 `metadata.status` 时默认 `"active"`（不跳过），符合预期。

2. **回归风险**：确认 `_get_member_data()` 目前仅被 `/api/members` 端点调用（以及 `renderMemberStatus` 中作为 fallback）。无其他消费者。

3. **fallback 路径**：`_get_member_data()` 的 ZooRegistry 异常 fallback 路径（L1208~L1240）需要同样的过滤逻辑——该路径直接读取 YAML 文件，同样会返回 inactive 成员。
