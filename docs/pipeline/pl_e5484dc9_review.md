# Review 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: review  
**上游**: design commit d57e8a2  

---

## 一、架构合理性

### ✅ 合理之处

1. **核心论点成立**: Pipeline 自动路由使手动指派无意义。`_pick_phase_agent` 已能正确路由所有阶段，assignee 字段是误导性残留。
2. **改动范围识别正确**: HTML/JS/后端/Daemon 4 文件是主要改动对象。
3. **历史数据不删**: 保留 requirements.json 中的 assignee 字段值，只删除 UI 和路由依赖，正确做法。
4. **Tradeoff 分析合理**: 完全删除优于隐藏/置灰。

### P0 — `_phase_assignee` 仍被调用但 design 未说明如何处理

5. **`_phase_assignee` 函数未被列入删除清单**: 当前 `_phase_assignee(phase, requirement)` 优先读 `requirement.assignee`，design 说"移除 assignee 兜底，纯自动路由"，但这意味着 `_phase_assignee` 的行为会与 `_pick_phase_agent` 完全相同。**问题**: 是否应该直接删除 `_phase_assignee` 并将所有调用点改为 `_pick_phase_agent`？还是保留函数但清空内部逻辑？design 未明确。**建议**: 删除 `_phase_assignee`，全量替换为 `_pick_phase_agent(phase)`，避免两个函数做相同的事。

### P1 — daemon 中 assignee 引用点远超 design 列出的 4 处

6. **daemon 有 42 处 assignee 引用**，design 仅列出 `_phase_assignee` 一处修改。以下关键位置未被 design 覆盖：

| 行号 | 代码 | 问题 |
|------|------|------|
| L602 | `assignee = payload.get("assignee") or _pick_phase_agent("design")` | 创建 pipeline 时仍从 payload 读 assignee |
| L624-625 | `if not cur_req.get("assignee"): cur_req["assignee"] = assignee` | 仍写入 assignee 到 requirement |
| L638 | `"assignee": assignee,` | 新建 requirement 时写入 assignee |
| L884 | `next_agent = cur_req.get("assignee") or _pick_phase_agent(fallback)` | 驳回时仍用 assignee 兜底 |
| L909 | `next_agent = cur_req.get("assignee") or _pick_phase_agent(next_phase)` | 推进时仍用 assignee 兜底 |
| L1371 | `"assignee": req.get("assignee", ""),` | 通知消息仍携带 assignee |
| L1421 | `assignee = phase_agent or req.get("assignee", "")` | stuck 检测仍用 assignee 兜底 |

design 说"删除 assignee 字段处理"但只提到 `_phase_assignee` 一处。**L884 和 L909 是关键遗漏**——这两行在 Pipeline 驳回和推进时仍优先读 `cur_req.get("assignee")`，如果保留这些行，即使 UI 删除了 assignee 选择，历史数据中的 assignee 仍会影响路由。

### P2 — 遗漏的文件

7. **`dashboard/static/dev_center.css`**: 有 `.task-assignee`、`.assignee-avatar`、`.assignee-avatar-img` 等 CSS 类定义（549-567 行、1031-1037 行），删除 JS 中 assignee 元素后这些 CSS 成死代码。

8. **`dashboard/test_p0_pipeline_push.py`**: 测试中 `post_issue` 函数签名含 `assignee` 参数（L28-31），需同步清理。

9. **`dashboard/test_priority_sort.py`**: 测试中硬编码 `"assignee": "alpha"`（L245）和 `"assignee": ""`（L260），需更新。

10. **`dashboard/app_v2.py`**: L455 返回 assignee 字段。虽然 app_v2.py 可能已不使用，但需确认。

---

## 二、安全风险

11. **无新增安全风险**: 删除 UI 字段和后端逻辑不引入新攻击面。
12. **历史 assignee 数据**: 保留不删是正确的，删除历史数据有审计风险。

---

## 三、遗漏检查

13. **`request-assignee-select`（看板页面的指派下拉框）未在 design 中提及**: JS 中 L684 有 `document.getElementById('request-assignee-select')`，L1588-1601 有看板页面创建需求时的 assignee 逻辑，design 未覆盖。

14. **SSE 通知中的 assignee 引用**: `app_enhanced.py` L743-750 在创建需求时通知 assignee，需同步删除。

15. **`_pending_queue` 中的 assignee 字段**: pending 队列 item 结构含 `assignee` 字段（L1274, L1297, L1300），但这不是需求 assignee，而是阶段执行者，语义不同，**不应删除**。design 未区分两者。

16. **stuck 检测逻辑**: L1421 `assignee = phase_agent or req.get("assignee", "")` — 这里 `phase_agent` 优先级已高于 `assignee`，但 fallback 到 `assignee` 是不正确的。stuck 检测应完全依赖 `_pick_phase_agent`。

---

## 四、改进建议

| 优先级 | # | 问题 | 建议 |
|--------|---|------|------|
| P0 | 5 | `_phase_assignee` 未明确处置 | 删除该函数，调用点全量替换为 `_pick_phase_agent(phase)` |
| P1 | 6 | daemon L884/L909 仍用 `cur_req.get("assignee")` | 改为 `_pick_phase_agent(fallback/next_phase)` |
| P1 | 13 | 看板页面 `request-assignee-select` 未覆盖 | 同步删除看板页面的指派下拉框 |
| P1 | 14 | SSE 通知中 assignee 引用未覆盖 | 同步删除 `app_enhanced.py` L743-750 的 assignee 通知 |
| P2 | 7 | CSS 死代码 | 删除 `.task-assignee` 等类 |
| P2 | 8-9 | 测试文件 assignee 参数 | 同步清理 `test_p0_pipeline_push.py` 和 `test_priority_sort.py` |
| P2 | 16 | stuck 检测 fallback 到 assignee | 改为 `assignee = phase_agent`，去掉 `or req.get("assignee", "")` |

---

## 五、判定

**REJECT**

理由：
1. **P0**: `_phase_assignee` 函数处置未明确——删除还是改空？design 未说明。两个函数做相同的事会导致混乱。
2. **P1**: daemon 中 L884/L909 仍用 `cur_req.get("assignee")` 作为路由兜底，这是需求的核心矛盾点（手动 assignee 干扰自动路由），但 design 遗漏了这两处。如果只删 UI 不改这两行，历史数据的 assignee 仍会覆盖自动路由。
3. **P1**: 看板页面 `request-assignee-select` 和 SSE 通知中的 assignee 逻辑未被 design 覆盖。

需补充：
- `_phase_assignee` 的处置方案（建议删除，替换为 `_pick_phase_agent`）
- L602/L884/L909/L1421 的具体改动
- 看板页面 assignee 下拉框和 SSE 通知的清理
- CSS/测试文件的同步清理清单
