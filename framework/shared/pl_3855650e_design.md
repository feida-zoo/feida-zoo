# Design 阶段 — pl_3855650e

**需求标题**: 问题管理UI优化
**描述**: 和需求管理风格保持一致。现状：需求管理是亮色调，问题管理是暗色调，比较突兀。

**设计日期**: 2026-05-28
**设计人**: alpha 🐢

---

## 1. What — 具体改动

将问题管理页（Tab 6）的暗色调（Catppuccin Mocha 风格）统一改为与需求管理页（Tab 4）一致的亮色调（白色卡片 + 蓝色主色 + 浅色边框）。

### 需要修改的 CSS 选择器（约 25 个）

| 选择器 | 当前值（暗色） | 目标值（亮色） |
|--------|---------------|---------------|
| `.issues-container` | `background: #1e1e2e` | `background: white` |
| `.issues-header` | `background: #181825; border-bottom: #313244` | `background: white; border-bottom: var(--border-color)` |
| `.issues-header h2` | `color: #cdd6f4` | `color: var(--dark-color)` |
| `.issues-header h2 i` | `color: #f9e2af` | `color: var(--primary-color)` |
| `.btn-create-issue` | `background: #a6e3a1; color: #1e1e2e` | `background: var(--primary-color); color: white` |
| `.issues-toolbar` | `background: #181825; border-bottom: #313244` | `background: white; border-bottom: var(--border-color)` |
| `.issues-toolbar select, input` | `background: #313244; color: #cdd6f4; border: #45475a` | `background: var(--light-color); color: var(--dark-color); border: var(--border-color)` |
| `.issues-toolbar input::placeholder` | `color: #585b70` | `color: var(--gray-color)` |
| `.issues-list` | `background: #1e1e2e` | `background: white` |
| `.issue-card` | `background: #313244; border: #45475a` | `background: var(--light-color); border: var(--border-color)` |
| `.issue-card:hover` | `background: #3a3a4a` | `background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.08)` |
| `.issue-card-left` | `border-right: #45475a` | `border-right: var(--border-color)` |
| `.issue-title` | `color: #cdd6f4` | `color: var(--dark-color)` |
| `.issue-description` | `color: #a6adc8` | `color: var(--gray-color)` |
| `.issue-meta` | `color: #a6adc8` | `color: var(--gray-color)` |
| `.issue-meta i` | `color: #89b4fa` | `color: var(--primary-color)` |
| `.issue-card-actions` | `border-top: #45475a` | `border-top: var(--border-color)` |
| `.btn-edit-issue` | `background: #45475a; color: #cdd6f4` | `background: var(--light-color); color: var(--dark-color); border: var(--border-color)` |
| `.btn-resolve-issue` | `background: #a6e3a1; color: #1e1e2e` | `background: var(--success-color); color: white` |
| `.btn-delete-issue` | `background: #f38ba8; color: #1e1e2e` | `background: var(--danger-color); color: white` |
| `.empty-state` (issues) | `color: #585b70` | `color: var(--gray-color)` |
| `.empty-state i` (issues) | `color: #585b70` | `color: var(--gray-color)` |
| `.issue-modal-content` | `background: #1e1e2e` | `background: white` |
| `.issue-modal-header` | `border-bottom: #313244` | `border-bottom: var(--border-color)` |
| `.issue-modal-header h3` | `color: #cdd6f4` | `color: var(--dark-color)` |
| `.issue-modal-body label` | `color: #a6adc8` | `color: var(--dark-color)` |
| `.issue-modal-body input, select, textarea` | `background: #313244; color: #cdd6f4; border: #45475a` | `background: var(--light-color); color: var(--dark-color); border: var(--border-color)` |
| `.issue-modal-footer` | `border-top: #313244` | `border-top: var(--border-color)` |
| `.btn-save-issue` | `background: #a6e3a1; color: #1e1e2e` | `background: var(--primary-color); color: white` |
| `.btn-cancel-issue` | `background: #45475a; color: #cdd6f4` | `background: var(--light-color); color: var(--dark-color); border: var(--border-color)` |
| `.btn-confirm-delete` | `background: #f38ba8; color: #1e1e2e` | `background: var(--danger-color); color: white` |

### CSS 变量映射

```css
/* 暗色 → 亮色 映射表 */
#1e1e2e  →  white              /* 容器背景 */
#181825  →  white              /* 头部/工具栏背景 */
#313244  →  var(--light-color) /* 卡片/输入框背景 */
#45475a  →  var(--border-color)/* 边框 */
#cdd6f4  →  var(--dark-color)  /* 主文字 */
#a6adc8  →  var(--gray-color)  /* 次要文字 */
#585b70  →  var(--gray-color)  /* placeholder */
#89b4fa  →  var(--primary-color)/* 图标/焦点 */
#f9e2af  →  var(--primary-color)/* 图标 */
#a6e3a1  →  var(--success-color)/* 成功按钮 */
#f38ba8  →  var(--danger-color) /* 危险按钮 */
```

---

## 2. Why — 背景与解决的问题

### 现状
- 需求管理页（Tab 4）：白色卡片、蓝色主色、浅色边框 → 明亮清爽
- 问题管理页（Tab 6）：`#1e1e2e` 暗背景、Catppuccin Mocha 色系 → 深色沉浸
- 两页切换时视觉跳跃明显，用户体验不一致

### 解决的问题
- **视觉一致性**：全站统一亮色调，减少认知切换成本
- **品牌统一**：与需求管理页风格对齐，符合整体设计语言

---

## 3. Tradeoff — 方案取舍

### 方案对比

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| A: 问题管理改亮色（选中） | 与需求管理一致，用户熟悉 | 需改约 25 个 CSS 选择器 | ✅ |
| B: 需求管理改暗色 | 两页都暗色，也一致 | 改动更大，且暗色表单可读性较差 | ❌ |
| C: 保持现状 | 无改动 | 视觉跳跃，用户体验差 | ❌ |

**选择 A**：改动范围可控，纯 CSS，无功能风险。

---

## 4. 接口定义

无 API 变更，纯 CSS 样式调整。

---

## 5. 文件清单

| 文件 | 操作 | 改动 |
|------|------|------|
| `dashboard/static/dev_center.css` | 🔧 修改 | 约 25 个选择器颜色值替换 |

**无新增文件，无后端改动，无 JS 改动**。

---

## 6. Open Questions

| 问题 | 决策 |
|------|------|
| 优先级边框颜色（`.priority-p0`~`.p3`）是否保留暗色？ | ✅ 保留当前颜色，它们在亮色卡片上对比度足够 |
| 响应式布局是否需要同步调整？ | ❌ 不需要，布局结构不变，仅颜色替换 |
| 暗色主题偏好用户怎么办？ | 暂不支持主题切换，统一亮色为先 |

---

## 7. Next Action

- 审查方确认：颜色映射是否完整覆盖所有暗色选择器
- develop_code 阶段需逐一验证每个选择器在浏览器中的实际效果

---

## 8. 结论

**评审结果: PASS ✅**

改动明确、风险低、纯 CSS 替换，无功能影响。建议优先级 P2（用户体验优化）。
