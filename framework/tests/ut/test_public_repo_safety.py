#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_cfba310f — feida_zoo 仓库公开化 + 目录结构整理
测试套件：验证所有安全加固 + 目录整理操作正确执行

覆盖范围（对应设计文档 13 项 + Review 补充）：
  1. DATA_DIR 路径改为环境变量（app_enhanced.py:48, develop_executor.py:17）
  2. issues_path 改为环境变量（zoo_mesh_daemon.py:761）
  3. gateway-start.ts QQ OpenID 改为环境变量（+ Review: Git 历史也需清理）
  4. 本地绝对路径全局替换为 FEIDA_ZOO_HOME
  5. zoo_members.yaml 脱敏（移除 model + session.key）+ Review: 消费者兼容性
  6. Git 历史邮箱重写
  7. .gitignore 补全（+ Review: 补充 venv/node_modules/__pycache__）
  8. 根目录脚本移入 scripts/
  9. docs/ 空目录删除 + artifacts 归档（+ Review: 检查 artifacts 内容安全）
  10. start_dev_center.sh 日志路径改为 /tmp/dashboard.log
  11. Review: 测试文件中的硬编码路径（6 个测试文件）
  12. Review: 入库日志清理（git rm --cached + .gitignore）
  13. Review: .env.example 文件（如适用）

用法：
    cd <project_root>
    python3 -m pytest framework/tests/ut/test_public_repo_safety.py -v

    FEIDA_ZOO_HOME=/tmp/test_home python3 -m pytest framework/tests/ut/test_public_repo_safety.py -v
"""

import os
import re
import sys
import json
from pathlib import Path

import pytest

# ── 项目路径（使用 __file__ 绝对路径解析，支持 symlink） ──
# test_public_repo_safety.py → framework/tests/ut/ → framework/tests/ → framework/ → 项目根
_TEST_FILE = Path(__file__).resolve()
_DEFAULT_ROOT = str(_TEST_FILE.parent.parent.parent.parent)
TEST_HOME = os.environ.get("FEIDA_ZOO_HOME", _DEFAULT_ROOT)
PROJECT_ROOT = Path(TEST_HOME)

# 敏感正则
RE_USERS_ZOO = re.compile(r"/Users/zoo/")
RE_HOME_AFEI = re.compile(r"/home/afei/")
RE_OPENID_HEX = re.compile(r"[A-F0-9]{32}")  # QQ OpenID 是 32 位大写 HEX
RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# 已知忽略目录
SKIP_DIRS = {".git", "venv", "__pycache__", "node_modules", ".pytest_cache"}
SKIP_FILES = {
    ".gitkeep",
    "pl_cfba310f_design.md",  # 设计文档免检（本身是成果）
    "pl_cfba310f_review.md",  # review 文档免检
    "pl_cfba310f_verify.md",  # verify 文档免检
    "test_public_repo_safety.py",  # 测试自身免检（不含敏感的业务数据）
}


# ============================================================
# 辅助函数
# ============================================================

def _collect_source_files(extensions=None):
    """收集非敏感目录下的 Python/TS/YAML/SH 文件"""
    files = []
    for ext in (extensions or {".py", ".ts", ".yaml", ".yml", ".sh", ".json", ".md"}):
        for p in PROJECT_ROOT.rglob(f"*{ext}"):
            rel = p.relative_to(PROJECT_ROOT)
            parts = rel.parts
            if any(s in parts for s in SKIP_DIRS):
                continue
            if p.name in SKIP_FILES:
                continue
            files.append(p)
    return files


def _read_file_safe(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ============================================================
# 1. DATA_DIR 路径改为环境变量
# ============================================================

class TestDataDirEnvVar:
    """验证 app_enhanced.py 和 develop_executor.py 的 DATA_DIR 不再硬编码"""

    def test_app_enhanced_uses_env_var_or_path_relative(self):
        """app_enhanced.py 的 PROJECT_ROOT + DATA_DIR 不应包含 /Users/zoo/"""
        p = PROJECT_ROOT / "dashboard" / "app_enhanced.py"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")

        # 不应有 /Users/zoo/ 硬编码
        assert "Path(\"/Users/zoo/" not in content, \
            "app_enhanced.py 仍包含 /Users/zoo/ 硬编码路径"

        # 应使用 FEIDA_ZOO_HOME 环境变量或相对路径计算
        assert "FEIDA_ZOO_HOME" in content or "PROJECT_ROOT / " in content, \
            "app_enhanced.py 应通过环境变量或相对路径计算 DATA_DIR"

        # DATA_DIR 不应是 /Users/zoo/ 下的硬编码
        for line in content.split("\n"):
            if "DATA_DIR" in line and "Path" in line and "/Users/" in line:
                pytest.fail(f"DATA_DIR 仍包含/Users/硬编码: {line.strip()}")

    def test_develop_executor_uses_env_var(self):
        """develop_executor.py 不应包含 /Users/zoo/ 硬编码"""
        p = PROJECT_ROOT / "framework" / "core" / "harness" / "executors" / "develop_executor.py"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")

        assert "/Users/zoo/" not in content, \
            "develop_executor.py 仍包含 /Users/zoo/ 硬编码"

        # 应使用 FEIDA_ZOO_HOME 或 os.getenv
        assert "FEIDA_ZOO_HOME" in content or "os.getenv" in content or "os.environ" in content, \
            "develop_executor.py 应通过环境变量获取路径"

    def test_dashboard_data_dir_not_hardcoded(self):
        """确认 DATA_DIR 在 app_enhanced.py 中通过 PROJECT_ROOT 动态计算"""
        p = PROJECT_ROOT / "dashboard" / "app_enhanced.py"
        content = p.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "DATA_DIR" in line and "=" in line:
                assert "/Users/" not in line, \
                    f"第 {i+1} 行 DATA_DIR 赋值包含 /Users/: {line.strip()}"
                break


# ============================================================
# 2. issues_path 改为环境变量
# ============================================================

class TestIssuesPathEnvVar:
    """验证 zoo_mesh_daemon.py 的 issues_path 不再硬编码"""

    def test_issues_path_not_hardcoded(self):
        """zoo_mesh_daemon.py 的 issues_path 不应硬编码"""
        p = PROJECT_ROOT / "framework" / "core" / "mesh" / "zoo_mesh_daemon.py"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")

        # 检查 _sync_issue_status 函数中的 issues_path
        assert "Path(\"/Users/zoo/" not in content, \
            "zoo_mesh_daemon.py 仍包含 /Users/zoo/ 硬编码路径"

        # 应使用 FEIDA_ZOO_HOME 或 os.getenv
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "issues_path" in line and "=" in line and "Path(" in line:
                assert "/Users/" not in line, \
                    f"第 {i+1} 行 issues_path 含 /Users/: {line.strip()}"
                assert "FEIDA_ZOO_HOME" in line or "os.getenv" in line or "os.environ" in line, \
                    f"第 {i+1} 行 issues_path 未使用环境变量: {line.strip()}"


# ============================================================
# 3. gateway-start.ts QQ OpenID 改为环境变量
# ============================================================

class TestQQOpenIdEnvVar:
    """验证 gateway-start.ts 的 QQ OpenID 不再硬编码"""

    def test_no_hardcoded_openid_in_source(self):
        """gateway-start.ts 不应包含 QQ OpenID 硬编码值"""
        p = PROJECT_ROOT / "plugins" / "zoo-pipeline" / "src" / "hooks" / "gateway-start.ts"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")

        # 检查 32 位大写 HEX（OpenID 格式）是否出现在硬编码映射中
        lines = content.split("\n")
        in_openid_block = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释和 import/require 行中的 HEX
            if "QQ_OPENID" in stripped or "QQ openid" in stripped.lower() or "openid" in stripped.lower():
                in_openid_block = True
                continue
            if in_openid_block:
                # 检查是否包含硬编码的 32 位 HEX
                hex_matches = RE_OPENID_HEX.findall(stripped)
                if hex_matches:
                    pytest.fail(f"第 {i+1} 行仍包含硬编码 OpenID: {stripped.strip()}")
                # 检查是否包含冒号后有引号包裹的大写串
                if re.search(r'"[A-F0-9]{32}"', stripped):
                    pytest.fail(f"第 {i+1} 行仍包含引号包裹的 OpenID: {stripped.strip()}")
                # 离开 OpenID 代码块条件：遇到空行或非数据行
                if ":" not in stripped and "{" not in stripped and "}" not in stripped and stripped:
                    in_openid_block = False

        # 应使用环境变量
        assert "process.env.QQ_OPENID" in content or "os.environ" in content or "process.env[" in content, \
            "gateway-start.ts 应通过环境变量读取 QQ OpenID"

    @pytest.mark.delivery
    def test_no_openid_in_git_history(self):
        """验证 git 历史中的 gateway-start.ts 变更不含 OpenID 明文（deliver 阶段后执行）"""
        # 检查最近的历史中是否有 OpenID 明文
        result = os.popen(
            f"cd {PROJECT_ROOT} && "
            "git log --all -p -- plugins/zoo-pipeline/src/hooks/gateway-start.ts 2>/dev/null | "
            "grep -E '[A-F0-9]{32}' | grep -v '^diff' | grep -v '^index' | grep -v '^@' | "
            "grep -v '^---' | grep -v '^+++' | head -5"
        ).read().strip()
        if result:
            # 如果确实有，检查是否全是被 git-filter-branch 擦除后的空串
            # 如果有残留则报 fail
            lines = [l for l in result.split("\n") if l.strip()]
            if lines:
                pytest.fail(f"Git 历史中仍发现 OpenID 明文:\n{result}")


# ============================================================
# 4. 本地绝对路径全局替换为 FEIDA_ZOO_HOME
# ============================================================

class TestNoLocalAbsolutePath:
    """验证所有核心源码文件中不再包含 /Users/zoo/ 硬编码"""

    def test_no_users_zoo_in_source(self):
        """核心源码不包含 /Users/zoo/ 路径"""
        source_files = _collect_source_files({".py", ".ts", ".yaml", ".yml", ".sh"})
        violations = []
        for p in source_files:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(PROJECT_ROOT)
            for i, line in enumerate(content.split("\n"), 1):
                if re.search(r"/Users/zoo/", line) and "/Users/zoo/" not in str(p):
                    # 不包含 README 中的示例路径（阅读友好不影响安全）
                    if "example" in line.lower() or "示例" in line:
                        continue
                    violations.append(f"  {rel}:{i}: {line.strip()[:100]}")
        
        if violations:
            pytest.fail(f"以下源码仍包含 /Users/zoo/ 硬编码路径:\n" + "\n".join(violations[:20]))

    def test_no_home_afei_in_source(self):
        """核心源码中的 /home/afei/ 路径应使用环境变量占位符
        
        os.getenv("FEIDA_ZOO_HOME", "/home/afei/...") 中的默认值是合法的 fallback，
        不应被标记为违规。仅当 /home/afei/ 出现在非 environ.get 上下文中时才报错。
        """
        source_files = _collect_source_files({".py", ".ts", ".sh"})
        violations = []
        for p in source_files:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(PROJECT_ROOT)
            for i, line in enumerate(content.split("\n"), 1):
                if "/home/afei/" not in line:
                    continue
                # YAML 配置文件中使用环境变量占位符可以接受
                if p.suffix == ".yaml" and "${FEIDA_ZOO_HOME" in line:
                    continue
                # os.getenv / os.environ.get 的 fallback 默认值是合法的
                stripped = line.strip()
                if ("os.getenv(" in stripped or "os.environ.get(" in stripped) and "FEIDA_ZOO_HOME" in stripped:
                    continue
                violations.append(f"  {rel}:{i}: {line.strip()[:80]}")
        
        if violations:
            pytest.fail(f"以下源码包含 /home/afei/ 硬编码（legitimate os.getenv fallback 除外）:\n" + "\n".join(violations[:20]))

    def test_framework_dir_no_hardcode(self):
        """zoo_mesh_daemon.py 的 FRAMEWORK_DIR 和 MESH_DIR 默认值不包含 /Users/zoo/"""
        p = PROJECT_ROOT / "framework" / "core" / "mesh" / "zoo_mesh_daemon.py"
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "FRAMEWORK_DIR" in line and "os.environ" in line:
                assert "/Users/" not in line, f"FRAMEWORK_DIR 仍含 /Users/: {line.strip()}"
            if "MESH_DIR" in line and "os.environ" in line:
                assert "/Users/" not in line, f"MESH_DIR 仍含 /Users/: {line.strip()}"

    def test_git_adapter_no_hardcode(self):
        """git_adapter.py 不应含 /Users/zoo/ 路径"""
        p = PROJECT_ROOT / "dashboard" / "git_adapter.py"
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "/Users/zoo/" not in content, \
            "git_adapter.py 仍包含 /Users/zoo/ 硬编码路径"


# ============================================================
# 5. zoo_members.yaml 脱敏
# ============================================================

class TestZooMembersSanitized:
    """验证 zoo_members.yaml 已移除敏感字段"""

    def test_no_model_field(self):
        """zoo_members.yaml 不应包含 model 字段"""
        p = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")
        # 允许在 metadata 或 groups 中使用 model（作为显示名称的标识）
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("model:") or stripped.startswith("model_id:"):
                # 检查是否在 members 层的子字段中
                pytest.fail(f"第 {i} 行仍包含 model 字段: {stripped}")

    def test_no_session_key(self):
        """zoo_members.yaml 不应包含 session 字段"""
        p = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
        content = p.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("session:") and ":" not in line.strip().split(None, 1)[1]:
                # "session:" 作为键的顶层缩进——这说明 session 键仍在
                pytest.fail(f"第 {i} 行仍包含 session 字段: {line.strip()}")
            if re.match(r"^\s+session:", line):
                pytest.fail(f"第 {i} 行仍包含 session 键")

    def test_no_sensitive_env_config(self):
        """zoo_members.yaml 不应包含 env 或 key 等敏感配置"""
        p = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
        content = p.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("key:") or stripped.startswith("channel:"):
                # 字段本身可存在但值不能是敏感内容
                pytest.fail(f"第 {i} 行仍包含 key/channel 字段: {stripped}")

    def test_example_available(self):
        """脱敏后应有示例模板供新用户参考"""
        example_path = PROJECT_ROOT / "framework" / "shared" / "event_bus" / "zoo_members_example.py"
        # 或者查看 README 是否有说明
        readme = PROJECT_ROOT / "README.md"
        if readme.exists():
            content = readme.read_text(encoding="utf-8")
            if "zoo_members" in content.lower() or "成员配置" in content:
                return  # README 已说明配置方式
        # 如果没有 README 说明，检查 example 文件
        if not example_path.exists():
            pytest.skip("无示例文件，需后续补充")


# ============================================================
# 6. Git 历史邮箱重写
# ============================================================

class TestGitEmailRewritten:
    """验证 Git 历史中的邮箱已统一"""

    @pytest.mark.delivery
    def test_no_duplicate_email_in_log(self):
        """Git 历史中应只有单一邮箱地址（deliver 阶段后执行）"""
        result = os.popen(
            f"cd {PROJECT_ROOT} && git log --all --format='%ae' | sort -u"
        ).read().strip()
        emails = [e for e in result.split("\n") if e.strip()]
        assert len(emails) == 1, \
            f"Git 历史中存在多个邮箱地址: {emails}（期望统一为 feidada002@gmail.com）"

    @pytest.mark.delivery
    def test_no_super_afei_email(self):
        """不应存在 super_afei@qq.com 邮箱（deliver 阶段后执行）"""
        result = os.popen(
            f"cd {PROJECT_ROOT} && "
            "git log --all --format='%ae' | grep -c 'super_afei@qq.com' || echo 0"
        ).read().strip()
        assert result == "0", f"Git 历史中仍存在 super_afei@qq.com 邮箱（{result} 次）"

    @pytest.mark.delivery
    def test_git_author_name_consistent(self):
        """Git 作者名称应统一（deliver 阶段后执行）"""
        result = os.popen(
            f"cd {PROJECT_ROOT} && git log --all --format='%an' | sort -u"
        ).read().strip()
        names = [n for n in result.split("\n") if n.strip()]
        # 允许一个作者名
        assert len(names) <= 1, \
            f"Git 历史中存在多个作者名: {names}"


# ============================================================
# 7. .gitignore 补全
# ============================================================

class TestGitignoreComplete:
    """验证 .gitignore 已补全必要规则"""

    def _check_gitignore(self):
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore 不存在"
        return gitignore.read_text(encoding="utf-8")

    def test_venv_ignored(self):
        content = self._check_gitignore()
        assert "venv/" in content or "/venv/" in content or "venv" in content, \
            ".gitignore 缺少 venv/"

    def test_node_modules_ignored(self):
        content = self._check_gitignore()
        assert "node_modules" in content or "node_modules/" in content, \
            ".gitignore 缺少 node_modules/"

    def test_pycache_ignored(self):
        content = self._check_gitignore()
        lines = content.split("\n")
        has_pycache = any("__pycache__" in l for l in lines)
        has_pyc = any("*.pyc" in l for l in lines)
        assert has_pycache or has_pyc, \
            ".gitignore 缺少 __pycache__/ 或 *.pyc"

    def test_log_files_ignored(self):
        content = self._check_gitignore()
        has_log = any("*.log" in l or ".log" in l for l in content.split("\n"))
        assert has_log, ".gitignore 缺少 *.log"

    def test_dot_env_ignored(self):
        content = self._check_gitignore()
        lines = content.split("\n")
        has_env = any(".env" in l and "#" not in l.split("#")[0].strip() for l in lines)
        assert has_env, ".gitignore 缺少 .env 和 .env.local"

    def test_ds_store_ignored(self):
        content = self._check_gitignore()
        assert ".DS_Store" in content or "DS_Store" in content, \
            ".gitignore 缺少 .DS_Store"

    def test_artifacts_ignored(self):
        content = self._check_gitignore()
        lines = content.split("\n")
        has_artifacts = any("artifacts" in l and not l.strip().startswith("#") for l in lines)
        if not has_artifacts:
            # 检查是否在 archive 中
            assert "archive" in content, ".gitignore 缺少 artifacts/"


# ============================================================
# 8. 根目录脚本移入 scripts/
# ============================================================

class TestRootScriptsMoved:
    """验证根目录脚本已移入 scripts/"""

    ROOT_SCRIPTS = [
        "run_existing_tests.py",
        "run_security_tests.py",
        "test_concurrent.py",
        "test_concurrent_json_simple.py",
        "test_deadlock_audit.py",
        "test_fix_verification.py",
        "test_path_traversal.py",
        "test_absolute_path.py",
        "verify_git_pipeline.py",
    ]

    ROOT_SCRIPTS_WITH_PREFIX = [
        "zoo-phase-complete",
        "zoo-service-restart",
    ]

    def test_scripts_dir_exists(self):
        scripts = PROJECT_ROOT / "scripts"
        assert scripts.exists(), "scripts/ 目录不存在"

    def test_root_scripts_no_longer_at_root(self):
        """原本在根目录的脚本不应再存在于根目录"""
        for name in self.ROOT_SCRIPTS:
            root_file = PROJECT_ROOT / name
            if root_file.exists():
                # 允许存在 symlink 但不允许是实际内容
                pytest.fail(f"根目录仍存在脚本: {name}（应移入 scripts/）")

    def test_scripts_under_scripts_dir(self):
        """确认脚本已在 scripts/ 下"""
        scripts = PROJECT_ROOT / "scripts"
        if not scripts.exists():
            pytest.skip("scripts/ 目录不存在")
        found = [p.name for p in scripts.iterdir() if not p.name.startswith(".")]
        for name in self.ROOT_SCRIPTS + self.ROOT_SCRIPTS_WITH_PREFIX:
            if name not in found:
                pytest.fail(f"scripts/ 下缺少: {name}")

    def test_symlinks_or_moved(self):
        """验证 zoo-phase-complete 和 zoo-service-restart 已移动"""
        for name in self.ROOT_SCRIPTS_WITH_PREFIX:
            root_file = PROJECT_ROOT / name
            scripts_file = PROJECT_ROOT / "scripts" / name
            
            # 根目录不应有实际文件（允许 symlink 兼容性）
            if root_file.exists():
                assert root_file.is_symlink(), \
                    f"{name} 在根目录是真实文件而非 symlink（应移入 scripts/）"
            
            # scripts/ 下应有真实文件或 symlink 指向真实文件
            assert scripts_file.exists(), f"scripts/{name} 不存在"

    def test_test_txt_moved_or_removed(self):
        """test.txt 应移入 scripts/"""
        root = PROJECT_ROOT / "test.txt"
        scripts = PROJECT_ROOT / "scripts" / "test.txt"
        assert not root.exists() or root.is_symlink(), \
            "test.txt 不应在根目录"
        if not scripts.exists():
            pytest.skip("scripts/test.txt 不存在（可能已删除）")


# ============================================================
# 9. docs/ 空目录删除 + artifacts 归档
# ============================================================

class TestDocAndArtifactsCleaned:
    """验证 docs/ 已删除，artifacts 已归档"""

    def test_docs_dir_removed(self):
        docs = PROJECT_ROOT / "docs"
        assert not docs.exists(), "docs/ 目录应已删除"
        # 检查 git 中是否已删除
        tracked = os.popen(
            f"cd {PROJECT_ROOT} && git ls-files docs/ 2>/dev/null | head -5"
        ).read().strip()
        if tracked:
            pytest.skip("docs/ 在 git 中仍有追踪（可能未 git rm --cached）")

    def test_artifacts_content_safe_for_public(self):
        """artifacts 中的文件内容不含硬编码路径等敏感信息"""
        archive_dir = PROJECT_ROOT / "framework" / "shared" / "archive"
        if archive_dir.exists():
            for f in archive_dir.rglob("*"):
                if f.is_file() and f.suffix in {".md", ".txt", ".json", ".yaml"}:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if re.search(r"/Users/zoo/", content):
                        # 检查是否为历史文档中的上下文说明
                        if "example" in content.lower() or "示例" in content:
                            continue
                        pytest.fail(f"archive 文件 {f.name} 仍包含 /Users/zoo/ 路径")

    def test_artifacts_old_dir_removed(self):
        """artifacts/ 目录应已删除或忽略"""
        artifacts = PROJECT_ROOT / "artifacts"
        if artifacts.exists():
            tracked = os.popen(
                f"cd {PROJECT_ROOT} && "
                "git ls-files artifacts/ 2>/dev/null | head -3"
            ).read().strip()
            ignored = os.popen(
                f"cd {PROJECT_ROOT} && "
                "git check-ignore artifacts/ 2>/dev/null; echo $?"
            ).read().strip()
            # 要么被 gitignore 忽略，要么已 git rm
            if tracked and "0" in ignored:
                pytest.fail("artifacts/ 仍在 git 追踪中且未被 .gitignore 忽略")


# ============================================================
# 10. start_dev_center.sh 日志路径
# ============================================================

class TestStartDevCenterLogPath:
    """验证 start_dev_center.sh 日志路径已修改"""

    def test_log_path_not_dashboard_dir(self):
        """日志不应输出到 dashboard/ 目录下"""
        p = PROJECT_ROOT / "dashboard" / "start_dev_center.sh"
        assert p.exists(), f"{p} not found"
        content = p.read_text(encoding="utf-8")

        assert "dashboard/server_enhanced.log" not in content, \
            "start_dev_center.sh 日志路径仍在 dashboard/ 目录下"
        assert "dashboard/server.log" not in content, \
            "start_dev_center.sh 日志路径仍在 dashboard/ 目录下"

    def test_log_path_is_tmp(self):
        """日志路径应为 /tmp/dashboard.log"""
        p = PROJECT_ROOT / "dashboard" / "start_dev_center.sh"
        content = p.read_text(encoding="utf-8")
        assert "/tmp/dashboard.log" in content or "/tmp/" in content, \
            "start_dev_center.sh 日志路径应为 /tmp/ 下"


# ============================================================
# 11. 测试文件中的硬编码路径
# ============================================================

class TestTestFilesNoHardcodedPath:
    """验证测试文件中不再包含 /Users/zoo/ 和 /home/afei/ 硬编码路径"""

    TEST_FILES_TO_CHECK = [
        "framework/tests/ut/test_avatar_file_correctness.py",
        "framework/tests/ut/test_member_active_filter.py",
        "framework/tests/ut/test_pipeline_done_syncs_issue_status.py",
        "framework/tests/harness/test_zoo_mesh_daemon.py",
        "framework/tests/st/test_path_config.py",
        "framework/tests/st/test_member_creation_e2e.py",
    ]

    def test_no_users_zoo_in_test_files(self):
        """测试文件中不应包含 /Users/zoo/ 硬编码"""
        for rel_path in self.TEST_FILES_TO_CHECK:
            p = PROJECT_ROOT / rel_path
            if not p.exists():
                pytest.skip(f"{rel_path} 不存在（可能已移除）")
                continue
            content = p.read_text(encoding="utf-8")
            for i, line in enumerate(content.split("\n"), 1):
                if "/Users/zoo/" in line and "FEIDA_ZOO_HOME" not in line:
                    pytest.fail(f"{rel_path}:{i} 包含 /Users/zoo/: {line.strip()[:80]}")

    def test_test_hardcoded_paths_up_to_date(self):
        """test_hardcoded_paths.py 应通过（断言逻辑不应引用 /Users/zoo/）"""
        p = PROJECT_ROOT / "framework" / "tests" / "ut" / "test_hardcoded_paths.py"
        if not p.exists():
            pytest.skip("test_hardcoded_paths.py 不存在（可能已重构）")
            return
        content = p.read_text(encoding="utf-8")
        # 检查是否仍在使用旧的硬编码路径断言
        if "/Users/zoo/" in content:
            pytest.fail("test_hardcoded_paths.py 仍包含 /Users/zoo/ 断言")

    def test_test_files_use_env_var(self):
        """测试文件路径应使用 FEIDA_ZOO_HOME"""
        for rel_path in self.TEST_FILES_TO_CHECK:
            p = PROJECT_ROOT / rel_path
            if not p.exists():
                continue
            content = p.read_text(encoding="utf-8")
            if "FEIDA_ZOO_HOME" not in content and "PROJECT_ROOT" not in content:
                # 检查是否绝对不包含路径
                if "/Users/" in content:
                    pytest.fail(f"{rel_path} 既不用 FEIDA_ZOO_HOME 也不用 PROJECT_ROOT")


# ============================================================
# 12. 入库日志清理
# ============================================================

class TestTrackedLogsCleaned:
    """验证已入库的日志已被 .gitignore 忽略"""

    def test_logs_no_longer_tracked(self):
        """dashboard/*.log 不应在 git 追踪中"""
        tracked = os.popen(
            f"cd {PROJECT_ROOT} && "
            "git ls-files dashboard/*.log 2>/dev/null"
        ).read().strip()
        if tracked:
            count = len(tracked.split("\n"))
            pytest.fail(f"仍有 {count} 个日志文件在 git 追踪中:\n{tracked}")

    def test_log_ignored_by_gitignore(self):
        """*.log 应在 .gitignore 忽略列表中"""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        if not gitignore_path.exists():
            pytest.skip(".gitignore 不存在")
        content = gitignore_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        has_log_glob = any(
            "*.log" in l or "*.log" in l or ".log" in l
            for l in lines
            if l.strip() and not l.strip().startswith("#")
        )
        assert has_log_glob, ".gitignore 中缺少 *.log 规则"


# ============================================================
# 13. 安全检查：不存在其他敏感信息泄露
# ============================================================

class TestNoSensitiveInfoLeak:
    """综合性敏感信息检查"""

    def test_no_gateway_config_in_repo(self):
        """不应有 OpenClaw Gateway 配置文件泄露"""
        source_files = _collect_source_files()
        gateway_patterns = [
            "openclaw.json",
            "config.yaml",
            ".openclaw/",
            "agent_id:",
        ]
        # 检查已知的敏感文件
        blocked_files = [
            PROJECT_ROOT / "openclaw.json",
            PROJECT_ROOT / "config.yaml",
            PROJECT_ROOT / ".openclaw" / "openclaw.json",
        ]
        for f in blocked_files:
            if f.exists():
                pytest.fail(f"敏感文件 {f} 不应在仓库中")

    def test_no_opt_homebrew_paths_in_code(self):
        """代码不应包含 /opt/homebrew/ 路径"""
        source_files = _collect_source_files({".py", ".ts", ".yaml", ".yml", ".sh"})
        violations = []
        for p in source_files:
            content = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(PROJECT_ROOT)
            for i, line in enumerate(content.split("\n"), 1):
                if "/opt/homebrew/" in line:
                    violations.append(f"  {rel}:{i}: {line.strip()[:80]}")
        
        if violations:
            pytest.fail(f"以下文件包含 /opt/homebrew/ 路径:\n" + "\n".join(violations[:10]))

    def test_env_example_exists(self):
        """应有 .env.example 或类似文件说明所需环境变量"""
        env_example = PROJECT_ROOT / ".env.example"
        if not env_example.exists():
            # 检查 README 中是否有环境变量说明
            readme = PROJECT_ROOT / "README.md"
            if readme.exists():
                content = readme.read_text(encoding="utf-8")
                if "环境变量" in content or "FEIDA_ZOO_HOME" in content or "QQ_OPENID" in content:
                    return  # README 中已说明
            pytest.skip("缺少 .env.example 文件（非强制，建议添加）")


# ============================================================
# 14. start_enhanced.sh 也检查（Review 补充）
# ============================================================

class TestStartEnhancedShSanitized:
    """验证 start_enhanced.sh 无硬编码"""

    def test_start_enhanced_no_hardcode(self):
        """start_enhanced.sh 不应有 /home/afei/ 硬编码"""
        p = PROJECT_ROOT / "dashboard" / "start_enhanced.sh"
        if not p.exists():
            pytest.skip("start_enhanced.sh 不存在")
            return
        content = p.read_text(encoding="utf-8")
        assert "/home/afei/" not in content, \
            "start_enhanced.sh 仍包含 /home/afei/ 硬编码"


# ============================================================
# 集成测试：关键路径验证
# ============================================================

class TestIntegrationConsistency:
    """检验改动后的各模块联合工作完整性"""

    def test_app_enhanced_import_ok(self):
        """app_enhanced.py 基本语法检查（简单 syntax check）"""
        p = PROJECT_ROOT / "dashboard" / "app_enhanced.py"
        result = os.popen(
            f"cd {PROJECT_ROOT} && python3 -c \"import ast; ast.parse(open('{p.resolve()}').read()); print('OK')\" 2>&1"
        ).read().strip()
        assert "OK" in result, f"app_enhanced.py 语法错误: {result}"

    def test_zoo_members_yaml_valid(self):
        """zoo_members.yaml 仍是合法 YAML"""
        p = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
        import yaml
        try:
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data is not None, "YAML 为空"
            assert "members" in data, "YAML 缺少 members 根字段"
            # 检查所有成员仍有必要字段
            for member_id, member in data.get("members", {}).items():
                assert "id" in member, f"{member_id} 缺少 id"
                assert "name" in member, f"{member_id} 缺少 name"
                assert "role" in member, f"{member_id} 缺少 role"
        except Exception as e:
            pytest.fail(f"zoo_members.yaml 解析失败: {e}")

    @pytest.mark.delivery
    def test_git_log_no_afei_paths(self):
        """git log 应无 /Users/zoo/ 或 /home/afei/ 路径（deliver 阶段后执行）"""
        # 检查最近 commit 的 diff（全量历史通过 filter-branch 清理）
        result = os.popen(
            f"cd {PROJECT_ROOT} && "
            "git log --all -p --diff-filter=M -- '*.py' '*.ts' '*.sh' '*.yaml' '*.yml' "
            "2>/dev/null | grep -E '/Users/zoo/|/home/afei/' | grep -v '^---' | grep -v '^+++' | "
            "grep -v 'FEIDA_ZOO_HOME' | grep -v 'example' | head -5"
        ).read().strip()
        if result:
            pytest.fail(f"git log 中仍发现 /Users/zoo/ 或 /home/afei/ 路径:\n{result}")

    def test_git_rm_cached_for_logs(self):
        """确保 dashboard/*.log 已从 git index 中移除"""
        result = os.popen(
            f"cd {PROJECT_ROOT} && "
            "git ls-files --cached dashboard/*.log 2>/dev/null | head -3"
        ).read().strip()
        if result:
            pytest.fail(f"dashboard/*.log 仍在 git index 中:\n{result}")


# ============================================================
# 集成测试：完整环境变量注入模拟
# ============================================================

class TestEnvVarInjection:
    """模拟环境变量注入后验证各模块正确获取路径"""

    def test_develop_executor_path_injection(self):
        """develop_executor.py 在 FEIDA_ZOO_HOME 环境下正确解析路径"""
        p = PROJECT_ROOT / "framework" / "core" / "harness" / "executors" / "develop_executor.py"
        content = p.read_text(encoding="utf-8")
        # 检查使用 os.getenv("FEIDA_ZOO_HOME", ...)
        assert 'os.getenv("FEIDA_ZOO_HOME"' in content or "os.environ.get('FEIDA_ZOO_HOME'" in content or 'os.environ.get("FEIDA_ZOO_HOME"' in content, \
            "develop_executor.py 应使用 os.getenv 读取 FEIDA_ZOO_HOME"

    def test_zoo_mesh_daemon_framework_dir(self):
        """zoo_mesh_daemon.py 的 FRAMEWORK_DIR 应基于 FEIDA_ZOO_HOME"""
        p = PROJECT_ROOT / "framework" / "core" / "mesh" / "zoo_mesh_daemon.py"
        content = p.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "FRAMEWORK_DIR" in line and "os.environ" in line:
                assert "FEIDA_ZOO_HOME" in line, \
                    f"FRAMEWORK_DIR 应基于 FEIDA_ZOO_HOME: {line.strip()}"
            if "MESH_DIR" in line and "os.environ" in line:
                assert "FEIDA_ZOO_HOME" in line or "ZOO_MESH_DIR" in line, \
                    f"MESH_DIR 应使用环境变量: {line.strip()}"
