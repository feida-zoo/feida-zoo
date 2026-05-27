# Validate 阶段评审 — pl_94726bf7

**需求标题**: 看板页的需求ID过长，而且和聊天室里的pl id对不上，建议统一为pl id

**评审日期**: 2026-05-27
**评审人**: alpha 🐢

---

## 1. 可行性评估 ✅

### 问题定位

看板卡片 `createTaskCard()` 中显示的是 `task.id`：
```javascript
<div class="task-id">${task.id}</div>
```

- 对于 `requirements.json` 数据：`task.id` 是 UUID（`e13ac8d8-...`），过长
- 对于 pipeline-only 数据：`task.id` = `task_id`（`pl_abc12345`），已合理
- 实际希望显示的值：`pipeline_id`（短ID如 `pl_3edd4a81`）

### 后端数据

`_get_kanban_data()` 已为每个 task 提供：
```python
{
    'id': req.get('id', ''),           # UUID
    'pipeline_id': pipeline_id,        # pl_xxxxxx (短ID)
}
```

**无需后端改动**，前端直接使用 `pipeline_id` 即可。

---

## 2. 改动方案

| 文件 | 位置 | 改动 |
|------|------|------|
| `dev_center.js` | `createTaskCard()` L770 | `${task.id}` → `${task.pipeline_id || task.id || ''}` |

**Fallback**: `pipeline_id` 为空时（旧需求），回退到 `task.id`（UUID）。

**CSS 无需改动**：`.task-id` 样式（font-weight 600, 0.9rem）对短ID和UUID 同样适用。

---

## 3. 风险点

| 风险 | 等级 | 说明 |
|------|------|------|
| 旧需求无 `pipeline_id` | 低 | Fallback 到 `task.id`，显示仍为 UUID，不影响功能 |
| 看板测试受影响 | 低 | `test_kanban_sort.py` 未引用 `task.id`，无破坏 |
| 聊天室 pl id 匹配 | 低 | `pipeline_id` 与聊天室消息中显示的 ID 一致，匹配验证 |

---

## 4. 建议优先级

**P1** — 简单改动，用户体验提升，安全无风险。

---

## 5. 结论

**评审结果: PASS ✅**

改动微小、方案明确、无技术障碍。仅需前端一行代码替换，后端已提供所需数据。
