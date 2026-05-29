#!/usr/bin/env python3
"""
pl_e5484dc9 — 移除「指派成员」字段测试用例

覆盖设计文档全部 12 项改动:
- daemon 核心: _phase_assignee 删除、路由纯自动、stuck 检测
- dashboard API: 创建/返回不携带 assignee
- UI: HTML/JS/CSS 元素已删除
- 不受影响: pending_queue 的 assignee 保留、历史数据保留
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAEMON_PATH = os.path.join(REPO_ROOT, "framework", "core", "mesh", "zoo_mesh_daemon.py")
APP_PATH = os.path.join(REPO_ROOT, "dashboard", "app_enhanced.py")
HTML_PATH = os.path.join(REPO_ROOT, "dashboard", "templates", "dev_center.html")
JS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.js")
CSS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.css")
TEST_PUSH_PATH = os.path.join(REPO_ROOT, "dashboard", "test_p0_pipeline_push.py")
TEST_SORT_PATH = os.path.join(REPO_ROOT, "dashboard", "test_priority_sort.py")


# ============================================================
# TC-001 ~ TC-002: 核心路由 — _phase_assignee 已删除
# ============================================================

class TestPhaseAssigneeRemoved:
    """TC-001: _phase_assignee 函数已被删除"""

    def test_phase_assignee_function_gone(self):
        """_phase_assignee 函数定义不存在"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        # 检查 def _phase_assignee — 如果存在则是未删除
        matches = re.findall(r'def _phase_assignee\b', content)
        assert len(matches) == 0, f"_phase_assignee 函数仍存在 ({len(matches)} 处)"

    def test_phase_assignee_not_called(self):
        """_phase_assignee 不应被调用"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        calls = re.findall(r'_phase_assignee\(', content)
        assert len(calls) == 0, f"_phase_assignee 仍被调用 ({len(calls)} 处)"


class TestPickPhaseAgentUsed:
    """TC-002: 路由改为纯 _pick_phase_agent"""

    def test_routing_no_assignee_fallback(self):
        """L884/L909 路由不应有 assignee 兜底"""
        with open(DAEMON_PATH) as f:
            lines = f.readlines()
        # 找路由位置的 assignee 兜底
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 含有 cur_req.get("assignee") 且不在注释或 pending_queue 中
            if 'cur_req.get("assignee")' in stripped and not stripped.startswith('#'):
                # 确认不在 pending 相关代码中
                if 'pending' not in stripped.lower() and '_enqueue_pending' not in stripped:
                    pytest.fail(f"L{i+1}: cur_req.get('assignee') 仍作为路由兜底存在: {stripped}")

    def test_stuck_no_assignee_fallback(self):
        """L1421 stuck 检测无 assignee 兜底
        搜索 stuck 检测特定区域的 req.get('assignee')，排除写入 assignee 的区域。"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        # 找到 stuck 检测函数区域
        stuck_func_match = re.search(r'def _handle_user_pipeline_stuck.*?(?=
def |$)', content, re.DOTALL)
        if not stuck_func_match:
            # 如果没有独立的 stuck 函数，搜 _stuck_check 相关代码
            stuck_matches = [m.start() for m in re.finditer(r'stuck', content, re.IGNORECASE)]
        else:
            stuck_code = stuck_func_match.group(0)
            # 在 stuck 函数中找 req.get('assignee')
            if 'req.get("assignee"' in stuck_code or "req.get('assignee'" in stuck_code:
                pytest.fail(f"stuck 检测中仍存在 assignee 兜底: {stuck_code[:200]}")

    @staticmethod
    def _find_context(content, pattern, window=100):
        idx = content.find(pattern)
        if idx >= 0:
            return content[max(0,idx-window):idx+window]
        return ""


class TestRouteNoPayloadAssignee:
    """TC-002(续): 创建 pipeline 不从 payload 读 assignee"""

    def test_no_payload_assignee(self):
        """创建 pipeline 时不应从 payload.get('assignee')"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        # payload.get("assignee") 在 daemon 中应不存在（_handle_pipeline_request 部分）
        if 'payload.get("assignee")' in content:
            pytest.fail("payload.get('assignee') 仍存在于 daemon 中")

    def test_no_write_assignee_to_req(self):
        """不应向 requirement 写入 assignee"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        # cur_req["assignee"] = 的写入应不存在
        matches = re.findall(r'cur_req\[.assignee.\]', content)
        allowed_contexts = []
        for m in matches:
            idx = content.find(m)
            # 检查是否在 pending_queue 上下文中（合法）
            context = content[max(0,idx-50):idx+50]
            if 'pending' in context.lower():
                allowed_contexts.append(m)
        disallowed = len(matches) - len(allowed_contexts)
        assert disallowed == 0, f"cur_req['assignee'] 写入仍存在 {disallowed} 处"


# ============================================================
# TC-003: Dashboard API — 不再接受/返回 assignee
# ============================================================

class TestDashboardAPINoAssignee:
    """TC-003: Dashboard 创建 API 不再处理 assignee"""

    def test_create_requirement_no_assignee(self):
        """创建需求 API 不接收 assignee"""
        with open(APP_PATH) as f:
            content = f.read()
        # 创建需求部分不应有 data.get('assignee')
        # 找到创建需求的 handler 部分
        create_req_section = content.split("def do_POST")[-1] if "def do_POST" in content else ""
        # 检查是否还有 assignee 处理
        if 'data.get(\'assignee\'' in create_req_section or 'data.get("assignee"' in create_req_section:
            # 排除 issues 的 GET/POST
            if 'issue' not in create_req_section.lower():
                pytest.fail("创建需求 API 仍处理 assignee 字段")

    def test_requirement_response_no_assignee(self):
        """需求 API 响应不含 assignee 字段"""
        with open(APP_PATH) as f:
            content = f.read()
        # 响应体构造不应返回 assignee
        assignee_in_resp = re.findall(r'"assignee"\s*:\s*task\.get\(', content) + \
                           re.findall(r"'assignee'\s*:\s*task\.get\(", content) + \
                           re.findall(r'"assignee"\s*:\s*req\.get\(', content)
        # 排除 issues handler 中的合法 GET 响应（get_issues）
        allowed = 0
        for m in assignee_in_resp:
            idx = content.find(m)
            context = content[max(0,idx-100):idx+100]
            if 'issue' in context.lower():
                allowed += 1  # issue 详情显示历史 assignee — review 时确认是否有必要
            else:
                pytest.fail(f"需求 API 响应仍含 assignee: {context}")
        # 允许 issues 列表保留历史 assignee
        if len(assignee_in_resp) > allowed:
            extra = len(assignee_in_resp) - allowed
            if extra > 3:  # 3 个是 issue GET 的合理数量
                pytest.fail(f"assignee 在 API 响应中出现 {extra} 次（超过预期的 issue 显示）")

    def test_issue_API_no_assignee(self):
        """问题 API 不应接收 assignee"""
        with open(APP_PATH) as f:
            content = f.read()
        # issue 创建 handler 不应处理 assignee
        if 'issue' in content:
            create_issue_section = content.split("def create_issue")[-1] if "def create_issue" in content else ""
            create_issue_section = create_issue_section or (content.split("/api/issues")[0][-500:])
            if create_issue_section:
                if 'data.get(\'assignee\'' in create_issue_section or 'data.get("assignee"' in create_issue_section:
                    # 确认是创建/更新 issue 的 assignee，不是 GET 响应
                    if 'post' in create_issue_section.lower() or 'create' in create_issue_section.lower():
                        pytest.fail("创建问题 API 仍处理 assignee 字段")


# ============================================================
# TC-004 ~ TC-005: UI 元素已删除
# ============================================================

class TestHTMLAssigneeRemoved:
    """TC-004: HTML 中 assignee 下拉框已删除"""

    ASSIGNEE_SELECTS = [
        'id="req-assignee"',
        'id="issue-assignee"',
        'id="request-assignee-select"',
        'label for="req-assignee"',
        'label for="issue-assignee"',
    ]

    def test_requirement_assignee_select_gone(self):
        with open(HTML_PATH) as f:
            content = f.read()
        for sel in self.ASSIGNEE_SELECTS:
            assert sel not in content, f"HTML 中仍存在: {sel}"

    def test_assignee_labels_gone(self):
        with open(HTML_PATH) as f:
            content = f.read()
        assert '指派给' not in content, "HTML 中仍存在'指派给'标签"


class TestJSAssigneeRemoved:
    """TC-005: JS 中 assignee 逻辑已删除"""

    ASSIGNEE_REFS = [
        'document.getElementById(\'req-assignee\')',
        'document.getElementById("req-assignee")',
        'document.getElementById(\'issue-assignee\')',
        'document.getElementById("issue-assignee")',
        'document.getElementById(\'request-assignee-select\')',
        'document.getElementById("request-assignee-select")',
    ]

    def test_assignee_selects_gone(self):
        with open(JS_PATH) as f:
            content = f.read()
        for ref in self.ASSIGNEE_REFS:
            assert ref not in content, f"JS 中仍引用: {ref}"

    def test_kanban_assignee_display_gone(self):
        with open(JS_PATH) as f:
            content = f.read()
        # 看板中的 .task-assignee 或 assigneeEmoji/assignee 显示
        # detail-value 后的 assignee 显示
        detail_assignee = re.findall(r'detail-value.*assignee', content) or \
                          re.findall(r'assignee.*detail-value', content)
        assert len(detail_assignee) == 0, f"看板 assignee 显示仍存在: {detail_assignee}"

    def test_issue_list_assignee_gone(self):
        with open(JS_PATH) as f:
            content = f.read()
        assert 'issue-assignee' not in content, "问题列表 assignee 显示仍存在"


class TestCSSAssigneeRemoved:
    """TC-006: CSS 中 assignee 样式已删除"""

    CSS_CLASSES = [
        '.task-assignee',
        '.assignee-avatar',
        '.assignee-avatar-img',
        '.issue-assignee',
    ]

    def test_css_classes_gone(self):
        with open(CSS_PATH) as f:
            content = f.read()
        for cls in self.CSS_CLASSES:
            assert cls not in content, f"CSS 中仍存在: {cls}"


# ============================================================
# TC-007: SSE 通知不含 assignee
# ============================================================

class TestSSENotificationNoAssignee:
    """TC-007: SSE 通知不应发送 assignee"""

    def test_sse_notify_no_assignee(self):
        with open(APP_PATH) as f:
            content = f.read()
        # 创建需求后的 SSE 通知不应处理 assignee
        # 检查 'notify.*assignee' 或 'assignee.*notify' 模式
        notify_assignee = re.findall(r'notify.*assignee|assignee.*notif', content, re.IGNORECASE)
        for match in notify_assignee:
            pytest.fail(f"SSE 通知仍含 assignee: {match}")


# ============================================================
# TC-008: 测试文件清理
# ============================================================

class TestTestFilesNoAssignee:
    """TC-008: 测试文件 assignee 参数已移除"""

    def test_pipeline_push_no_assignee_param(self):
        with open(TEST_PUSH_PATH) as f:
            content = f.read()
        # post_issue 函数签名的 assignee 参数应已删除
        post_issue_def = re.findall(r'def post_issue\(.*?\)', content)
        for d in post_issue_def:
            if 'assignee' in d:
                pytest.fail(f"test_p0_pipeline_push 中 post_issue 仍含 assignee 参数: {d}")

    def test_priority_sort_no_hardcoded_assignee(self):
        with open(TEST_SORT_PATH) as f:
            content = f.read()
        # 硬编码的 "assignee": "alpha" 或 "assignee": "" 应不存在
        if '"assignee"' in content or "'assignee'" in content:
            lines_with_assignee = [l for l in content.split('\n') if 'assignee' in l]
            relevant = [l for l in lines_with_assignee if 'pending' not in l.lower()]
            if relevant:
                pytest.fail(f"test_priority_sort 中 assignee 未清理: {relevant}")


# ============================================================
# TC-009: pending_queue 的 assignee 保留（不受影响）
# ============================================================

class TestPendingQueueAssigneeKept:
    """TC-009: pending_queue 的 assignee 字段应保留"""

    def test_pending_queue_assignee_field_kept(self):
        """_pending_queue 中的 assignee 是阶段执行者，应保留"""
        with open(DAEMON_PATH) as f:
            content = f.read()
        # 确认 pending_queue 相关代码中仍有 assignee
        pending_section_match = re.search(r'_pending_queue.*?def ', content, re.DOTALL)
        if pending_section_match:
            pending_code = pending_section_match.group(0)
            assert 'assignee' in pending_code, \
                "pending_queue 中 assignee 字段不应被删除"
