# Review Report — pl_ecd1f8b8

**Task**: 成员管理界面各成员头像不正确  
**Requirement**: 21470d44-3b25-4d92-b9fd-f04867ef783d  
**Reviewer**: Duci (🦂)  
**Date**: 2026-05-26  
**Input**: `pl_ecd1f8b8_design.md` + `pl_ecd1f8b8_ui_design.md` + source code verification

---

## 架构合理性：✅ 通过

**方案选择正确。** 头像问题本质上是一个**文件替换 + 路径修复**的问题，不涉及数据逻辑或 API 契约变更。零代码改动（改动 A/C）+ 最小化代码改动（改动 B）+ 极小前端改动（改动 D）是最优路径。

**PROJECT_AGENTS_DIR 指向正确**：
```bash
/Users/zoo/workspace/code/feida_zoo/agents/{panda,alpha,duci}/avatar.png  # 全部存在 ✅
```

**文件操作顺序正确。** `rm` 先删 symlink，`cp` 后覆盖——避免了 cp 覆盖 symlink target 而非替换 link 的常见错误。

---

## 安全风险：✅ 低风险

### ✅ Path Traversal（已防护）
```python
file_path = STATIC_DIR / urlparse(self.path).path.split('/static/')[-1]
```
从 URL path 中提取相对路径片段再拼接到 STATIC_DIR，不存在 `../` 逃逸。

### ✅ 文件来源可信
头像源文件来自本地 `agents/` 目录和 `~/workspace/members/`，无外部输入。

### ✅ 无注入风险
无用户输入进入文件路径或命令执行。

### 🟢 `_serve_avatar()` 的 path traversal（但非本 pipeline 引入）
同 pl_2070b427 review 中的发现：`member_id` 来自 URL 无白名单。已有问题，本次 pipeline 不扩大攻击面（无代码改动涉及 `_serve_avatar()` 逻辑，仅改路径指向）。

---

## 遗漏检查

### 🟢 Issue 1：dev_center.js L743 已经是 clean 版本

**实际代码**（L743）：
```js
const avatarSrc = executor ? `/static/avatars/${executor}.png` : '';
```
设计文档说这是"改前"（有 stinger 映射），但当前代码**没有** stinger 映射。这意味着：
- 要么这是已修复状态（无需改动 D）
- 要么设计文档的历史版本有误

**结论**：改动 D（去除 stinger 硬编码）**不必要**，但执行也无害。可保留。

### 🟢 Issue 2：`duci.png` 是 symlink → `stinger.png`（实际比 validate 更严重）

**当前**：`static/avatars/duci.png` → symlink to `stinger.png`

设计文档已正确处理（`rm` 删除 symlink，`cp` 重建为真实文件）。这是设计文档在 validate 报告基础上的正确补充。

**验证**：
```bash
lrwx------  1 zoo  staff  11 May 13 23:18 duci.png -> stinger.png
```
设计文档的删除 + 替换操作可以正确解决此问题。

### 🟢 Issue 3：panda 头像来源已确认存在

**设计文档说**：`agents/panda/avatar.png`  
**源码验证**：
```
/Users/zoo/workspace/code/feida_zoo/agents/panda/avatar.png  # 存在 ✅
```

### 🟢 Issue 4：`stinger` 在代码中无引用

`grep -n "stinger" dev_center.js` → 无结果。说明历史遗留的 stinger 映射从未进入代码（可能只是 validate 报告的假设风险，而非实际代码问题）。

---

## 改进建议

1. **改动 D 建议改为"确认 dev_center.js 无 stinger 引用"**（而不是"修改"）。避免不必要的代码变更。

2. **文件操作前建议加锁或停止 dashboard 服务**，避免 dashboard 正在读取头像时文件被替换导致损坏（低风险，但严谨起见建议）。

---

## 结论：**pass**

**理由**：
- 方案最优（零/最小化代码改动解决头像问题）
- 安全风险低
- 所有源文件路径已验证存在
- 文件操作顺序正确（rm symlink → cp）
- dev_center.js 无需改动（已是 clean）

---

## 审查摘要

| 检查项 | 结论 |
|--------|------|
| 架构合理性 | ✅ 通过 |
| 安全风险 | ✅ 低风险 |
| 源文件存在性 | ✅ agents/{panda,alpha,duci}/avatar.png 全部存在 |
| 文件操作顺序 | ✅ rm symlink → cp 避免覆盖 target |
| dev_center.js stinger | 🟢 已 clean，D 不必要 |
| 最终结论 | **pass** |
