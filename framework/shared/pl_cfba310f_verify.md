# Verify 测试评审报告
## pl_cfba310f — feida_zoo 仓库公开化 + 目录结构整理

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 71486f2

---

## 总体评定：🔴 REJECT

49 用例，排除 `@pytest.mark.delivery` 的 5 个后：44 用例，30 failed / 12 passed / 2 skipped。**非 delivery 通过率 27.3%**。

上次 REJECT 的 5 个致命 bug 已全部修复（路径计算、SKIP_FILES、os.popen 硬编码、delivery 标记、/home/afei/ fallback 豁免）。但测试套件仍有 **2 个逻辑 bug + 1 个设计缺陷**，需要修复。

---

## 1. 测试运行结果

| 指标 | 全量 | 排除 delivery |
|------|------|---------------|
| 总用例 | 49 | 44 |
| 通过 | 12 (24.5%) | 12 (27.3%) |
| 失败 | 35 (71.4%) | 30 (68.2%) |
| 跳过 | 2 (4.1%) | 2 (4.5%) |

---

## 2. 失败分类

### 🔴 类 A：测试逻辑 bug（2 处，影响 3 用例）

#### A1. `test_no_session_key` IndexError

**第 317 行**：
```python
if line.strip().startswith("session:") and ":" not in line.strip().split(None, 1)[1]:
```

当 `session:` 行为 `session:` 无值时（如 `    session:`），`split(None, 1)` 只有 1 个元素，`[1]` 触发 IndexError。

**修复**：加长度检查，或简化为 `re.match(r"^\s+session:\s*$", line)`。

#### A2. `test_zoo_mesh_daemon_framework_dir` 断言过于严格

**第 815 行**：
```python
if "FRAMEWORK_DIR" in line and "os.environ" in line:
    assert "FEIDA_ZOO_HOME" in line, ...
```

当前 `zoo_mesh_daemon.py:15` 使用 `ZOO_FRAMEWORK_DIR` 环境变量：
```python
FRAMEWORK_DIR = os.environ.get("ZOO_FRAMEWORK_DIR", "/Users/zoo/...")
```

设计文档明确 `FRAMEWORK_DIR` 的环境变量是 `ZOO_FRAMEWORK_DIR` 而非 `FEIDA_ZOO_HOME`。测试断言 `FEIDA_ZOO_HOME in line` 会一直失败，因为合法方案是用 `ZOO_FRAMEWORK_DIR`。

**修复**：断言应检查 `"ZOO_FRAMEWORK_DIR" in line or "FEIDA_ZOO_HOME" in line`。

### 🟡 类 B：测试期望与设计文档不一致（影响 2 用例）

#### B1. `test_framework_dir_no_hardcode` 对 os.environ.get fallback 判定有误

**第 278 行**：
```python
if "FRAMEWORK_DIR" in line and "os.environ" in line:
    assert "/Users/" not in line
```

这行代码检测 `FRAMEWORK_DIR = os.environ.get("ZOO_FRAMEWORK_DIR", "/Users/zoo/...")`，断言 `/Users/` 不应出现。但设计文档 `2.6 节` 明确允许 `os.getenv/os.environ.get` 的 fallback 默认值中使用路径。测试的 `/home/afei/` 检查已做了豁免，但 `/Users/zoo/` 检查未做同等豁免。

**修复**：与 `test_no_home_afei_in_source` 一致，对 `os.getenv`/`os.environ.get` 的 fallback 做豁免。

#### B2. `test_no_home_afei_in_source` 遗漏非 ut 目录的文件

当前发现 `verify_git_pipeline.py`、`dashboard/app_simple.py`、`dashboard/app_v2.py`、`dashboard/test_integration.py` 中含 `/home/afei/` 硬编码。这些文件不在 `framework/tests/ut/` 下，而是业务代码或根目录脚本。设计文档的文件清单遗漏了这些文件。

### 🟢 类 C：develop_code 阶段未执行的预期失败（~25 用例）

这些失败全部对应源码中的硬编码路径、脱敏、.gitignore 补全等改动——均尚未执行，属于预期行为：

| 测试类 | 失败数 | 原因 |
|--------|--------|------|
| TestDataDirEnvVar | 2 | app_enhanced.py/develop_executor.py 仍含硬编码 |
| TestIssuesPathEnvVar | 1 | zoo_mesh_daemon.py:761 仍含硬编码 |
| TestQQOpenIdEnvVar::test_no_hardcoded_openid_in_source | 1 | gateway-start.ts 仍含 OpenID |
| TestNoLocalAbsolutePath | 5 | 源码仍含 29 处硬编码 |
| TestZooMembersSanitized | 2 | yaml 仍含 model/session/key（不含 IndexError） |
| TestGitignoreComplete | 4 | .gitignore 缺 venv/node_modules/.env/.DS_Store |
| TestRootScriptsMoved | 4 | scripts/ 不存在，根目录脚本未移 |
| TestDocAndArtifactsCleaned | 1 | docs/ 未删 |
| TestStartDevCenterLogPath | 2 | 日志路径未改 |
| TestTestFilesNoHardcodedPath | 2 | 测试文件仍含硬编码 |
| TestTrackedLogsCleaned | 1 | 日志仍在 git index |
| TestNoSensitiveInfoLeak | 1 | /opt/homebrew/ 路径 |
| TestStartEnhancedShSanitized | 1 | start_enhanced.sh 仍含硬编码 |
| TestIntegrationConsistency | 1 | 日志仍在 git index |
| TestEnvVarInjection | 2 | develop_executor.py/zoo_mesh_daemon.py 未改 |

---

## 3. 上次 REJECT 问题修复确认

| # | 上次问题 | 修复状态 | 验证 |
|---|----------|----------|------|
| 1 | PROJECT_ROOT `.parent` 层级错误 | ✅ 已修复 | `.resolve().parent.parent.parent.parent` |
| 2 | 测试自身未排除在扫描之外 | ✅ 已修复 | SKIP_FILES 含 `test_public_repo_safety.py` |
| 3 | os.popen 硬编码路径 | ✅ 已修复 | 全部改为 `f"cd {PROJECT_ROOT}"` |
| 4 | Git 历史测试与阶段时序不匹配 | ✅ 已修复 | `@pytest.mark.delivery` 标记 |
| 5 | /home/afei/ 合法 fallback 误判 | ✅ 已修复 | os.getenv 豁免逻辑 |

---

## 4. 新发现的测试缺陷

| # | 缺陷 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | `test_no_session_key` IndexError | 🔴 高 | 运行时崩溃，未正确检测 session 字段 |
| 2 | `test_zoo_mesh_daemon_framework_dir` 断言 `FEIDA_ZOO_HOME` 过严 | 🔴 高 | 合法方案 `ZOO_FRAMEWORK_DIR` 也被拒绝 |
| 3 | `/Users/zoo/` 在 os.environ.get fallback 中未豁免 | 🟡 中 | 与 `/home/afei/` 豁免逻辑不一致 |
| 4 | 设计文档文件清单遗漏 `app_simple.py`/`app_v2.py`/`test_integration.py`/`start_enhanced.sh` | 🟡 中 | 这些文件含 `/home/afei/` 硬编码但未被清单覆盖 |

---

## 5. 修复建议

```python
# 修复 1：test_no_session_key IndexError
# 替换整个 session 检测逻辑：
for i, line in enumerate(lines, 1):
    if re.match(r"^\s+session:\s*$", line):
        pytest.fail(f"第 {i} 行仍包含 session 键: {line.strip()}")

# 修复 2：test_zoo_mesh_daemon_framework_dir 断言
if "FRAMEWORK_DIR" in line and "os.environ" in line:
    assert "FEIDA_ZOO_HOME" in line or "ZOO_FRAMEWORK_DIR" in line, ...
# 同理 MESH_DIR

# 修复 3：test_framework_dir_no_hardcode 一致豁免
if "FRAMEWORK_DIR" in line and "os.environ" in line:
    # 与 test_no_home_afei_in_source 一致，允许 os.environ.get 的 fallback
    if ("os.getenv(" in line or "os.environ.get(" in line) and "FEIDA_ZOO_HOME" in line:
        continue
    assert "/Users/" not in line, ...
```

---

## 6. 结论

| 维度 | 上次 | 本次 | 变化 |
|------|------|------|------|
| 致命 bug | 1（路径计算） | 2（IndexError + 断言过严） | 已修复旧问题，引入新问题 |
| 非delivery通过率 | 14.3% | 27.3% | ↑ 提升 |
| 测试可执行性 | 🔴 不可执行 | 🟡 基本可执行（2 bug 需修） | 改善 |

**判定：REJECT** — 测试套件新增 2 个逻辑 bug（IndexError + 过严断言），需修复后重跑。修复量约 10 分钟。

上次 5 个致命问题已全部修复 ✅，进展明确。
