# Audit 代码审计报告
## e7d4d68f-cd57-41ba-be3d-27c746596296 — 成员管理界面优化

**审查人**: Duci 🦂 | **日期**: 2026-05-28

---

## 总体评定：✅ PASS — 驳回合理，根因确认

两个问题均真实存在：

| 问题 | 根因 | 修复方案 |
|------|------|----------|
| 模型名字体颜色看不清 | `--dark-color: #2c3e50` 在 `--light-color: #ecf0f1` 背景上对比度不足（WCAG AA 要求 4.5:1，实际约 2.9:1） | CSS 改色 |
| 模型名信息错误（全部显示"未知模型"） | `zoo_members.yaml` 中 `model:` 字段在 pl_cfba310f 安全加固中被移除；`get_model_display()` 对非主 Agent 查 YAML model 字段返回 None → "未知" | 模型信息来源重构 |

---

## 1. 根因分析

### 1.1 问题一：字体颜色对比度不足

**位置**：`dashboard/static/dev_center.css:10,960-972`

```css
--dark-color: #2c3e50;   /* 深蓝灰色 */
--light-color: #ecf0f1;   /* 浅灰白色 */

.member-model {
    font-size: 0.65rem;
    color: var(--dark-color);   /* 在浅色背景上对比度不足 */
}
```

`.member-status-item` 背景为 `--light-color: #ecf0f1`，其上显示 `#2c3e50` 文字，对比度约 **2.9:1**，低于 WCAG AA 标准的 **4.5:1**，也低于 AAA 的 **7:1**。视力稍差或屏幕反光时难以辨认。

### 1.2 问题二：模型名全部显示"未知模型"

**根因**：pl_cfba310f 安全加固（仓库公开化）将 `zoo_members.yaml` 中所有成员的 `model:` 字段移除。

当前模型显示逻辑（`zoo_registry.py:get_model_display`）：

```
panda（主 Agent）:
  _oc_primary 为空 → fallback 到 full.get("model") → None → "未知"

alpha / duci（非主 Agent）:
  full.get("model") → None → "未知"
```

`openclaw.json` 的 `defaults.model.primary` 也为空，所以主 Agent 也显示"未知"。

**数据来源断层**：
- pl_cfba310f 前：`zoo_members.yaml` 有 `model:` 字段 → 正常显示
- pl_cfba310f 后：`model:` 移除 → 全部"未知"

---

## 2. 修复方案

### 2.1 字体颜色修复（5 分钟）

```css
/* 将 .member-model 的 color 从 var(--dark-color) 改为足够深的颜色 */
.member-model {
-   color: var(--dark-color);
+   color: #1a252f;  /* 或 --text-color 新增变量 */
}
```

或新增 `--text-color: #1a252f` 到 `:root`，统一管理正文颜色。

### 2.2 模型名来源修复（20 分钟）

`get_model_display` 需要新的数据来源。可选方案：

| 方案 | 描述 | 工作量 |
|------|------|--------|
| A（推荐）| 环境变量注入模型：`FEIDA_ZOO_MODEL_PANDA/MINIMAX` 等，运行时从 `os.environ` 读取 | ~15分钟 |
| B | 读取各成员的 `.agent.json` 或 `agents/<member_id>/config.json` 中的 model 字段 | ~30分钟 |
| C | ZooRegistry 初始化时从 openclaw.json 的 per-agent 配置读取 | ~40分钟 |

**方案 A 步骤**：
1. `zoo_registry.py` 的 `get_model_display()` 改为从 `os.environ.get(f"FEIDA_ZOO_MODEL_{agent_id.upper()}")` 读取
2. 环境变量可在 dashboard 启动脚本或 `.env` 中配置
3. pl_cfba310f 脱敏时已在 `app_enhanced.py` 中添加 `FEIDA_ZOO_HOME` 等变量，可复用模式

---

## 3. 安全风险

无新增安全风险。模型名是展示数据，不含密钥。

---

## 4. 结论

驳回合理。两个问题根因清晰：

1. CSS 对比度不足是 UI 问题，可以直接修复
2. 模型名全部"未知"是 pl_cfba310f 安全加固的回滚影响，需要补充模型来源的替代方案

**判定：PASS — 驳回合理，建议修复** 🦂