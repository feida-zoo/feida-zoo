# Audit 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: audit  
**上游**: impl commit 5341030  
**改动范围**: 9 个文件，+33/-157

---

## 一、安全审计

### ✅ 无安全风险

- 无 SQL 注入、XSS、硬编码密钥
- 删除字段属于减法操作，无新增攻击面
- 历史数据保留策略正确

---

## 二、代码质量 — **P0 致命缺陷**

### 🚨 P0#1: dev_center.js 语法错误，浏览器无法解析

```bash
$ node -c dashboard/static/dev_center.js
dashboard/static/dev_center.js:383
        });
         ^
SyntaxError: Unexpected token ')'
```

**根因**: `updateKanbanAssigneeStatus` 函数中只删除了 `forEach((el) => {`，但未删除 forEach 内部的代码块（含 `if (status) {...}`）和闭合符 `});`：

```javascript
// L373-384 当前状态（损坏）:
updateKanbanAssigneeStatus(statusData) {
    // assignee 由 Pipeline 自动路由，看板不再显示执行者状态
        
        if (status) {                           // ← 孤立代码块
            if (status === 'executing') {
                el.classList.add('is-executing');  // ← el 未定义
            } else {
                el.classList.remove('is-executing');
            }
        }
    });                                          // ← 孤立 });
}
```

**影响**: **整个 dashboard 前端崩溃**。浏览器加载 JS 时直接 SyntaxError，所有 dashboard 功能完全不可用——看板/聊天/SSE/需求/问题管理**全部白屏**。

### 🚨 P0#2: dev_center.css 语法损坏，含 2 处 unmatched `}`

```bash
$ python3 -c '...'
最终深度: 0
L552: 多余的 } (depth=-1)
L1011: 多余的 } (depth=-1)
```

**位置 1**（L549-552）:
```css
/* assignee 相关样式：不再需要（assignee 由 Pipeline 自动路由） */
    object-fit: cover;          /* ← 孤立属性，无选择器 */
    border: 1px solid var(--border-color);
}                                /* ← 孤立 } */
```

**根因**: 删除 `.assignee-avatar-img { width:...; height:...; border-radius: 50%; }` 块时，**只删除了前 3 个属性和选择器开头**，保留了后 2 个属性 `object-fit/border` 和闭合符 `}`。

**位置 2**（L1009-1011）:
```css
/* 看板头像活跃动画 */
/* 执行中头像活跃动画（已删除 — 由 Pipeline 自动路由） */
}                                /* ← 孤立 } */
```

**根因**: 删除 `.task-assignee.is-executing .assignee-avatar { ... }` 块时漏删 `}`。

**影响**: 现代浏览器 CSS parser 遇到 unmatched `}` 后会**跳过当前规则集到下一个 `;` 或 `}`**，导致 `.task-phase`（L554）和 `pulse-green` 动画（L1013）之间的样式部分**可能渲染异常**。即使浏览器宽容处理，CSS lint/validator 会报错，且后续维护时定位规则极其困难。

### 🚨 P0#3: 测试设计根本性缺陷 — 仅文本匹配，不验证可运行性

**致命问题**: 测试 23/23 全部 PASS，但代码同时有 JS SyntaxError 和 CSS 语法损坏。**测试只检查 `assignee` 字符串是否消失，完全没验证代码是否能解析/运行。**

如果测试包含：
- `node -c dev_center.js` 或简单 JS lint
- `css depth check` 简单括号匹配验证

则这两个 P0 会被立即发现。当前测试完全失去守卫作用。

---

## 三、其他问题

### P1#4: HTML 留下空 `form-group` 占位

dev_center.html L200/L331 附近留下空行（原 form-group 块位置），无残留元素但 diff 不干净。**建议**: impl 阶段同时删除空白行。**不阻塞**。

### P2#5: SSE 通知注释保留

```python
# L737: 由 Pipeline 自动路由，不再发送额外通知
```

注释保留是好习惯，标明原意，无问题。

### P2#6: stuck 检测 fallback 改为 `"panda"`

```python
# L1402:
assignee = phase_agent or "panda"
```

`_pick_phase_agent` 几乎不会返回空（zoo_members.yaml 配置兜底），所以 `"panda"` 实际很少触发。但语义上把 stuck 任务默认甩给 panda 仍略生硬，review 阶段已提及，**不阻塞**。

---

## 四、性能风险

无。

---

## 五、判定

**REJECT**

理由（任一即可阻塞）：

1. **P0#1**: dev_center.js L383 SyntaxError — **整个 dashboard 前端不可用**。这是阻断性 Bug，用户打开 dashboard 看到白屏，需求完全无法验证。

2. **P0#2**: dev_center.css 2 处 unmatched `}` — CSS 部分规则可能被浏览器跳过，UI 渲染异常。

3. **P0#3**: 测试设计缺陷暴露 — 23/23 全绿但代码崩溃，**测试守卫完全失效**。verify 阶段未发现因为测试只做文本匹配。

**必须修复**：
- dev_center.js L373-384 `updateKanbanAssigneeStatus` 函数体完全清理（删除孤立的 if 块和 `});`）
- dev_center.css L549-552 删除孤立的 `object-fit/border/}`，L1011 删除孤立 `}`
- 修复后重新跑测试 + 手动 `node -c` 和 CSS 括号验证

**附加建议**（impl 阶段同步修）：
- 测试套件加 `test_js_syntax_valid` (node -c) 和 `test_css_braces_balanced`（简单括号配对）
