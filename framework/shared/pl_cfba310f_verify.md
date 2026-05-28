# Verify 测试评审报告
## pl_cfba310f — feida_zoo 仓库公开化 + 目录结构整理

**审查人**: Duci 🦂 | **日期**: 2026-05-28 | **上游 commit**: 0f22bf6

---

## 总体评定：🔴 REJECT

49 个测试用例，34 failed / 7 passed / 8 skipped。**通过率 14.3%**。

测试套件存在 **1 个致命 bug + 5 类设计缺陷**，在 develop_code 产出来看这些失败全部属于预期行为（代码改动尚未执行），但测试套件本身的质量问题需要修复。

---

## 1. 测试运行结果

| 指标 | 数值 |
|------|------|
| 总用例 | 49 |
| 通过 | 7 (14.3%) |
| 失败 | 34 (69.4%) |
| 跳过 | 8 (16.3%) |

---

## 2. 失败根因分类

### 🔴 类 A：PROJECT_ROOT 路径计算致命 bug（影响 10+ 用例）

**根因**：测试文件第 48 行：

```python
TEST_HOME = os.environ.get("FEIDA_ZOO_HOME", str(Path(__file__).parent.parent.parent))
PROJECT_ROOT = Path(TEST_HOME)
```

`__file__` = `framework/tests/ut/test_public_repo_safety.py`
- `.parent` = `framework/tests/ut/`
- `.parent.parent` = `framework/tests/`
- `.parent.parent.parent` = `framework/`  ← **错误！** 应为项目根目录

结果：所有相对路径计算变成 `framework/dashboard/app_enhanced.py`、`framework/framework/core/mesh/...`，全部 FileNotFoundError。

**修复**：应为 `.parent.parent.parent.parent`（向上 4 级：ut → tests → framework → 项目根）。

**影响用例**：TestDataDirEnvVar ×3、TestIssuesPathEnvVar ×1、TestQQOpenIdEnvVar::test_no_hardcoded_openid_in_source、TestRootScriptsMoved::test_scripts_dir_exists + test_symlinks_or_moved、TestIntegrationConsistency::test_zoo_members_yaml_valid、TestEnvVarInjection ×2。

### 🟡 类 B：测试自身包含 `/Users/zoo/`（影响 3+ 用例）

**根因**：测试文件自身 docstring（第 27 行）和正则定义（第 44 行）包含 `/Users/zoo/` 字面量，被自身的全文件扫描检测到。

`test_no_users_zoo_in_source` 扫描 `.py` 文件时匹配到 `test_public_repo_safety.py` 自身。

**修复**：
1. 将测试文件自身加入 `SKIP_FILES`
2. 或将正则中的 `/Users/zoo/` 改为字符串拼接避免匹配

### 🟡 类 C：symlink 环境差异（影响 1 用例）

**根因**：`/Users/zoo/workspace/code/feida_zoo` 是 `/Volumes/data/workspace/code/feida_zoo` 的 symlink。`Path(__file__).resolve()` 解析到 `/Volumes/data/...`，导致 `p = PROJECT_ROOT / "dashboard" / "app_enhanced.py"` 路径不匹配。

pytest 的工作目录是 symlink 路径，而 `Path(__file__).parent` resolve 后是物理路径，两者不一致。

**修复**：`PROJECT_ROOT` 应使用 `Path.cwd()` 或 `Path(__file__).resolve().parent.parent.parent.parent`。

### 🟡 类 D：当前仓库状态未改动——测试检查的是 develop_code 后的状态（影响 ~20 用例）

这些失败不是测试 bug，而是 **develop_code 阶段尚未执行**导致的预期失败：

| 测试类 | 失败原因 |
|--------|----------|
| TestNoLocalAbsolutePath::test_no_users_zoo_in_source | 源码仍有 29 处 `/Users/zoo/` |
| TestNoLocalAbsolutePath::test_no_home_afei_in_source | spawner.py/permissions.py 仍有 `/home/afei/` |
| TestZooMembersSanitized ×3 | yaml 仍含 model/session/key |
| TestGitEmailRewritten ×3 | 仍有 super_afei@qq.com |
| TestGitignoreComplete ×7 | .gitignore 缺 venv/node_modules 等 |
| TestStartDevCenterLogPath ×2 | 日志仍在 dashboard/ |
| TestTrackedLogsCleaned ×1 | 日志仍在 git index |
| TestNoSensitiveInfoLeak ×1 | gateway-start.ts 含 /opt/homebrew/ |

**结论**：这类失败属于预期行为，不构成 reject 理由。

### 🔴 类 E：Git 历史检查误判——不应在 verify 阶段检查（影响 2 用例）

`test_no_openid_in_git_history` 和 `test_git_log_no_afei_paths` 检查 git 历史中的敏感信息残留。

**问题**：
1. Git 历史重写（`filter-branch`）应在 **deliver 阶段最后一步**执行，因为重写历史不可逆，必须在所有代码改动完成后执行
2. 在 verify 阶段运行这些测试必然失败（历史还没重写）
3. 这些测试应标记为 `@pytest.mark.delivery` 或类似标记，仅在 deliver 阶段后执行

---

## 3. 测试用例质量评审

### 3.1 覆盖度：✅ 优秀（14 个测试类，49 个用例）

| 需求项 | 测试覆盖 | 评价 |
|--------|----------|------|
| DATA_DIR 环境变量 | 3 用例 | ✅ |
| issues_path 环境变量 | 1 用例 | ✅ |
| QQ OpenID 环境变量 | 2 用例 | ✅（含历史检查） |
| 本地绝对路径替换 | 5 用例 | ✅ |
| zoo_members.yaml 脱敏 | 4 用例 | ✅ |
| Git 邮箱重写 | 3 用例 | ✅ |
| .gitignore 补全 | 7 用例 | ✅ |
| 根目录脚本移动 | 5 用例 | ✅ |
| docs/artifacts 清理 | 3 用例 | ✅ |
| 日志路径修改 | 2 用例 | ✅ |
| 测试文件硬编码 | 3 用例 | ✅ |
| 入库日志清理 | 2 用例 | ✅ |
| 敏感信息综合 | 3 用例 | ✅ |
| 集成测试 | 4 用例 | ✅ |
| 环境变量注入 | 2 用例 | ✅ |

### 3.2 边界用例：🟡 不足

| 缺失边界 | 说明 |
|----------|------|
| 环境变量未设置时的 fallback 行为 | 未测试 `FEIDA_ZOO_HOME` 为空或非法值时的行为 |
| symlink 兼容性 | 未考虑 `/Users/zoo/` → `/Volumes/data/` 的 symlink 场景 |
| 编译产物一致性 | gateway-start.ts 修改后应验证 `.js` 编译产物同步 |
| 竞态条件 | 多个环境变量缺失时的启动行为 |

### 3.3 测试自身质量缺陷

| # | 缺陷 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | **PROJECT_ROOT 路径计算错误**（.parent 多了一级） | 🔴 致命 | 10+ 用例全部 FileNotFoundError |
| 2 | **测试自身未排除在扫描之外** | 🟡 高 | 自身 `/Users/zoo/` 字面量被误报 |
| 3 | **硬编码 `/Users/zoo/` 路径在 os.popen 中** | 🟡 中 | 第 204、211、766 等行使用硬编码路径调用 git |
| 4 | **Git 历史测试与 develop_code 阶段时序不匹配** | 🟡 高 | 应分离到 deliver 后执行 |
| 5 | **`/home/afei/` 正则与合法默认值冲突** | 🟡 中 | spawner.py/permissions.py 的 fallback 默认值被误判为硬编码 |

---

## 4. 具体修复建议

### 4.1 必须修复（阻塞性）

```python
# 修复 1：PROJECT_ROOT 路径计算
# 当前（错误）：
TEST_HOME = os.environ.get("FEIDA_ZOO_HOME", str(Path(__file__).parent.parent.parent))
# 修复为：
TEST_HOME = os.environ.get("FEIDA_ZOO_HOME", str(Path(__file__).resolve().parent.parent.parent.parent))
```

```python
# 修复 2：排除测试自身
SKIP_FILES = {
    ".gitkeep",
    "pl_cfba310f_design.md",
    "pl_cfba310f_review.md",
    "pl_cfba310f_verify.md",
    "test_public_repo_safety.py",  # ← 新增
}
```

```python
# 修复 3：os.popen 中的硬编码路径改为 PROJECT_ROOT
# 当前：
"cd /Users/zoo/workspace/code/feida_zoo && ..."
# 修复为：
f"cd {PROJECT_ROOT} && ..."
```

### 4.2 建议修复（非阻塞）

```python
# 建议 1：Git 历史测试标记为 deliver 阶段
@pytest.mark.delivery
def test_no_openid_in_git_history(self):
    ...

# 建议 2：/home/afei/ 检查排除合法 fallback
# spawner.py 和 permissions.py 中 os.getenv("FEIDA_ZOO_HOME", "/home/afei/...") 是合法默认值
# 测试应检查是否在 os.getenv/os.environ.get 的 fallback 中出现，而非一刀切
```

---

## 5. 结论

| 维度 | 评价 |
|------|------|
| 测试覆盖度 | ✅ 优秀（49 用例，14 测试类，覆盖全部 13 项需求） |
| 边界用例 | 🟡 不足（缺 fallback 行为、symlink、编译产物一致性） |
| 测试可执行性 | 🔴 不可执行（PROJECT_ROOT 致命 bug，10+ 用例直接 FileNotFoundError） |
| 测试自身安全性 | 🟡 有硬编码路径残留（os.popen 中 5 处 `/Users/zoo/`） |

**判定：REJECT** — 测试套件存在致命的路径计算 bug（`.parent` 层级错误），导致 10+ 用例无法正确执行。修复路径计算 + 排除自身文件后，预计可通过率提升至 ~70%（剩余为 develop_code 未执行的预期失败）。

**修复工作量**：约 15 分钟（改 3 处代码 + 运行验证）。
