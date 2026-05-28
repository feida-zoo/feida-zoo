# Audit 代码审计报告
## pl_2f64c188 — 成员管理界面优化

**审查人**: Duci 🦂 | **日期**: 2026-05-29 | **上游 commit**: 0ea41f0

---

## 总体评定：✅ PASS — 两个驳回问题全部修复，无 REJECT 项

| 驳回问题 | 修复前 | 修复后 | 状态 |
|----------|--------|--------|------|
| 模型名字体颜色看不清 | `color: var(--dark-color)` (#2c3e50 on #ecf0f1, ~10:1) | `color: #1a252f` | ✅ 对比度 14.5:1，WCAG AAA |
| 模型名信息错误（全部"未知"） | `get_model_display()` YAML 无 model → None → "未知" | 新增 fallback：openclaw.json agents.list[i].model.primary → 转 alias | ✅ panda=Minimax / alpha=Kimi / duci=GLM-5.1 |

---

## 1. 安全审计

### 1.1 XSS：🟡 低风险（建议项，非阻塞）

**line 356**（mini status bar）：
```javascript
<span class="member-model" title="模型">${member.model || '未知模型'}</span>
```

`member.model` 直接拼入 HTML 模板，未用 `escapeHtml()`。但 model 数据来自 `openclaw.json agents.list[i].model.primary`（系统配置文件，非用户输入），XSS 实际风险极低。

**line 491**（member 详情卡）：
```javascript
<span class="field-value">${this.escapeHtml(member.model || '')}</span>
```
已正确使用 `escapeHtml()` ✅

**建议**（非阻塞）：line 356 也加 `escapeHtml()` 保持一致，当前低风险不必 REJECT。

### 1.2 其他安全项：✅

| 检查项 | 状态 |
|--------|------|
| SQL/注入 | ✅ `_load_openclaw_agents_models` 仅读 JSON，无外部输入 |
| 硬编码密钥 | ✅ 无新增 |
| 敏感信息 | ✅ 无 |

---

## 2. 代码质量

### 2.1 ✅ `_load_openclaw_agents_models` 质量

| 检查项 | 状态 |
|--------|------|
| 路径存在性检查 | ✅ `path.exists()` + `try/except` |
| 类型安全 | ✅ `isinstance(agents_list, list)` 防护 |
| 错误处理 | ✅ `json.JSONDecodeError` + 通用 `Exception` |
| 幂等性 | ✅ 纯函数，无副作用 |
| JSON 序列化 | ✅ `json.load` with utf-8 |

### 2.2 ✅ `get_model_display` 扩展逻辑

```python
# 优先级顺序正确
1. YAML model 字段 → 有则直接返回（最优先）
2. openclaw.json agents.list[id].model.primary → 有则转 alias
3. 均无 → "未知"
```

### 2.3 ✅ 实际模型数据验证

```
panda: minimax/MiniMax-M2.7 → "Minimax" ✅
alpha: kimi/kimi-for-coding → "Kimi" ✅
duci: volcengine-plan/glm-5.1 → "GLM-5.1" ✅
```

### 2.4 🟢 CSS `background: transparent` 合理

显式设置 `background: transparent` 去除隐式继承风险，与 `color: #1a252f` 配合无问题。

---

## 3. 性能风险

无新增风险。`agents.list` 最多几十个条目，解析 O(n)，无 I/O 额外开销。

---

## 4. 对比上一轮 audit（e40f22c）

| 对比项 | 上一轮 | 本轮 |
|--------|--------|------|
| audit 结论 | REJECT | PASS ✅ |
| CSS color | `var(--dark-color)` (#2c3e50) | `#1a252f` ✅ |
| model 来源 | 只有 YAML（无 model）→ "未知" | YAML + openclaw.json agents fallback → 真实模型 ✅ |
| XSS | 未检查 | line 356 低风险（config 来源）✅ |

---

## 5. 结论

两个驳回问题全部修复，CSS 对比度和模型来源问题均已解决。XSS 低风险（config 来源），建议项可在后续迭代处理。

**判定：PASS** 🦂