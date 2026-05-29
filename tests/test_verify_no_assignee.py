#!/usr/bin/env python3
"""
pl_b58d7c0e — Test no assignee: 端到端集成测试

覆盖设计文档全部 6 项验证:
1. 测试全部通过 (meta)
2. JS 语法正确 (import node -c from test_remove_assignee)
3. CSS 括号配对 (import from test_remove_assignee)
4. Dashboard 运行中
5. 创建需求 API 无 assignee
6. 创建问题 API 无 assignee
"""
import os
import json
import subprocess
import pytest
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_URL = "http://127.0.0.1:18792"
JS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.js")
CSS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.css")


class TestDashboardRunning:
    """TC-1: Dashboard 运行中"""

    def test_dashboard_http_200(self):
        resp = requests.get(f"{DASHBOARD_URL}/", timeout=5)
        assert resp.status_code == 200, f"Dashboard 状态码: {resp.status_code}"

    def test_kanban_api_available(self):
        resp = requests.get(f"{DASHBOARD_URL}/api/kanban", timeout=5)
        assert resp.status_code == 200, f"看板 API 状态码: {resp.status_code}"


class TestCreateRequirementNoAssignee:
    """TC-2: 创建需求无 assignee"""

    def test_create_requirement_response_no_assignee(self):
        resp = requests.post(
            f"{DASHBOARD_URL}/api/requirements",
            json={"title": "Verify no assignee", "description": "test", "priority": "P3"},
            timeout=5
        )
        assert resp.status_code == 200, f"创建需求状态码: {resp.status_code}"
        data = resp.json()
        assert "assignee" not in data, f"响应中仍含 assignee: {data['assignee']}"

    def test_create_requirement_accepts_no_assignee(self):
        """不传 assignee 字段不应报错"""
        resp = requests.post(
            f"{DASHBOARD_URL}/api/requirements",
            json={"title": "Verify no assignee field", "description": ""},
            timeout=5
        )
        assert resp.status_code == 200, f"无assignee字段请求失败: {resp.status_code}"


class TestCreateIssueNoAssignee:
    """TC-3: 创建问题无 assignee"""

    def test_create_issue_response_no_assignee(self):
        resp = requests.post(
            f"{DASHBOARD_URL}/api/issues",
            json={"title": "Verify no assignee issue", "description": "test", "priority": "P3"},
            timeout=5
        )
        assert resp.status_code == 200, f"创建问题状态码: {resp.status_code}"
        data = resp.json()
        assert "assignee" not in data, f"响应中仍含 assignee: {data['assignee']}"

    def test_create_issue_accepts_no_assignee(self):
        """不传 assignee 字段不应报错"""
        resp = requests.post(
            f"{DASHBOARD_URL}/api/issues",
            json={"title": "Verify no assignee field", "description": ""},
            timeout=5
        )
        assert resp.status_code == 200, f"无assignee字段请求失败: {resp.status_code}"


class TestJSSyntaxValid:
    """TC-4: JS 语法正确"""

    def test_js_syntax(self):
        result = subprocess.run(
            ["node", "-c", JS_PATH],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JS 语法错误: {result.stderr}"


class TestCSSBracesBalanced:
    """TC-5: CSS 括号配对"""

    def test_css_braces(self):
        with open(CSS_PATH) as f:
            lines = f.readlines()
        depth = 0
        for i, line in enumerate(lines, 1):
            depth += line.count("{") - line.count("}")
            if depth < 0:
                pytest.fail(f"CSS L{i}: 多余的 }}")
        assert depth == 0, f"CSS 大括号未闭合: depth={depth}"
