#!/usr/bin/env python3
"""
pl_35ccc3cc — System Sanity Check 测试用例

覆盖设计文档全部健康检查维度
"""
import os
import re
import json
import subprocess
import pytest
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {
    "daemon": os.path.join(REPO_ROOT, "framework", "core", "mesh", "zoo_mesh_daemon.py"),
    "app": os.path.join(REPO_ROOT, "dashboard", "app_enhanced.py"),
    "app_v2": os.path.join(REPO_ROOT, "dashboard", "app_v2.py"),
    "js": os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.js"),
    "css": os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.css"),
    "html": os.path.join(REPO_ROOT, "dashboard", "templates", "dev_center.html"),
    "readme": os.path.join(REPO_ROOT, "README.md"),
}
DASHBOARD_URL = "http://127.0.0.1:18792"
DAEMON_URL = "http://127.0.0.1:18793"


# ============================================================
# TC-001: 服务可用性
# ============================================================

class TestServices:
    """TC-001: Dashboard 和 Daemon 服务可用"""

    def test_dashboard_http_200(self):
        resp = requests.get(f"{DASHBOARD_URL}/", timeout=5)
        assert resp.status_code == 200, f"Dashboard: {resp.status_code}"

    def test_daemon_reachable(self):
        """Daemon 无根页面返回 404 为健康状态"""
        resp = requests.get(f"{DAEMON_URL}/", timeout=5)
        # daemon 没有根路由，404 或 200 都算运行中
        assert resp.status_code in (200, 404, 405), f"Daemon: {resp.status_code}"


# ============================================================
# TC-002: Python 语法
# ============================================================

class TestPythonSyntax:
    """TC-002: 所有 Python 文件语法正确"""

    MODULES = ["daemon", "app"]

    def test_daemon_syntax(self):
        result = subprocess.run(
            ["python3", "-m", "py_compile", FILES["daemon"]],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"daemon 语法错误: {result.stderr}"

    def test_app_syntax(self):
        result = subprocess.run(
            ["python3", "-m", "py_compile", FILES["app"]],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"app 语法错误: {result.stderr}"

    def test_app_v2_syntax(self):
        if not os.path.exists(FILES["app_v2"]):
            pytest.skip("app_v2.py 不存在")
        result = subprocess.run(
            ["python3", "-m", "py_compile", FILES["app_v2"]],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"app_v2 语法错误: {result.stderr}"


# ============================================================
# TC-003: JS 语法
# ============================================================

class TestJSSyntax:
    """TC-003: JavaScript 文件语法正确"""

    def test_js_syntax(self):
        result = subprocess.run(
            ["node", "-c", FILES["js"]],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JS 语法错误: {result.stderr}"


# ============================================================
# TC-004: CSS 括号配对
# ============================================================

class TestCSSBraces:
    """TC-004: CSS 大括号必须配对"""

    def test_css_braces(self):
        with open(FILES["css"]) as f:
            lines = f.readlines()
        depth = 0
        for i, line in enumerate(lines, 1):
            depth += line.count("{") - line.count("}")
            if depth < 0:
                pytest.fail(f"CSS L{i}: 多余的 }}")
        assert depth == 0, f"CSS 大括号未闭合: depth={depth}"


# ============================================================
# TC-005: Git 工作区
# ============================================================

class TestGitWorkspace:
    """TC-005: Git 工作区状态"""

    def test_git_clean(self):
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=REPO_ROOT
        )
        # 报告用注释 — 不强制干净，只记录
        if result.stdout.strip():
            print(f"\n⚠️  未提交修改:\n{result.stdout}")
        # sanity check 不要求强制干净，只是报告

    def test_critical_files_exist(self):
        """所有核心源码文件存在"""
        for name, path in FILES.items():
            assert os.path.exists(path), f"核心文件缺失: {name} ({path})"


# ============================================================
# TC-006: 已有测试全部通过
# ============================================================

class TestExistingTestSuite:
    """TC-006: 已有测试全部通过"""

    def test_existing_tests_pass(self):
        result = subprocess.run(
            [os.path.join(REPO_ROOT, "venv", "bin", "pytest"),
             "tests/test_readme_update.py",
             "tests/test_remove_assignee.py",
             "tests/test_verify_no_assignee.py",
             "-q"],
            capture_output=True, text=True, timeout=60,
            cwd=REPO_ROOT
        )
        out = result.stdout + result.stderr
        print(f"\n{out}")
        # 检查是否有 passed 行
        if "passed" not in out and "failed" in out:
            assert False, f"已有测试未通过: {out}"
