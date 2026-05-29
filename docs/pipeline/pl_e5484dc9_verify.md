# Verify 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」(第 2 轮)

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: verify（第 2 轮）  
**上游**: test commit 331785b  
**上轮**: REJECT (b0a5832) — 测试文件 L71 语法错误 + stuck 函数名错误 + 3 处假阴性风险

---

## 一、上轮 REJECT 问题修复验证

| # | 上轮问题 | v2 修复 | 验证 |
|---|----------|--------|------|
| P0#1 | L71 正则裸换行符语法错误 | 改为纯字符串搜索 `content.find('def _check_stuck_pipelines')` | ✅ ast.parse 通过 |
| P0#2 | stuck 匹配 `_handle_user_pipeline_stuck` 错误函数名 | 改为 `_check_stuck_pipelines` | ✅ 测试 FAIL 正确反映 daemon 现状 |
| P1#3 | `test_no_write_assignee_to_req` pending 上下文判断逻辑误 | 拆分为 `test_no_write_assignee_to_cur_req` + `test_new_req_dict_no_assignee` | ✅ 逻辑清晰 |
| P1#4 | `test_create_requirement_no_assignee` 切割逻辑错 | 改用 `_do_POST_handler` 提取 handler 块 | ❌ **见 P0#1（新问题）** |
| P1#5 | `test_issue_API_no_assignee` 切割方向反 | 改用 `_do_POST_handler` 提取 handler 块 | ❌ **见 P0#1（新问题）** |

**上轮 P0 全部修复，但 P1 修复引入新的 P0 假阳性问题。**

---

## 二、测试运行结果

```
23 collected: 20 FAILED + 3 PASSED
```

| FAIL 分类 | 数量 | 预期 |
|----------|------|------|
| daemon 改动未做（_phase_assignee 仍存在等） | 8 | ✅ 真实 FAIL |
| dashboard API 改动未做 | 1 | ✅ 真实 FAIL |
| HTML 改动未做 | 2 | ✅ 真实 FAIL |
| JS 改动未做 | 4 | ✅ 真实 FAIL |
| CSS 改动未做 | 1 | ✅ 真实 FAIL |
| SSE 通知改动未做 | 1 | ✅ 真实 FAIL |
| 测试文件清理未做 | 2 | ✅ 真实 FAIL |
| app_v2.py 改动未做 | 1 | ✅ 真实 FAIL |

20 个 FAIL 全部为真实反映 impl 阶段尚未做的改动，**无假阴性**。

---

## 三、3 个 PASSED 用例的假阳性审查

### ✅ `test_pending_queue_assignee_field_kept` — 真实 PASS

pending_queue 中 assignee 字段确实保留，符合 design 意图。

### ❌ `test_create_requirement_no_assignee_input` — **假阳性 P0**

测试代码：
```python
def _do_POST_handler(self, handler_sig):
    pos = content.find(handler_sig)  # 找 '"/api/requirements"'
    block_start = content[:pos].rfind('\n') + 1
    block_end = content.find('\n    def ', block_start + 1)
    return content[block_start:block_end]
```

**问题**: `_do_POST_handler('"/api/requirements"')` 找到的是字符串 `'/api/requirements'`（单引号），在源文件中**第一个匹配是 GET handler 区域**（L520），而真正的创建 POST handler 是 `_handle_requirements_post`（L662）。

**实证**:
- 测试取到的 handler_code (L18296-19833): GET handler 路由表 → 无 assignee
- 实际的 `_handle_requirements_post` (L662-806): **含 6 处 assignee**:
  ```python
  L686: assignee = (data.get('assignee') or '').strip()
  L695: "assignee": assignee,
  L725: "assignee": assignee,
  L743: # Also notify assignee if different from panda
  L744: if assignee and assignee != 'panda':
  L750: 'content': f"@{assignee} 新需求已创建: ..."
  ```

测试 PASS 但 daemon 改动完全没做。**完全假阳性**。

### ❌ `test_create_issue_no_assignee_input` — **假阳性 P0**

同样问题：`_do_POST_handler('"/api/issues"')` 找到的是 GET handler 区域。

实际的 `_handle_issues_post` (L1243) 含：
```python
"assignee": (data.get('assignee') or '').strip(),
```

测试 PASS 但代码未改。**完全假阳性**。

---

## 四、P1 问题

### P1#4: `test_assignee_label_gone` 检查 '指派给' 字符串过粗

```python
assert '指派给' not in content, "HTML 中仍存在'指派给'标签"
```

如果 impl 阶段删除了下拉框但保留了 placeholder 类似 `"指派给某人"`，这个测试可能误判。**建议**: 改为定位到具体 label 元素。**不阻塞当前 verify。**

### P1#5: `test_kanban_response_no_assignee` 上下文检测脆弱

```python
context_start = max(0, content[:content.find(stripped, max(0,i*30-500))].rfind('\ndef ', 0))
```

`i*30-500` 估算位置极其不稳定，且 `content.find(stripped, ...)` 可能找到完全无关的同名行。**建议**: impl 阶段验证时单独跑此测试确认正确。**不阻塞当前 verify。**

---

## 五、判定

**REJECT**

理由：
1. **P0 假阳性**: `test_create_requirement_no_assignee_input` 和 `test_create_issue_no_assignee_input` 通过 GET handler 区域误判 PASS，实际真正的 POST handler `_handle_requirements_post` (L662) 和 `_handle_issues_post` (L1243) 仍含 6+ 处 assignee 处理代码。这两个测试相当于失效。

2. **核心质量风险**: TC-003 Dashboard API 创建逻辑是整个 design 的关键改动之一，但测试根本没检查到真正的代码，意味着即使 impl 阶段完全不改 `_handle_requirements_post`，测试也会 PASS。这是严重的守卫失效。

必须修复：
- `_do_POST_handler` 改为直接定位 `def _handle_requirements_post`/`def _handle_issues_post` 函数体
- 或新增 `test_handle_requirements_post_no_assignee` 直接检查函数体
- 验证修复后这两个测试在当前 daemon 状态下应 FAIL（因为代码未改）
