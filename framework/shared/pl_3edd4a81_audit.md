# Audit 阶段代码审计报告 — pl_3edd4a81

**需求标题**: 需求管理和问题管理页已解决或者已关闭的项目按时间顺序由新到旧排序，开启中的项目按优先级由高到低排序

**审计日期**: 2026-05-27
**审计人**: 毒刺 🦂

**代码提交**: 9b6b528 → 925a49d（`🐢 feat: 需求管理和问题管理页分组排序`）

---

## 1. 安全漏洞

### 1.1 🔴 XSS：问题管理页 priority 回退渲染直接输出原始值

**位置**: `dev_center.js:1323`
```javascript
${priorityLabels[issue.priority] || issue.priority}
```

当 `issue.priority` 不在 `priorityLabels` 映射中时（如被篡改为 `<script>alert(1)</script>`），回退直接输出 `issue.priority` 原始值到 innerHTML，构成 **存储型 XSS**。

攻击路径：`PUT /api/issues/:id` → `data.priority` 未经校验直接写入 → 前端渲染时注入。

**需求数据页无此问题**（`dev_center.js:1650`）：`PRIORITY_LABELS[r.priority] || 'P3低'`，回退为安全字符串。

**修复**：
```javascript
// 方案A：回退也用映射值
${priorityLabels[issue.priority] || priorityLabels['P3']}

// 方案B：escapeHtml 兜底
${priorityLabels[issue.priority] || escapeHtml(issue.priority)}
```

### 1.2 🔴 后端 priority 白名单校验缺失（review 阶段明确要求，未落实）

**位置**: `app_enhanced.py`

| 端点 | 行号 | 当前处理 | 问题 |
|------|------|----------|------|
| `_handle_requirements_post()` | 693 | `(data.get('priority') or 'P3').upper()` | 仅 `.upper()`，无白名单 |
| `_handle_issues_post()` | 960 | `(data.get('priority') or 'P3').upper()` | 同上 |
| `_handle_issues_put()` | 1054 | `issue['priority'] = data['priority']` | 连 `.upper()` 都没有 |

Review 阶段 P0 要求："后端 priority 白名单校验——仅允许 P0/P1/P2/P3，非法值 fallback P3"。**未落实**。

可构造请求 `PUT /api/issues/:id` with `priority: "<img onerror=alert(1)>"`，直接写入 JSON 存储，再由 1.1 的 XSS 路径触发。

**修复**：
```python
VALID_PRIORITIES = {'P0', 'P1', 'P2', 'P3'}

# _handle_requirements_post / _handle_issues_post
priority = (data.get('priority') or 'P3').upper()
if priority not in VALID_PRIORITIES:
    priority = 'P3'

# _handle_issues_put
if 'priority' in data:
    p = data['priority'].upper()
    issue['priority'] = p if p in VALID_PRIORITIES else 'P3'
```

### 1.3 🟢 其他安全检查

| 检查项 | 结果 |
|--------|------|
| SQL 注入 | 无风险（JSON 文件存储，无查询构造） |
| 硬编码密钥 | 未引入 |
| CSRF | 原有状态，非本次引入 |
| 数据越权 | 原有状态，非本次引入 |

---

## 2. 代码质量

### 2.1 🟡 agentNames 对象重复 key

**位置**: `dev_center.js:1639-1640`
```javascript
const agentNames = {
    'alpha': '🐢 阿尔法',
    'alpha': '🐢 阿尔法',  // 重复 key
    'duci': '🦂 毒刺',
    'panda': '🐼 达达'
};
```

JS 对象重复 key 不报错，后值覆盖前值。功能不受影响但代码不干净。

### 2.2 🟢 排序函数命名与结构

`sortRequirementsForDisplay()` 和 `sortIssuesForDisplay()` 命名清晰，逻辑集中，分组策略与 design 一致。常量 `PRIORITY_ORDER`、`TERMINAL_REQ_STATUSES`、`CLOSED_ISSUE_STATUSES` 提取为模块级变量，可维护。

### 2.3 🟢 后端排序移除

`app_enhanced.py:899` 移除 `issues.sort(...)` 并加注释 `# 排序已由前端统一处理`，语义清晰。

### 2.4 🟢 前端 `.reverse()` hack 移除

`loadRequirementsList()` 中 `reqs.slice().reverse()` 已替换为 `sortRequirementsForDisplay(reqs)`。

### 2.5 🟢 HTML 表单

`dev_center.html` 新增 `<select id="req-priority">` 结构与 issue 表单的优先级选择器一致，选项顺序 P3→P0（低→高）与已有模式相同。

### 2.6 🟢 CSS 样式

`.req-priority-badge` 及 `.p0`~`.p3` 四个子类完整定义，与 issue 页 `.issue-priority-badge` 风格统一。

---

## 3. 性能风险

| 风险 | 等级 | 说明 |
|------|------|------|
| 前端全量排序 | 无 | 当前数据 <50 条，filter+sort 开销可忽略 |
| 排序函数每次调用新建数组 | 无 | `.filter()` + `.sort()` + `.concat()` 标准做法 |
| 后端移除排序影响其他消费者 | 低 | 若有其他客户端调用 `GET /api/issues`，返回顺序变为插入序。当前仅 dashboard 消费，风险可控 |

---

## 4. 测试覆盖

**测试文件**: `dashboard/test_priority_sort.py`，29 测试全过。

| 测试类 | 用例数 | 覆盖点 |
|--------|--------|--------|
| `TestRequirementSortLogic` | 7 | 开启前于关闭、优先级排序、时间倒序、fallback、默认P3、终端状态归类、混合 |
| `TestIssueSortLogic` | 6 | 同上 + 筛选后排序 |
| `TestBackendRequirementPriority` | 2 | priority 字段存在、默认 P3 |
| `TestBackendIssueSortRemoval` | 1 | 验证排序行移除 |
| `TestFrontendCodeStructure` | 5 | HTML/CSS/JS 结构验证 |
| `TestKanbanNotAffected` | 1 | 看板不受影响 |
| `TestEndToEndSortBehavior` | 3 | 空列表/全开启/全关闭 |

**未覆盖**：
- PUT 接口的 priority 白名单校验（因尚未实现）
- XSS payload 注入测试

---

## 5. 结论

**REJECT ❌**

两个安全漏洞必须修复才能 pass：

1. **🔴 XSS（§1.1）**：`loadIssues()` 第 1323 行 priority 回退直接输出原始值到 innerHTML。与 §1.2 组合即构成完整攻击链：恶意 priority 值经 PUT API 写入 → 前端渲染触发 XSS。
2. **🔴 priority 白名单校验缺失（§1.2）**：Review 阶段 P0 明确要求，未落实。三个端点（POST requirements / POST issues / PUT issues）均无白名单校验。

**修复工作量**：约 10 行代码。后端加 `VALID_PRIORITIES` 校验 + 前端回退改为安全映射值即可。

**修复后可直接 pass，无需重新走 design/review 流程。**
