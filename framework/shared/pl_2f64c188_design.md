# Design 阶段 — pl_2f64c188

**需求标题**: 成员管理界面优化
**描述**: 
1. openclaw.json配置里agent的模型已修改，没有同步到zoo仪表盘上
2. 当前成员管理界面的模型配置，配色导致根本看不清

**设计日期**: 2026-05-28
**设计人**: alpha 🐢

---

## 1. What — 具体改动

### 改动 1：模型显示从硬编码改为动态读取

**问题定位**：
`renderMemberStatus()` 中成员模型是硬编码写死的：
```javascript
{ id: 'alpha', model: 'DeepSeek V4 Flash' },
{ id: 'duci', model: 'GLM-5.1' },
{ id: 'panda', model: 'MiniMax-M2.7' }
```

但后端 `/api/members` 已正确返回 `member.model`（从 openclaw.json 解析的别名）。前端没有使用 API 返回的数据。

**修复方案**：
- 删除硬编码模型数组
- 从 `/api/members` 返回的 `membersData` 中读取 `member.model`
- 无模型数据时显示 `"未知"`

### 改动 2：成员管理页配色从暗色调改为亮色调

**问题定位**：
成员管理页（Tab 5）使用亮色背景，但 `.member-details-mini` 和 `.member-model` 的文字颜色是 `rgba(255,255,255,0.7)` 和 `rgba(255,255,255,0.5)` —— 这是为暗色背景设计的，在亮色背景下几乎看不见。

**修复方案**：
将成员管理页相关 CSS 从暗色文字改为深色文字，与需求管理页风格一致。

| 选择器 | 当前值 | 目标值 |
|--------|--------|--------|
| `.member-details-mini` | `color: rgba(255,255,255,0.7)` | `color: var(--gray-color)` |
| `.member-model` | `color: rgba(255,255,255,0.5)` | `color: var(--gray-color)` |
| `.member-status-item` (第一定义) | `background: rgba(255,255,255,0.05); border: rgba(255,255,255,0.1)` | `background: var(--light-color); border: var(--border-color)` |
| `.member-status-item:hover` | `background: rgba(255,255,255,0.1)` | `background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08)` |

---

## 2. Why — 背景与解决的问题

### 问题 1：模型不同步
- openclaw.json 中模型配置修改后，仪表盘仍显示旧值
- 用户无法确认当前 Agent 实际使用的模型

### 问题 2：配色看不清
- 成员管理页是亮色背景，但文字颜色为半透明白色
- 对比度极低，用户无法阅读模型和角色信息

---

## 3. Tradeoff — 方案取舍

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| A: 前端动态读取 API model（选中） | 实时同步 openclaw.json | 需要修改 JS | ✅ |
| B: 后端推送模型变更到前端 | 前端无改动 | 需要 SSE/WebSocket 机制 | ❌ 过度设计 |
| C: 手动刷新页面 | 简单 | 用户体验差 | ❌ |

---

## 4. 接口定义

**无需新增/修改 API**。已有 `/api/members` 返回：
```json
{
  "id": "alpha",
  "name": "阿尔法 Alpha",
  "model": "DeepSeek V4 Flash",
  ...
}
```

---

## 5. 文件清单

| 文件 | 操作 | 改动 |
|------|------|------|
| `dashboard/static/dev_center.js` | 🔧 修改 | `renderMemberStatus()` 删除硬编码模型，使用 API 返回的 `member.model` |
| `dashboard/static/dev_center.css` | 🔧 修改 | `.member-details-mini`、`.member-model`、`.member-status-item` 颜色替换 |

---

## 6. Open Questions

| 问题 | 决策 |
|------|------|
| 模型显示为空时如何处理？ | ✅ 显示 `"未知"` |
| 成员管理页其他暗色元素是否需要同步修改？ | ✅ 一并修改 `.member-status-item` 背景和边框 |

---

## 7. Next Action

- develop_code 阶段需验证模型读取正确性
- 审查方确认配色对比度是否足够

---

## 8. 结论

**评审结果: PASS ✅**

改动明确、风险低、用户体验提升明显。建议优先级 P1。
