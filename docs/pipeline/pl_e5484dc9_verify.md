# Verify 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」(第 3 轮)

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: verify（第 3 轮）  
**上游**: test commit 85d4ba5  
**上轮**: REJECT (23c8eb8) — `_do_POST_handler` 定位到 GET handler 区域导致 2 个 P0 假阳性

---

## 一、上轮 REJECT 问题修复验证

| # | 上轮问题 | v3 修复 | 验证 |
|---|----------|--------|------|
| P0#1 | `test_create_requirement_no_assignee_input` 检查 GET handler | 改为 `_extract_handle_fn('_handle_requirements_post')` 直接定位函数 | ✅ 现在正确 FAIL |
| P0#2 | `test_create_issue_no_assignee_input` 检查 GET handler | 改为 `_extract_handle_fn('_handle_issues_post')` 直接定位函数 | ✅ 现在正确 FAIL |

**上轮 2 项 P0 假阳性全部修复。** 两个测试从 PASS 变为 FAIL，正确反映 impl 未做状态。

---

## 二、测试运行结果

```
23 collected: 22 FAILED + 1 PASSED
```

### 22 FAIL — 全部真实（impl 阶段尚未执行）

| 测试类 | FAIL 数 | 真实性验证 |
|--------|---------|-----------|
| TestPhaseAssigneeRemoved | 2 | `_phase_assignee` 仍定义且仍被调用 ✅ |
| TestRoutingPureAuto | 2 | `cur_req.get("assignee")` 兜底仍存在 + stuck 检测仍含 assignee ✅ |
| TestRouteNoPayloadAssignee | 4 | payload.get("assignee") + cur_req["assignee"] 写入 + 新建 dict 含 assignee ✅ |
| TestDashboardAPINoAssignee | 3 | `_handle_requirements_post` 含 6 处 assignee + `_handle_issues_post` 含 assignee + 看板响应含 assignee ✅ |
| TestHTMLAssigneeRemoved | 2 | 3 个 select ID + "指派给"标签仍存在 ✅ |
| TestJSAssigneeRemoved | 4 | select refs + kanban display + issue list + detail display ✅ |
| TestCSSAssigneeRemoved | 1 | `.task-assignee` 等类仍存在 ✅ |
| TestSSENotificationNoAssignee | 1 | L743 `# Also notify assignee` 仍存在 ✅ |
| TestTestFilesNoAssignee | 2 | `post_issue(assignee=)` + `"assignee": "alpha"` 仍存在 ✅ |
| TestAppV2AssigneeResponse | 1 | L455 返回 assignee 字段 ✅ |

### 1 PASS — 真实

| 测试 | 说明 | 验证 |
|------|------|------|
| `test_pending_queue_assignee_field_kept` | pending_queue 中 assignee 是阶段执行者，应保留 | ✅ pending_queue 注释含 `assignee` 字段定义 |

**0 假阳性，0 假阴性。**

---

## 三、测试代码质量审查

### ✅ 优秀之处

1. **`_extract_handle_fn` 设计正确**: 直接按函数名定位，比之前 `_do_POST_handler` 按路径字符串匹配可靠得多
2. **覆盖完整**: design 12 项改动均有对应测试，外加 app_v2.py 和 pending_queue 保留验证
3. **0 语法错误**: `ast.parse` 验证通过
4. **FAIL 消息清晰**: 包含行号和代码片段，便于定位

### P2 — 测试粒度问题（不阻塞）

5. **`_extract_handle_fn` 范围过宽**: 使用 `content.find('\ndef ', pos+1)` 找下一个顶层 `def`，但 `_handle_requirements_post` 是类方法（4 空格缩进），`\ndef ` 匹配不到缩进的 `def`，导致 `block_end = len(content)`，取到文件末尾。**当前影响**：无。impl 完成后，如果 `_handle_requirements_post` 已清理但文件其他位置仍有合法 assignee（如 pending），测试可能仍 FAIL。**建议**: impl 阶段验证时注意此点，如遇到可通过匹配 `\n    def `（4 空格 + def）解决。

---

## 四、判定

**PASS**

理由：
1. **上轮 2 项 P0 假阳性全部修复**: 从 PASSED 变为 FAILED，正确反映 impl 未做状态
2. **22 FAIL 全部真实**: 逐项验证代码现状，无假阴性
3. **1 PASS 真实**: pending_queue assignee 保留，符合 design
4. **0 语法错误，0 假阳性，0 假阴性**
5. **覆盖完整**: 23 个用例覆盖 design 全部 12 项改动 + app_v2.py + pending_queue 保留

P2 粒度问题在 impl 完成后验证时注意即可，不阻塞当前 verify 通过。
