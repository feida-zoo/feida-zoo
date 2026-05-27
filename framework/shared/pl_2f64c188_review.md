# Review 阶段审查报告 — pl_2f64c188

**需求标题**: 成员管理界面优化
**描述**:
1. openclaw.json配置里agent的模型已修改，没有同步到zoo仪表盘上
2. 当前成员管理界面的模型配置，配色导致根本看不清

**审查日期**: 2026-05-28
**审查人**: 毒刺 🦂

**上游 commit**: 1c6eb7d (`🐢 design: 成员管理界面优化`)

---

## 1. 架构合理性

### 1.1 问题1修复方案 — 合理

**当前问题**：`renderMemberStatus()` 硬编码模型数组，忽略 API 返回的 `member.model`。

**方案**：删除硬编码，从 `membersData[i].model` 读取。后端 `/api/members` 已正确返回模型数据，前端未使用。

改动精确，无 API 改动，无数据流变更。✅

### 1.2 问题2修复方案 — 合理

**当前问题**：亮色背景 + `rgba(255,255,255,0.7)` 白色文字 → 对比度极低。

**方案**：颜色替换为 `var(--gray-color)`（深灰色），与需求管理页风格一致。

颜色映射覆盖 `.member-details-mini`、`.member-model`、`.member-status-item` 三个选择器，完整。✅

### 1.3 Tradeoff 分析

| 方案 | 选择 | 理由 |
|------|------|------|
| 前端动态读取 API（选中） | ✅ | 改动小，实时同步 |
| 后端推送变更 | ❌ | 过度设计，需 SSE/WebSocket |
| 手动刷新 | ❌ | 体验差 |

合理。✅

---

## 2. 安全风险

| 风险 | 等级 | 说明 |
|------|------|------|
| 模型值注入 XSS | 低 | 模型值来自后端解析 openclaw.json，用户不可控；但若 openclaw.json 配置被恶意篡改，模型名直接渲染存在风险。建议后端对模型名字符做 `escapeHtml()` |
| API 返回数据篡改 | 低 | `/api/members` 返回数据仅来自配置文件，无用户输入，篡改需文件系统权限 |

---

## 3. 遗漏检查

### 3.1 🟡 XSS 风险：模型名未做 escapeHtml

Design §4 接口定义中，`member.model` 直接用于 innerHTML 渲染（`renderMemberStatus()` 的 `innerHTML`）。若 openclaw.json 中模型名含 `<script>` 等，会被执行。

**建议**：develop_code 阶段在渲染模型时加 `escapeHtml(member.model)` 兜底。

### 3.2 🟢 open Questions 已闭环

- 模型为空 → 显示 "未知" ✅
- 其他暗色元素 → 一并修改 ✅

---

## 4. 改进建议

### 4.1 P1 — 模型名渲染加 escapeHtml

```javascript
// renderMemberStatus() 中
model: ${escapeHtml(member.model) || '未知'}
```

### 4.2 P2 — 验证 `/api/members` 返回的 model 字段

确保后端 `getMemberData()` 确实返回了 `model` 字段（非 null/undefined）。

---

## 5. 结论

**PASS ✅**

两个问题均有明确修复方案，改动范围小（JS + CSS 各几处），风险低。唯一 P1 建议是模型名渲染加 `escapeHtml()`（低风险但应做），不阻塞本次通过。