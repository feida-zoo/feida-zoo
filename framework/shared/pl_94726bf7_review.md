# Review 阶段审查报告 — pl_94726bf7

**需求标题**: 看板页的需求ID过长，而且和聊天室里的pl id对不上，建议统一为pl id
**审查日期**: 2026-05-27
**审查人**: 毒刺 🦂

**上游 commit**: 10819cc (`🐢 design: 看板页需求ID统一为pl id`)

---

## 1. 架构合理性

### 1.1 改动范围精确

仅修改 `createTaskCard()` 一处显示逻辑，无后端改动，无接口变更。风险极低。

### 1.2 Fallback 策略正确

`${task.pipeline_id || task.id || ''}` 三层兜底：
- 有 pipeline_id → 显示短 ID（如 `pl_3edd4a81`）
- 无 pipeline_id → 回退 UUID
- 均无 → 空字符串

验证：21 条需求中 19 条有 pipeline_id，2 条旧数据（avatar 重绘，无 pipeline_id），fallback 到 task.id 不崩。✅

### 1.3 click handler 不受影响

`taskCard.dataset.taskId = task.id` 不变，详情面板仍用 UUID 做唯一标识。显示与标识解耦，合理。✅

---

## 2. 安全风险

| 风险 | 等级 | 说明 |
|------|------|------|
| pipeline_id 注入 | 无 | 格式固定 `pl_` + hex，不可能含 HTML 特殊字符 |
| 旧数据 fallback | 无 | UUID 格式也安全 |

---

## 3. 遗漏检查

### 3.1 🟡 详情面板未改

`dev_center.js:892` 任务详情弹窗中仍有：
```javascript
<span class="detail-value">${task.id}</span>
```

Design 未提及此位置。如果用户点击卡片看详情，详情里还是 UUID，与卡片上的 pl_id 不一致，可能造成困惑。

**建议**：详情面板也应显示 pipeline_id，或同时显示两者（如 `pl_3edd4a81 (e13ac8d8-...)`）。

### 3.2 🟢 无 pipeline_id 的旧数据 fallback 体验

2 条旧需求显示 UUID，其余显示 pl_id。视觉上不统一，但影响范围极小（已完成状态，用户不常关注），可接受。

---

## 4. 改进建议

### 4.1 P1 — 详情面板同步显示 pipeline_id

`showTaskDetail()` 中 task.id 也应替换为 pipeline_id，或增加一行显示 pipeline_id。

### 4.2 P2 — 旧数据 pipeline_id 补全

2 条 avatar 重绘需求无 pipeline_id，可在后端读取时 lazy-fill（与 pl_3edd4a81 中建议的 priority lazy-fill 同理）。

---

## 5. 结论

**PASS ✅**

改动精确、风险低、fallback 策略覆盖所有边界。detail 面板未同步是 P1 改进项，不阻塞通过。
