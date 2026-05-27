# Review 阶段审查报告 — pl_94726bf7

**需求标题**: 看板页的需求ID过长，而且和聊天室里的pl id对不上，建议统一为pl id
**审查日期**: 2026-05-27
**审查人**: 毒刺 🦂

**上游 commit**: ab82e6e6 (`🐼 StateMachine TRANSITIONS 同步新阶段`)

---

## 0. Commit 内容审计

上游 commit 包含**两类不相关改动**：

1. requirements.json 状态推进（validate → design）— 常规 pipeline 推进 ✅
2. **StateMachine TRANSITIONS 重构** — 删除了 ui_design/final_check/timed_out/escalated 阶段，新增 verify/rejected 阶段

design 文件（10819cc）仅涉及 `createTaskCard()` 中 ID 显示逻辑，**StateMachine 改动未被 design 覆盖，属于超范围变更**。

---

## 1. 架构合理性

### 1.1 看板 ID 改动 — 合理

Design 方案：`${task.id}` → `${task.pipeline_id || task.id || ''}`

- 解决了 UUID 过长（36字符）与聊天室 pl_id 不匹配的问题
- Fallback 到 task.id 保证旧数据兼容
- `dataset.taskId` 和详情面板中的 `task.id` 不变，仅改显示，click handler 不受影响 ✅

**但改动尚未实现**——当前代码 `dev_center.js:769` 仍为 `${task.id}`，design 定了方案但代码未落地。

### 1.2 StateMachine 重构 — 合理但有风险

**新流程**: `request → design → review → develop_wt → verify → develop_code → audit → deliver → done`

对比旧流程 `request → validate → design → ui_design → review → develop → develop_wt → review_test → develop_code → test → audit → final_check → deliver → done`

变化：
| 变化 | 评估 |
|------|------|
| 删除 `validate` | `request` 直达 `design`，validate 仅保留向后兼容入口 |
| 删除 `ui_design` | 合并到 `design`，简化 |
| 删除 `final_check` | 合并到 `audit`，简化 |
| 删除 `develop`、`test` | 原流程 develop→develop_wt→review_test→develop_code 和 test→audit 被重整为 develop_wt→verify→develop_code |
| 新增 `verify` | 替代 `review_test`，名称更精确 |
| 新增 `rejected` 终态 | 合理，review/audit 驳回不再走 escalated |
| 删除 `timed_out`/`escalated` 活跃转换 | 降级为向后兼容残留 |

**验证结果**：StateMachine.transition() 测试通过，新流程可正常推进。旧状态 validate/escalated/timed_out 保留向后兼容入口。✅

---

## 2. 安全风险

| 风险 | 等级 | 说明 |
|------|------|------|
| pipeline_id 显示注入 | 低 | pipeline_id 格式固定 `pl_` + 8位hex，不可能含 HTML；且 `createTaskCard` 用 template literal 构造，无 `escapeHtml` 但输入可控 |
| StateMachine 删除阶段导致存量数据卡死 | 中 | 若有 pipeline state 文件处于 `ui_design`/`final_check`/`review_test`/`test` 状态，TRANSITIONS 中这些状态已被移除，`transition()` 会报错。扫描 pipeline_state 目录未发现卡在这些状态的数据，**当前安全** |

---

## 3. 遗漏检查

### 3.1 🔴 代码改动未落地

Design 定义了 `createTaskCard()` 改动，但当前 `dev_center.js:769` 仍为 `${task.id}`，改动**未实现**。上游 commit 仅包含 StateMachine 改动和 requirements.json 推进，实际需求的代码改动缺失。

### 3.2 🟡 StateMachine 改动与前端状态映射不同步

StateMachine 删除了 `ui_design`、`final_check`、`review_test`、`test`、`develop`，但前端代码仍保留这些状态的中文映射：

- `dev_center.js:748` — `'ui_design': 'UI设计中'`
- `dev_center.js:753` — `'final_check': '终审中'`
- `dev_center.js:1626` — `'ui_design': 'UI设计中'`
- `dev_center.js:1634` — `'final_check': '终检中'`
- `app_enhanced.py:1328` — `"ui_design": "alpha"`
- `app_enhanced.py:1331` — `"final_check": "panda"`

前端保留旧映射不会崩（只是永远不会匹配到），但属于死代码。同样，新增的 `verify` 阶段缺少前端中文映射。

### 3.3 🟡 KANBAN_STATUS 缺少 `verify` 列

`app_enhanced.py:99` 的 KANBAN_STATUS 未包含 `verify` 阶段。处于 verify 状态的 pipeline 不会在看板上显示（或被归入异常列）。

### 3.4 🟡 `rejected` 在 KANBAN_STATUS 但不在 dev_center.js 状态映射中

`app_enhanced.py` KANBAN_STATUS 有 `rejected: "🚫 已驳回"`，但 `dev_center.js:747-755` 的 STATUS_CN 映射没有 `rejected`，看板卡片会显示空白阶段文字。

---

## 4. 改进建议

### 4.1 P0 — 落地看板 ID 改动

design 定义了改动但代码未实现。develop 阶段必须落实：
```javascript
// dev_center.js:769
- <div class="task-id">${task.id}</div>
+ <div class="task-id">${task.pipeline_id || task.id || ''}</div>
```

### 4.2 P1 — 前端状态映射同步

- 删除 `ui_design`、`final_check`、`review_test`、`test`、`develop` 的映射（可选保留向后兼容）
- 新增 `verify: '验证中'` 和 `rejected: '🚫 已驳回'` 映射
- `app_enhanced.py` 的 `PHASE_MEMBER_MAP` 同步更新

### 4.3 P2 — StateMachine 超范围变更拆分

StateMachine 重构与看板 ID 需求无关，应独立为另一个 pipeline。混在一起增加审查难度和回滚风险。

---

## 5. 结论

**REJECT ❌**

原因：

1. **需求核心改动未实现**：看板卡片 ID 从 UUID 切换到 pipeline_id 的代码改动未落地（`dev_center.js:769` 仍为 `${task.id}`）
2. **StateMachine 超范围变更未覆盖**：commit 包含了大幅重构 StateMachine 流程的改动，但无对应 design 文件，审查无依据
3. **前后端不同步**：StateMachine 新增 `verify`/`rejected` 阶段，前端映射和看板列定义未同步更新

**建议**：
- 看板 ID 改动：实现 design 定义的 1 行代码改动，即可 pass
- StateMachine 重构：拆为独立 pipeline，走完整的 validate → design → review 流程
