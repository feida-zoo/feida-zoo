# UI Design Report — pl_b5e6038b

**Task**: issue已经done了，但是问题管理界面。状态还是待处理
**Requirement**: aba00359-1b1a-4742-bac5-45c31b8bd1e4
**Designer**: Alpha (🐢)
**Date**: 2026-05-26
**Input**: `pl_b5e6038b_design.md`

---

## 概述

本需求为**纯后端数据修复**（daemon 在 pipeline done 时同步更新 issues.json），**前端 UI 无需任何改动**。问题管理界面已有的状态显示逻辑完全正确，只是数据源（issues.json）中的 `status` 字段未随 pipeline 完成而更新。

---

## 页面布局 — 无变化

问题管理界面现有布局保持不变：

```
┌─────────────────────────────────────────┐
│  🔔 问题管理                              │
├─────────────────────────────────────────┤
│  [全部 ▼]  [🔍 搜索...]   [+ 新建问题]   │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐    │
│  │ ⚠️ 统计页不需要生态成员    P1 待处理 │ ← status=open    │
│  │ 统计页的生态成员栏和成员管理...      │                  │
│  │ 负责人: 阿尔法 🐢  创建: 05-16    │                  │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ ✅ 看板tab页的数据...       P2 已解决 │ ← status=resolved│
│  │ 请重新设计看板页的现实逻辑...         │                  │
│  │ 负责人: 阿尔法 🐢  解决: 05-16    │                  │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## 交互逻辑 — 无变化

| 操作 | 改前行为 | 改后行为 | 变更 |
|------|---------|---------|------|
| 打开问题管理 Tab | 显示 issues.json 中的 status | 同左 | 无（数据源已同步） |
| 点击「解决问题」按钮 | 发送 PUT /api/issues/:id, status=resolved | 同左 | 无 |
| Pipeline 自动完成 | issue status 仍显示「待处理」 | issue status 自动变为「已解决」 | ✅ 后端修复生效 |

---

## 状态定义 — 现有逻辑已完备

问题管理界面已有的状态映射（`dev_center.js` L1293）：

| status 值 | 中文标签 | CSS class | 颜色 |
|-----------|---------|-----------|------|
| `open` | 待处理 | `status-open` | 橙色 #f9a825 |
| `in_progress` | 处理中 | `status-in-progress` | 蓝色 #2196f3 |
| `resolved` | 已解决 | `status-resolved` | 绿色 #4caf50 |
| `closed` | 已关闭 | `status-closed` | 灰色 #757575 |

**状态流转按钮**（L1300-1310）已有正确映射：
- `open` → 按钮文字「开始处理」→ `in_progress`
- `in_progress` → 按钮文字「解决问题」→ `resolved`（同时设置 resolved_at）
- `resolved` → 按钮文字「关闭问题」→ `closed`

修复后，pipeline 自动完成触发的后端更新直接写入 `status=resolved`，与前端按钮点击效果一致。

---

## 视觉说明 — 无变化

所有颜色、字体、徽章样式保持 dashboard 现有设计系统：

```css
.status-open { background: rgba(249, 168, 37, 0.15); color: #f9a825; }
.status-resolved { background: rgba(76, 175, 80, 0.15); color: #4caf50; }
```

---

## 文件清单（UI 相关）

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `dashboard/static/dev_center.js` | 0 | 状态映射逻辑已正确，无需改动 |
| `dashboard/static/dev_center.css` | 0 | 样式已完备 |
| `dashboard/templates/dev_center.html` | 0 | 模板无需改动 |

---

## 验证方式

修复后，用户可见的变化：

1. 打开问题管理 Tab
2. 找到之前 pipeline 已完成的 issue（如 pl_2070b427、pl_ecd1f8b8 对应的 issue）
3. 状态徽章从 **🟠 待处理** 变为 **🟢 已解决**
4. 操作按钮从「开始处理」变为「关闭问题」

无需刷新页面（SSE 实时推送或页面自动轮询已在 dashboard 中实现）。
