# Design 阶段 — pl_94726bf7

**需求**: 看板页的需求ID过长，而且和聊天室里的pl id对不上，建议统一为pl id

**设计日期**: 2026-05-27
**设计人**: alpha 🐢

---

## 1. What — 具体改动

看板卡片 `createTaskCard()` 中将显示的 ID 从 `task.id`（UUID，32+字符）改为 `task.pipeline_id`（短ID，如 `pl_3edd4a81`，10字符）。

### 改动位置

| 文件 | 函数 | 行 | 改动 |
|------|------|-----|------|
| `dashboard/static/dev_center.js` | `createTaskCard()` | ~L770 | `${task.id}` → `${task.pipeline_id \|\| task.id \|\| ''}` |

---

## 2. Why — 背景与解决的问题

### 现状
- 看板卡片显示 `task.id` → UUID（如 `e13ac8d8-5f13-47f5-8779-8d7929dcb57a`）
- 聊天室消息显示 `pl_id`（如 `pl_3edd4a81`）
- 两者不一致，用户无法快速关联看板卡片 ↔ 聊天室消息
- UUID 过长，卡片空间浪费

### 解决的问题
- **认知对齐**：看板卡片 ID 与聊天室 pipeline ID 一致，用户一眼匹配
- **空间节省**：短ID（10字符）vs UUID（36字符），卡片更紧凑

---

## 3. Tradeoff — 方案取舍

### 方案对比

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| A: 显示 pipeline_id | 短、与聊天一致 | 旧需求可能无 pipeline_id | ✅ 选中 |
| B: 截取 UUID 前8位 | 不依赖 pipeline_id | 仍无法关联聊天室 | ❌ |
| C: 同时显示两者 | 信息完整 | 卡片拥挤 | ❌ |

### Fallback 策略
旧需求（无 pipeline_id）回退到 `task.id`（UUID），保证旧数据不崩。

---

## 4. 接口定义

**无需修改 API 接口**。后端 `_get_kanban_data()` 已在每个 task 对象中提供 `pipeline_id` 字段。

```javascript
// task 对象结构（已有）
{
    id: 'e13ac8d8-...',           // UUID（旧显示值）
    pipeline_id: 'pl_3edd4a81',   // 短ID（新显示值）
    name: '需求标题',
    ...
}
```

---

## 5. 文件清单

| 文件 | 操作 | 改动 |
|------|------|------|
| `dashboard/static/dev_center.js` | 🔧 修改 | `createTaskCard()` 中 ID 显示逻辑 |

**无新增文件，无后端改动**。

---

## 6. Open Questions

| 问题 | 决策 |
|------|------|
| 旧需求无 pipeline_id 怎么处理？ | ✅ 回退到 task.id（UUID），显示不变 |
| pipeline-only 任务（无 requirement）？ | ✅ task.id = task_id = pipeline_id，已一致 |
| 是否需要修改 click handler？ | ❌ 不需要，taskCard.dataset.taskId 仍用 task.id 做唯一标识 |

---

## 7. Next Action

- 审查方确认：Fallback 逻辑是否覆盖所有边界 case

---

## 8. 结论

**评审结果: PASS ✅**

改动微小、风险低、用户体验提升明显。
