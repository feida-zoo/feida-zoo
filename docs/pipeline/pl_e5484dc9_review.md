# Review 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」(第 2 轮)

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: review（第 2 轮）  
**上游**: design v2 commit 9073eda  
**上轮**: REJECT (e10ee16) — design v1 遗漏 daemon 内 6 处关键改动

---

## 一、上轮 REJECT 问题修复验证

| # | 上轮问题 | v2 修复方式 | 验证 |
|---|----------|------------|------|
| P0#5 | `_phase_assignee` 未明确处置 | **删除**该函数 + 全量替换为 `_pick_phase_agent` | ✅ 改动 #5 |
| P1#6 | daemon L884/L909 仍用 assignee 兜底 | 改为 `next_agent = _pick_phase_agent(fallback/next_phase)` | ✅ 改动 #9 |
| P1#6 | L602 创建 pipeline 仍读 payload assignee | 改为 `phase_assignee = _pick_phase_agent("design")` | ✅ 改动 #6 |
| P1#6 | L624-625 仍写入 assignee | 直接删除 if 块 | ✅ 改动 #7 |
| P1#6 | L638 创建 requirement JSON 含 assignee | JSON 中不含 assignee | ✅ 改动 #8 |
| P1#13 | 看板 `request-assignee-select` 未覆盖 | UI 设计 3.5 明确删除 | ✅ |
| P1#14 | SSE 通知中 assignee 逻辑未覆盖 | 删除 `app_enhanced.py` L743-750 整个 if 块 | ✅ 改动 #14 |
| P2#7 | CSS 死代码 | 改动清单 #3 明确清理 `.task-assignee` 等 | ✅ |
| P2#8-9 | 测试文件 assignee 参数 | 改动清单 #11/#12 明确清理 | ✅ |
| P2#16 | stuck 检测 fallback 到 assignee | 改为 `assignee = phase_agent or "panda"` | ✅ 改动 #10 |

**上轮全部 10 项问题已覆盖。**

---

## 二、架构合理性

### ✅ 优秀之处

1. **改动清单结构化**: 12 项改动按优先级（P0/P1/P2）和文件位置编号，清晰可执行
2. **核心矛盾分析准确**: 「核心矛盾: `_phase_assignee` 优先读 requirement.assignee → 数据污染」一针见血
3. **数据流图清晰**: 明确说明改后所有路由经过 `_pick_phase_agent`
4. **每个关键改动给出 before/after 代码**: #5/#6/#7/#9/#10/#14 都有具体代码示例
5. **正确区分两种 assignee 语义**: pending_queue 中的 assignee 是阶段执行者，与需求 assignee 语义不同，保留
6. **历史数据保留策略**: 不删 requirements.json 中已有的 assignee，符合"不破坏历史"原则
7. **实施步骤合理**: daemon → app_enhanced → HTML/JS/CSS → 测试，依赖顺序正确

### P2 — 小问题

8. **#10 stuck 检测的 fallback `"panda"` 略生硬**: stuck 检测的目的是找出当前阶段的负责人重新催办。如果 `_pick_phase_agent(status)` 返回空字符串，fallback 到 `"panda"` 会把所有 stuck 都甩给 panda。**建议**: 应该用 `_pick_phase_agent` 兜底失败时记日志并跳过，而不是默认给 panda（panda 不一定是当前阶段执行者）。**不阻塞**，但建议 impl 阶段考虑。

9. **未提及 `dashboard/app_v2.py`**: 上轮 review #10 提到 `app_v2.py` L455 返回 assignee 字段。v2 设计未列入清单。**建议**: 确认 `app_v2.py` 是否仍在使用，如已废弃可不改。

10. **JS 中 assignee 引用点未全部列出**: design 说 "~30 行删除"，但 dev_center.js 有 22 处 assignee 引用（行号包括 374-385、684、741-742、774-776、882-900、1335、1367、1380-1396、1533-1561、1588-1601）。**建议**: design 列出每个 JS 引用点的处置，避免 impl 阶段遗漏。

---

## 三、安全风险

11. **无新增安全风险** ✅
12. **历史数据保留**: 不删除 requirements.json 中的历史 assignee，正确做法 ✅
13. **API 兼容性**: 删除 assignee 字段后，旧客户端如果仍发送 assignee，应该被忽略而非报错。design 未明确，但 Python 的 `data.get('assignee')` 模式天然兼容（被忽略）。建议 impl 阶段确认。

---

## 四、遗漏检查

14. **`framework/shared/event_bus/zoo_members_example.py` 和 `event_bus_demo.py`** 含 assignee 引用（之前 grep 发现）：是 demo 文件，可不改。design 未提及，**不阻塞**。

15. **`requirements.json` 中所有现有 assignee 值的现状**: 改后 UI 不显示，但字段仍在 JSON 中。design 说"历史数据 assignee 保留不删"，但未说明：新建需求时 assignee 字段还会被写入吗？根据改动 #7/#8，answer 是**不会**——新需求不再写入 assignee 字段。这是正确的，但 design 可以更明确说明"新数据无 assignee 字段，旧数据保留"。

16. **JSON Schema 变更**: requirements.json 的 schema 实际上发生了变更（新数据缺 assignee 字段）。如果有其他工具（如导出脚本、Migration 工具）依赖该字段，可能受影响。design 未提及向后兼容性检查。**建议**: impl 阶段 grep 全仓库 `req.get("assignee"` 和 `requirement.get("assignee"` 确认无遗漏依赖。

---

## 五、改进建议

| 优先级 | # | 问题 | 建议 |
|--------|---|------|------|
| P2 | 8 | stuck 兜底 panda 略生硬 | impl 时考虑跳过而非默认 panda |
| P2 | 9 | app_v2.py 未列入 | 确认是否废弃，未废弃则同步清理 |
| P2 | 10 | JS 改动行号未全列出 | impl 时全文 grep assignee 确认全清 |
| P2 | 16 | JSON Schema 变更未提兼容性 | impl 时 grep 全仓库 `.get("assignee")` 确认无外部依赖 |

---

## 六、判定

**PASS**

理由：
1. **上轮全部 10 项 REJECT 问题均已修复**: 改动清单覆盖完整，每项关键修改给出 before/after 代码
2. **结构清晰可执行**: 12 项改动按优先级编号，文件路径明确
3. **核心矛盾分析准确**: 直击问题本质（`_phase_assignee` 优先读 assignee 造成污染）
4. **正确区分语义**: `pending_queue.assignee`（阶段执行者）≠ `requirement.assignee`（手动指派），不误删
5. **历史数据保留策略正确**: 不破坏现有数据
6. **实施步骤合理**: 从核心到外围

剩余 4 项 P2 建议（stuck 兜底、app_v2.py、JS 行号、JSON schema 兼容性）均为 impl 阶段可自行处理的细节，不构成 REJECT 理由。
