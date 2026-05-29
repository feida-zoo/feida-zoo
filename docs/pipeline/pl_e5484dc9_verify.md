# Verify 报告: pl_e5484dc9 — 移除需求/问题管理的「指派成员」

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: verify  
**上游**: test commit a6638ac  

---

## 一、测试运行结果

```
0/19 通过（测试无法 collect）
```

**致命错误**: `tests/test_remove_assignee.py` L71 Python 语法错误 — `SyntaxError: unterminated string literal`

```python
# L71: 正则字符串内有真实换行符，未用三引号包裹
stuck_func_match = re.search(r'def _handle_user_pipeline_stuck.*?(?=
def |$)', content, re.DOTALL)
```

应为 `r'def _handle_user_pipeline_stuck.*?(?=\ndef |$)'` 或使用三引号 `r"""..."""`。

**pytest 完全无法加载该文件，0 个用例被执行。**

---

## 二、P0 问题

### P0#1: 测试文件语法错误，无法 collect

L71 正则字符串含裸换行符，Python 解析器报 `SyntaxError`。整个测试套件无法运行，**verify 阶段零测试覆盖**。

### P0#2: `test_stuck_no_assignee_fallback` 匹配错误函数名

测试试图匹配 `def _handle_user_pipeline_stuck`，但 daemon 中实际函数名为 `def _check_stuck_pipelines`（L1390）。

**后果**: 即使语法修复，`re.search` 也找不到目标函数，走入 `else` 分支——`else` 分支仅统计 `stuck` 出现位置，不做任何断言。**当前 stuck 检测的 `req.get("assignee", "")` 兜底（L1421）仍存在，但测试会误判 PASS（假阳性）。**

---

## 三、P1 问题

### P1#3: `test_no_write_assignee_to_req` 的 pending 上下文判断逻辑有误

```python
# 测试代码认为 cur_req['assignee'] 可能出现在 pending 上下文中
for m in matches:
    idx = content.find(m)
    context = content[max(0,idx-50):idx+50]
    if 'pending' in context.lower():
        allowed_contexts.append(m)
```

但 `cur_req['assignee']` 和 `pending_queue` 是不同变量。`cur_req` 是 requirement 对象，`pending_queue` 的 item 才用 `item['assignee']`。**pending 上下文中不会出现 `cur_req['assignee']`，所以这个"允许"判断永远不会触发**——该测试的行为实际是正确的（检测到就 FAIL），但代码意图和逻辑不一致。

### P1#4: `test_create_requirement_no_assignee` 排除逻辑不可靠

```python
if 'data.get(\'assignee\'' in create_req_section or 'data.get("assignee"' in create_req_section:
    if 'issue' not in create_req_section.lower():
        pytest.fail(...)
```

`create_req_section = content.split("def do_POST")[-1]` — 这取的是**最后一个** `do_POST` 之后的所有内容（含 issues handler），`'issue' in create_req_section.lower()` 几乎永远为 True。**该测试可能永远不 fail（假阴性）。**

### P1#5: `test_issue_API_no_assignee` 切割逻辑脆弱

```python
create_issue_section = content.split("/api/issues")[0][-500:]
```

取 `/api/issues` 之前 500 字符，但创建 issue 的 POST handler 在 `/api/issues` 之后。切割方向反了，**该测试大概率不会检测到问题**。

---

## 四、P2 问题

### P2#6: `test_kanban_assignee_display_gone` 正则匹配不精确

```python
detail_assignee = re.findall(r'detail-value.*assignee', content) or \
                  re.findall(r'assignee.*detail-value', content)
```

JS 代码压缩后可能同一行含多个关键词，跨行匹配缺失 `re.DOTALL`。建议改为更精确的 DOM 结构匹配。

### P2#7: 缺少对 `app_v2.py` 的检查

design 和 review 阶段已提到 `app_v2.py` L455 返回 assignee，但测试未覆盖。

---

## 五、判定

**REJECT**

理由：
1. **P0#1**: 测试文件语法错误，0/19 用例可执行，verify 阶段零覆盖
2. **P0#2**: stuck 检测测试匹配错误函数名，即使语法修复也有假阳性
3. **P1#3/4/5**: 3 个测试用例的判断逻辑有假阴性风险

必须修复：
- L71 语法错误（裸换行符 → `\n` 转义或三引号）
- stuck 测试改为匹配 `_check_stuck_pipelines`
- `test_create_requirement_no_assignee` 重新设计 POST handler 分区逻辑
- `test_issue_API_no_assignee` 修正切割方向
