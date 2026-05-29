# Audit 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」(第 2 轮)

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: audit（第 2 轮）  
**上游**: impl fix commit 5e872b4  
**上轮**: REJECT (afef391) — JS SyntaxError + CSS 2 处 unmatched } + 测试设计缺陷

---

## 一、上轮 P0 修复验证

| # | 上轮问题 | 修复方式 | 验证 |
|---|----------|---------|------|
| P0#1 | dev_center.js L383 SyntaxError — 孤立 `if/});` | 函数体改为空函数 `updateKanbanAssigneeStatus(_statusData) {}` | ✅ `node -c` 通过 |
| P0#2 | CSS L549-552 孤立属性 + L1011 孤立 `}` | 删除孤立行 | ✅ 括号配对 depth=0 |
| P0#3 | 测试只文本匹配不验语法 | 新增 `test_js_syntax_valid` (node -c) + `test_css_braces_balanced` | ✅ 25/25 通过，守卫有效 |

**3 项 P0 全部修复。**

---

## 二、守卫测试有效性验证

手动注入语法错误验证：

- **JS 注入** `function broken( {` → `test_js_syntax_valid` **FAIL** ✅ 真实检测
- **CSS 注入** `} /* unmatched */` → `test_css_braces_balanced` **FAIL** ✅ 真实检测

守卫测试不是假阳性，能真正拦截语法破损。

---

## 三、测试运行

```
25/25 passed (0.03s)
```

含 2 个新增守卫测试。全部真实 PASS，0 假阳性。

---

## 四、安全审计

无新增安全风险 ✅

- 删除字段属减法操作，无新攻击面
- 历史数据保留策略正确
- API 不再接收 assignee → 攻击面缩小

---

## 五、代码质量

### ✅ 正确之处

1. **daemon 改动干净**: `_phase_assignee` 删除、L864/L889 路由改为 `_pick_phase_agent`、L1402 stuck 兜底改为 `"panda"`
2. **dashboard API 改动完整**: 创建/更新/响应全部清理
3. **UI 删除干净**: HTML 下拉框、JS 显示逻辑、CSS 死类全部清除
4. **app_v2.py 同步清理**: L455 assignee 字段已删

### P2 — 可改进（不阻塞）

5. **`updateKanbanAssigneeStatus` 空函数保留**: 调用方 `this.updateKanbanAssigneeStatus(statusData)` 仍存在，空函数避免报错但属于死代码。建议未来直接删除调用点和函数定义。**不阻塞**。

6. **daemon 中 `phase_assignee` 变量名**: L589/L639 仍用 `phase_assignee` 作局部变量名（值来自 `_pick_phase_agent`），语义准确但与删除的 `_phase_assignee` 函数名易混淆。**不阻塞**。

7. **CSS L549 注释保留**: `/* assignee 相关样式：不再需要（由 Pipeline 自动路由） */` 是一行解释性注释，可删可留。**不阻塞**。

---

## 六、性能风险

无 ✅

---

## 七、判定

**PASS**

理由：
1. **上轮 3 项 P0 全部修复**: JS 语法正确（node -c 通过）、CSS 括号配对正确、测试新增 JS/CSS 守卫
2. **守卫测试真实有效**: 手动注入语法错误均被检测
3. **25/25 测试全绿**: 0 假阳性
4. **安全无风险**: 减法操作，攻击面缩小
5. **design 12 项改动全部落地**: daemon + dashboard + UI + 测试文件 + app_v2.py

3 项 P2（空函数/变量名/注释）均为未来可清理的代码整洁问题，不影响功能和安全性，不阻塞。
