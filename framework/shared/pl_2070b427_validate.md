# Validate Report — pl_2070b427

**Task**: 成员管理界面人数不对
**Requirement**: 6587c35b-17d0-4361-bae4-5e04ecea31fa
**Validator**: Alpha (🐢)
**Date**: 2026-05-26

---

## 可行性分析：✅ 可实现

该需求技术上完全可行。问题根因已定位：

### 根因

**后端 `_get_member_data()`（`app_enhanced.py`）调用 `ZooRegistry.list_agents()`，该函数返回 `zoo_members.yaml` 中所有成员——包括 status 为 `inactive` 的已退出成员（weaver、aeterna、gulu）。**

`zoo_members.yaml` 有 6 个成员：
| 成员 | YAML status | 注册表 |
|------|-------------|--------|
| panda | active | ✅ |
| alpha | active | ✅ |
| duci | active | ✅ |
| weaver | inactive | ✅ (不应显示) |
| aeterna | inactive | ✅ (不应显示) |
| gulu | inactive | ✅ (不应显示) |

前端 `dev_center.js` 的 `renderMembersTab()` 未做任何过滤，直接渲染 API 返回的全部成员。

### 方案

两条路径，推荐 **A**：

**路径 A（推荐）—— 后端过滤，前端不动：**
- 在 `_get_member_data()` 中读取 YAML `metadata.status` 字段，仅返回 `"active"` 的成员
- 提供后端 `_get_inactive_members()` 供可选展示
- 改动量：~10 行 Python

**路径 B（次选）—— 前端过滤：**
- `renderMembersTab()` 根据后端返回的 `is_main_agent` 或新增 `status` 字段过滤
- 前端硬编码逻辑维护成本高

**路径 C（完工性补充）—— 显示非活跃成员分组：**
- 在路径 A 基础上，底部增加「非活跃成员」折叠区
- 前后端协同改动

---

## 依赖项

| # | 依赖 | 状态 | 说明 |
|---|------|------|------|
| 1 | ZooRegistry.list_agents() 返回完整列表 | ✅ 已满足 | 含 inactive |
| 2 | YAML 中 metadata.status 字段 | ✅ 已存在 | `active` / `inactive` |
| 3 | 看板/统计/需求等页面不受影响 | ✅ 无关联 | 仅成员管理 Tab 需改 |

---

## 风险点

| 风险 | 等级 | 说明 |
|------|------|------|
| 回归风险：`_get_member_data()` 被多处使用 | 🟢 低 | 该函数在 dashboard 中用于 `/api/members` 和 `renderMemberStatus()`，两者都在成员管理 Tab。统计页的成员状态列表也应同步过滤 |
| 看板任务负责人卡片 | 🟡 中 | 看板中 `task.assignee` 硬编码 emoji 映射仅含 3 个活跃成员。非活跃成员若 future 出现在 pipeline 任务中，会显示 `👤`。但短期内无风险 |
| 头像 fallback | 🟢 低 | 非活跃成员头像文件仍然存在 `/static/avatars/`，用户仍可通过 URL 直接访问。如需移除可作为后续 UI 清理项 |
| 前端 CSS 硬编码宽度 | 🟢 低 | `members-card-grid` 使用 CSS grid，加/减卡片自适应 |

---

## 建议优先级：**P1**

**P1 理由：**
- ✅ 这是一个**展示层的数据正确性 bug**，影响用户体验——用户看到 6 个成员，但实际上只有 3 个活跃成员在工作
- ✅ 修复量极小（~10 行 Python），零依赖、低回归风险
- ✅ zoome_members.yaml 已有明确 `status: inactive` 标记，不利用这个标记是数据治理疏漏
- ❌ 不阻塞生产流程（pipeline 调度不受影响），所以不需要 P0
- ❌ 没有数据丢失或崩溃风险

---

## 结论

**Pass** —— 需求清晰、可验证、可唯一判定（成员管理 Tab 显示成员数应为 3，而非 6）。修改范围窄，建议直接后端过滤一次到位。
