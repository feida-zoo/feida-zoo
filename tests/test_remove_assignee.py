#!/usr/bin/env python3
"""
pl_e5484dc9 — 移除「指派成员」字段测试用例

覆盖设计文档全部 12 项改动:
- daemon 核心: _phase_assignee 删除、路由纯自动、stuck 检测
- dashboard API: 创建/返回不携带 assignee
- UI: HTML/JS/CSS 元素已删除
- 不受影响: pending_queue 的 assignee 保留、历史数据保留
- app_v2.py assignee 返回
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAEMON_PATH = os.path.join(REPO_ROOT, "framework", "core", "mesh", "zoo_mesh_daemon.py")
APP_PATH = os.path.join(REPO_ROOT, "dashboard", "app_enhanced.py")
APP_V2_PATH = os.path.join(REPO_ROOT, "dashboard", "app_v2.py")
HTML_PATH = os.path.join(REPO_ROOT, "dashboard", "templates", "dev_center.html")
JS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.js")
CSS_PATH = os.path.join(REPO_ROOT, "dashboard", "static", "dev_center.css")
TEST_PUSH_PATH = os.path.join(REPO_ROOT, "dashboard", "test_p0_pipeline_push.py")
TEST_SORT_PATH = os.path.join(REPO_ROOT, "dashboard", "test_priority_sort.py")


def _read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ============================================================
# TC-001 ~ TC-002: 核心路由 — _phase_assignee 已删除
# ============================================================

class TestPhaseAssigneeRemoved:
    """TC-001: _phase_assignee 函数已被删除"""

    def test_phase_assignee_function_gone(self):
        content = _read_file(DAEMON_PATH)
        matches = re.findall(r'^def _phase_assignee\b', content, re.MULTILINE)
        assert len(matches) == 0, f"_phase_assignee 函数定义仍存在 ({len(matches)} 处)"

    def test_phase_assignee_not_called(self):
        content = _read_file(DAEMON_PATH)
        # 只搜索函数调用（排除注释和pending_queue中的字段引用）
        calls = []
        for m in re.finditer(r'_phase_assignee\(', content):
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:content.find('\n', m.start())]
            # pending_queue 是数据结构，含 assignee 字段但不调用该函数
            if not line.strip().startswith('#'):
                calls.append(line)
        assert len(calls) == 0, f"_phase_assignee 仍被调用: {calls}"


# ============================================================
# TC-002: 路由改为纯 _pick_phase_agent
# ============================================================

class TestRoutingPureAuto:
    """TC-002: 路由兜底和 stuck 检测移除 assignee 依赖"""

    def test_routing_no_assignee_fallback(self):
        content = _read_file(DAEMON_PATH)
        for i, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue
            # 路由位置的 cur_req.get("assignee") — 要求被替换掉
            if 'cur_req.get("assignee")' in stripped:
                pytest.fail(f"L{i}: cur_req.get('assignee') 仍作为路由兜底存在")

    def test_stuck_assignee_fallback_removed(self):
        """_check_stuck_pipelines 函数中
        assignee = phase_agent or req.get("assignee", "")
        → 应改为 assignee = phase_agent or "panda" """
        content = _read_file(DAEMON_PATH)
        # 定位 stuck 函数
        fn_start = content.find('def _check_stuck_pipelines')
        assert fn_start >= 0, "未找到 _check_stuck_pipelines 函数"
        fn_end = content.find('\ndef ', fn_start + 1)
        stuck_fn = content[fn_start:fn_end] if fn_end > 0 else content[fn_start:]
        # 寻找 assignee = phase_agent or req.get("assignee", "")
        if 'req.get("assignee"' in stuck_fn:
            pytest.fail("_check_stuck_pipelines 中仍存在 req.get('assignee') 兜底")


class TestRouteNoPayloadAssignee:
    """TC-002(续): 创建 pipeline 不从 payload 读 assignee"""

    def test_no_payload_assignee(self):
        content = _read_file(DAEMON_PATH)
        assert 'payload.get("assignee")' not in content, \
            "payload.get('assignee') 仍存在于 daemon 中"

    def test_no_assignee_routing_variable(self):
        """变量名改为 phase_assignee/next_agent，避免 named assignee 参与路由"""
        content = _read_file(DAEMON_PATH)
        for i, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue
            # L602 附近：assignee = ... 赋值（创建 pipeline 时）
            # 应改为 phase_assignee = ... 或其他变量名
            if re.match(r'assignee\s*=', stripped) and \
               '_pick_phase_agent' in stripped and \
               '_enqueue_pending' not in stripped:
                pytest.fail(f"L{i}: 变量名仍为 assignee（语义不明）: {stripped}")

    def test_no_write_assignee_to_cur_req(self):
        """cur_req['assignee'] = 的写入应不存在（pending 上下文也不会用 cur_req）"""
        content = _read_file(DAEMON_PATH)
        for m in re.finditer(r'cur_req\[\s*["\']assignee["\']\s*\]\s*=', content):
            line_start = content.rfind('\n', 0, m.start()) + 1
            line = content[line_start:content.find('\n', m.start())]
            assert False, f"cur_req['assignee'] 写入仍存在: {line.strip()}"

    def test_new_req_dict_no_assignee(self):
        """新建 requirement 的 dict 不应含 assignee（排除 pending_queue 中的合法使用）"""
        content = _read_file(DAEMON_PATH)
        # 按行检查，排除 _enqueue_pending 所在的函数
        in_pending_func = False
        for i, line in enumerate(content.split('\n')):
            if 'def _enqueue_pending' in line:
                in_pending_func = True
            elif line.strip().startswith('def ') and not line.strip().startswith('def _enqueue_pending'):
                in_pending_func = False
            if in_pending_func:
                continue
            if '"assignee": assignee' in line or "'assignee': assignee" in line:
                pytest.fail(f"L{i+1}: 新建 req dict 中仍含 assignee: {line.strip()}")


# ============================================================
# TC-003: Dashboard API
# ============================================================

class TestDashboardAPINoAssignee:
    """TC-003: Dashboard API 不再接收/返回 assignee"""

    def _extract_handle_fn(self, fn_name):
        """按顶层函数名提取函数体（如 _handle_requirements_post）"""
        content = _read_file(APP_PATH)
        pos = content.find(f'def {fn_name}(')
        if pos < 0:
            return None
        block_start = content[:pos].rfind('\n') + 1
        block_end = content.find('\ndef ', block_start + 1)
        if block_end < 0:
            block_end = len(content)
        return content[block_start:block_end]

    def test_handle_requirements_post_no_assignee(self):
        """_handle_requirements_post 函数不含 assignee 处理"""
        handler_code = self._extract_handle_fn('_handle_requirements_post')
        if handler_code is None:
            pytest.skip('_handle_requirements_post 不存在')
        assert 'assignee' not in handler_code, \
            f"_handle_requirements_post 中仍含 assignee"

    def test_handle_issues_post_no_assignee(self):
        """_handle_issues_post 函数不含 assignee 处理"""
        handler_code = self._extract_handle_fn('_handle_issues_post')
        if handler_code is None:
            pytest.skip('_handle_issues_post 不存在')
        assert 'assignee' not in handler_code, \
            f"_handle_issues_post 中仍含 assignee"

    def test_kanban_response_no_assignee(self):
        """看板 API 响应不应含 assignee 字段（issue 列表可以保留历史值）"""
        content = _read_file(APP_PATH)
        # 看板数据在处理 kanban 请求的函数中
        # 搜索 "assignee" 出现在 json 响应构造中的位置
        for i, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            if stripped.startswith('#') or not stripped:
                continue
            # 响应 dict 中的 "assignee": task.get("assignee", "")
            # 只检查非 issue handler 的区域
            if '"assignee"' in stripped and 'task.get' in stripped:
                # 检查是否在 issue handler 中
                context_start = max(0, content[:content.find(stripped, max(0,i*30-500))].rfind('\ndef ', 0))
                context = content[context_start:context_start+500]
                if 'issue' not in context.lower():
                    pytest.fail(f"L{i}: 看板 API 响应仍含 assignee: {stripped}")


# ============================================================
# TC-004 ~ TC-006: UI 元素
# ============================================================

class TestHTMLAssigneeRemoved:
    """TC-004: HTML 中 assignee 下拉框已删除"""

    IDS = ['req-assignee', 'issue-assignee', 'request-assignee-select']

    def test_assignee_selects_gone(self):
        content = _read_file(HTML_PATH)
        for sel in self.IDS:
            assert sel not in content, f"HTML 中仍存在: {sel}"

    def test_assignee_label_gone(self):
        content = _read_file(HTML_PATH)
        assert '指派给' not in content, "HTML 中仍存在'指派给'标签"


class TestJSAssigneeRemoved:
    """TC-005: JS 中 assignee 逻辑已删除"""

    SELECT_IDS = ['req-assignee', 'issue-assignee', 'request-assignee-select']

    def test_assignee_select_refs_gone(self):
        content = _read_file(JS_PATH)
        for sel_id in self.SELECT_IDS:
            patterns = [
                f"getElementById('{sel_id}')",
                f'getElementById("{sel_id}")',
                f"querySelector('#{sel_id}')",
                f'querySelector("#{sel_id}")',
            ]
            for p in patterns:
                assert p not in content, f"JS 中仍引用: {p}"

    def test_kanban_assignee_display_gone(self):
        content = _read_file(JS_PATH)
        patterns = [
            'task-assignee',
            'assigneeEmoji',
            'assignee-avatar',
        ]
        for p in patterns:
            # 赋值操作（= 左边含该名）可保留
            lines = [l for l in content.split('\n') if p in l and '=' not in l.split(p)[0][-20:]]
            for line in lines:
                pytest.fail(f"JS 看板中仍显示 assignee: {line.strip()[:80]}")

    def test_issue_list_assignee_gone(self):
        content = _read_file(JS_PATH)
        assert 'issue-assignee' not in content, "问题列表 assignee 显示仍存在"

    def test_detail_assignee_display_gone(self):
        """任务详情弹窗中的 assignee 行"""
        content = _read_file(JS_PATH)
        detail_lines = [l for l in content.split('\n') if 'detail-value' in l and 'assignee' in l]
        assert len(detail_lines) == 0, f"任务详情仍显示 assignee: {detail_lines[:2]}"


class TestCSSAssigneeRemoved:
    """TC-006: CSS 中 assignee 样式已删除"""

    CLASSES = [
        '.task-assignee',
        '.assignee-avatar',
        '.assignee-avatar-img',
        '.issue-assignee',
    ]

    def test_css_classes_gone(self):
        content = _read_file(CSS_PATH)
        for cls in self.CLASSES:
            assert cls not in content, f"CSS 中仍存在: {cls}"


# ============================================================
# TC-007: SSE 通知
# ============================================================

class TestSSENotificationNoAssignee:
    """TC-007: SSE 通知不应发送 assignee"""

    def test_sse_notify_no_assignee(self):
        content = _read_file(APP_PATH)
        # 搜索创建需求后 SSE 通知中的 assignee 处理
        for i, line in enumerate(content.split('\n'), 1):
            if 'assignee' in line and ('notify' in line.lower() or 'notif' in line.lower()):
                pytest.fail(f"L{i}: SSE 通知仍含 assignee: {line.strip()}")


# ============================================================
# TC-008: 测试文件清理
# ============================================================

class TestTestFilesNoAssignee:
    """TC-008: 测试文件 assignee 参数已移除"""

    def test_pipeline_push_no_assignee_param(self):
        content = _read_file(TEST_PUSH_PATH)
        for m in re.finditer(r'def post_issue\(.*?\)', content):
            if 'assignee' in m.group():
                pytest.fail(f"test_p0_pipeline_push 中 post_issue 仍含 assignee 参数")

    def test_priority_sort_no_hardcoded_assignee(self):
        """优先排除 pending_queue 上下文中的 assignee"""
        content = _read_file(TEST_SORT_PATH)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if 'assignee' not in stripped:
                continue
            context = '\n'.join(lines[max(0,i-3):i+3])
            if 'pending' in context.lower():
                continue
            pytest.fail(f"test_priority_sort L{i}: assignee 未清理: {stripped[:80]}")


# ============================================================
# TC-009: pending_queue 的 assignee 保留
# ============================================================

class TestPendingQueueAssigneeKept:
    """TC-009: pending_queue 的 assignee 字段应保留（阶段执行者）"""

    def test_pending_queue_assignee_field_kept(self):
        content = _read_file(DAEMON_PATH)
        pending_section = content[content.find('_pending_queue'):]
        pending_section = pending_section[:800]
        assert 'assignee' in pending_section, \
            "pending_queue 中 assignee 字段不应被删除"


# ============================================================
# TC-010: app_v2.py assignee 返回
# ============================================================

class TestAppV2AssigneeResponse:
    """TC-010: app_v2.py 不应返回 assignee（如果有该函数）"""

    def test_app_v2_response_no_assignee(self):
        if not os.path.exists(APP_V2_PATH):
            pytest.skip("app_v2.py 不存在")
        content = _read_file(APP_V2_PATH)
        # 搜索响应 dict 中的 assignee 字段
        for i, line in enumerate(content.split('\n'), 1):
            if re.search(r'["\']assignee["\']\s*:', line):
                pytest.fail(f"app_v2.py L{i}: 响应中仍含 assignee")
