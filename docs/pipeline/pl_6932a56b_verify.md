# Verify 报告: pl_6932a56b — 飝龘动物园 README 更新

**审查人**: 毒刺 (Duci) 🦂  
**日期**: 2026-05-29  
**阶段**: verify  
**上游**: test commit 89a300d  
**测试文件**: `tests/test_readme_update.py`（272 行，24 个用例）

---

## 一、测试运行结果

```
24 collected: 8 passed, 16 failed (通过率 33%)
```

**失败用例全部因为 README.md 尚未更新**（impl 阶段未执行），属于预期失败。8 个通过的用例需逐一审查是否存在假阳性。

---

## 二、假阳性分析（关键问题）

### P0 — 假阳性 #1: `TestRunGuide::test_has_start_command`

```python
assert "bash" in content or "sh " in content or "./" in content or "python" in content
```

**实际匹配**: `"sh "` 匹配到了「系统设计」中的 `"sh "` 子串，而非启动命令。旧 README 无任何启动命令，但测试 PASSED。

**根因**: 检查字符串含空格的子串匹配，中文文本中大量包含 `sh `。

**修复**: 改为检查代码块（\`\`\`bash 或 \`\`\`sh）或更具体的命令模式（如 `python3 `、`./script`）。

### P0 — 假阴性 #2: `TestActiveMembers::test_ex_members_not_in_active_table`

```python
assert "归档" in member_section or "已退出" in member_section
```

**实际匹配**: `"归档"` 匹配到了 Aeterna 的职责描述「记忆**归档**、文档撰写」，而非真正的成员归档标注。旧 README 的 Weaver/Aeterna/Gulu 在活跃成员表中，但测试误判为通过。

**根因**: 未区分"归档"作为职责描述 vs 作为成员分类标签。

**修复**: 检查是否有独立的「归档成员」小节标题（如 `### 归档成员` 或 `> 归档成员`），而非在整节中搜索"归档"字样。

### P1 — 假阳性 #3: `TestScreenshotPathStable::test_screenshots_in_stable_dir`

```python
assert exists_in_stable or exists_in_old, "截图文件未找到"
```

当前截图在 `docs/pipeline/`（old），不在 `docs/screenshots/`（stable）。测试仍 PASSED，因为 `or exists_in_old` 兜底。

**根因**: 测试逻辑等于"只要截图存在就行"，完全没检验 review P1#9（截图应迁移到稳定目录）。

**修复**: 应分两步——先断言截图存在，再断言必须在 stable 目录而非 pipeline 目录。移除 `or exists_in_old` 兜底，或改为：先 assert 存在，再 assert `exists_in_stable`。

---

## 三、测试覆盖度评审

### 设计文档 8 项检查点覆盖情况

| 检查点 | TC 编号 | 覆盖 | 问题 |
|--------|---------|------|------|
| README 存在 | TC-001 | ✅ | 无 |
| 成员列表（活跃/归档拆分） | TC-002 | ⚠️ | 归档检测假阴性 |
| 核心守则完整 | TC-003 | ⚠️ | 检查逻辑不够精确（长度阈值50字太低） |
| 截图 ≥3 张 | TC-004 | ✅ | 文件存在+非空检查正确 |
| 项目概述 | TC-005 | ✅ | 无 |
| 目录结构 | TC-006 | ✅ | 无 |
| 运行指南 | TC-007 | ⚠️ | 启动命令检测假阳性 |
| Pipeline+技术栈+贡献 | TC-008 | ✅ | 无 |

### 边界用例缺失

4. **截图引用格式未校验**: 仅检查截图文件名在 README 中出现，未验证 Markdown 引用语法正确（如 `![...](docs/screenshots/...)` 格式）。

5. **归档成员信息完整性未校验**: 只检查归档标注存在，未验证归档成员的姓名/emoji/职责是否包含。

6. **README 中无硬编码路径**: design 提到用 `${FEIDA_ZOO_HOME}` 替代硬编码路径，但测试未检查 README 中是否残存 `/home/afei/` 等敏感路径。

7. **截图文件尺寸上限**: 检查了 >10KB 下限，未检查上限（如单张 >2MB 可能不必要）。

8. **Markdown 格式有效性**: 未检查表格语法（`|---|` 分隔行是否存在）。

---

## 四、测试代码质量问题

9. **`_read_readme()` 异常处理无效**:
```python
pytest.raises(AssertionError) if not os.path.exists(README_PATH) else None
```
这行代码只是 `pytest.raises(AssertionError)` 作为表达式求值（返回 context manager 但未使用），不会触发断言。文件不存在时应直接 `assert os.path.exists(README_PATH)` 或 `pytest.skip`。

10. **Pipeline 阶段列表与实际不符**: 测试期望 `["design", "review", "develop", "test", "audit", "deliver"]`，缺少 `"requirement"` 阶段。实际 Pipeline 有 7 阶段。

11. **截图 fallback 逻辑降低检验标准**: `_screenshot_exists()` 同时搜索 `docs/screenshots/` 和 `docs/pipeline/`，与 `test_screenshots_in_stable_dir` 的意图矛盾。

---

## 五、改进建议

| 优先级 | # | 问题 | 修复方案 |
|--------|---|------|----------|
| P0 | 1 | 启动命令假阳性 | 改为检查代码块 `\`\`\`bash` 或正则 `\(python3?\s|./\w+)` |
| P0 | 2 | 归档检测假阴性 | 检查 `### 归档` 子标题存在，而非在全文搜索"归档" |
| P1 | 3 | 截图路径测试不检验 stable | 移除 `or exists_in_old`，断言必须在 `docs/screenshots/` |
| P1 | 6 | 未检查硬编码路径 | 新增测试：README 中无 `/home/` 或 `/Users/` 路径 |
| P1 | 10 | Pipeline 阶段不全 | 加入 `"requirement"` |
| P2 | 4 | 截图引用格式未校验 | 正则检查 `!\[.*\]\(.*\.png\)` 格式 |
| P2 | 9 | `_read_readme()` 无效异常处理 | 改为 `assert` 或 `pytest.skip` |

---

## 六、判定

**REJECT**

理由：
1. **P0 假阳性 ×2**: `test_has_start_command` 和 `test_ex_members_not_in_active_table` 在旧 README（未更新）上误报通过，意味着这两个关键检查点在 impl 完成后也可能产生假阳性，无法真正守卫质量
2. **P1 截图路径检验形同虚设**: `test_screenshots_in_stable_dir` 的 `or exists_in_old` 兜底使 review P1#9 的要求完全不被执行
3. **16/24 失败的根因是 README 未更新**，这本身不是测试的错，但假阳性意味着即使 impl 质量不达标，测试也可能误判通过

需修复后重新提交 test commit。
