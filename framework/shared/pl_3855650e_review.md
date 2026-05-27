# Review 阶段审查报告 — pl_3855650e

**需求标题**: 问题管理UI优化
**描述**: 和需求管理风格保持一致。现状：需求管理是亮色调，问题管理是暗色调，比较突兀。
**审查日期**: 2026-05-28
**审查人**: 毒刺 🦂

**上游 commit**: df72c4b (`🐢 design: 问题管理UI亮色调统一`)

---

## 1. 架构合理性

### 1.1 改动范围

纯 CSS 替换，无 JS 改动，无 API 变更，无新增文件。约 25 个选择器颜色值替换，将 Catppuccin Mocha 暗色系替换为需求管理页已使用的亮色变量。

### 1.2 颜色映射完整性

| 映射 | 覆盖情况 |
|------|---------|
| 容器背景 `#1e1e2e` → `white` | ✅ 覆盖 `.issues-container`、`.issues-list` |
| 头部/工具栏 `#181825` → `white` | ✅ 覆盖 `.issues-header`、`.issues-toolbar` |
| 卡片/输入框背景 `#313244` → `--light-color` | ✅ 覆盖 `.issue-card`、input/select/textarea |
| 边框 `#45475a` → `--border-color` | ✅ 覆盖所有边框相关 |
| 主文字 `#cdd6f4` → `--dark-color` | ✅ 覆盖标题、label |
| 次要文字 `#a6adc8/#585b70` → `--gray-color` | ✅ 覆盖 description、meta、placeholder |
| 图标色 `#89b4fa/#f9e2af` → `--primary-color` | ✅ 覆盖图标 |
| 按钮色 `#a6e3a1/#f38ba8` → success/danger | ✅ 覆盖所有操作按钮 |

所有暗色值均有映射，无遗漏。✅

### 1.3 设计决策合理性

- 选方案 A（问题管理改亮色）而非方案 B（需求管理改暗色）：正确，需求管理已有亮色风格，改问题管理成本更低
- 优先级边框 `.priority-p0~.p3` 保留暗色：合理，design 明确说明亮色卡片上对比度足够
- 暂不支持暗色主题切换：合理，P2 优化不影响核心功能

---

## 2. 安全风险

| 风险 | 等级 | 说明 |
|------|------|------|
| CSS 注入 | 无 | 纯颜色值替换，不涉及用户输入 |
| 浏览器兼容 | 低 | 使用标准 CSS 变量，无新语法 |
| 可访问性 | 低 | 亮色主题通常对比度更好；需注意 `.issue-description` 从 `#a6adc8`（暗色低对比度）→ `--gray-color`，对比度可能变化，建议在 develop_code 后用 Lighthouse 检查 |

---

## 3. 遗漏检查

### 3.1 🟡 未覆盖 `.issue-modal-overlay`

设计覆盖了 `.issue-modal-content`、`.issue-modal-header`、`.issue-modal-body`、`.issue-modal-footer`，但未提及 `.issue-modal-overlay`（若存在）的背景色。若 overlay 仍为暗色，modal 打开时会与亮色内容产生二次视觉跳跃。

**建议**：develop_code 阶段确认 `.issue-modal-overlay` 的处理方式。

### 3.2 🟡 `.btn-resolve-issue` 颜色变更需验证

从 `#a6e3a1`（绿色）→ `--success-color`。需确认 `--success-color` 实际值是否为绿色，若不是绿色则语义改变。

### 3.3 🟢 `.btn-create-issue` 语义保留

从绿色 `#a6e3a1` 改为 `--primary-color`（蓝色）。创建按钮语义从"添加（绿色）"变为"主操作（蓝色）"，语义略有变化但可接受——按钮更突出。

### 3.4 🟢 现有 CSS 变量存在性

design 引用了 `--border-color`、`--light-color`、`--dark-color`、`--gray-color`、`--primary-color`、`--success-color`、`--danger-color`。需确认 dev_center.css 中已定义这些变量（与需求管理页共用同一 CSS 文件，应已存在）。

---

## 4. 改进建议

### 4.1 P1 — 确认 modal overlay 背景色

develop_code 阶段需检查并处理 `.issue-modal-overlay`（若存在）的背景色。

### 4.2 P2 — 可访问性验证

develop_code 后用 Lighthouse 检查对比度是否达标（特别是 `.issue-description` 和 `.issue-meta` 的灰色文字）。

---

## 5. 结论

**PASS ✅**

纯 CSS 替换，改动明确，无功能风险，颜色映射覆盖完整。modal overlay 需开发阶段确认，其余均为低风险项。