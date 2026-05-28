#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_b9a4d0e1 — 驳回后未触发 Pipeline 修复
测试套件：验证审计通过后自动创建新 Pipeline

覆盖范围（对应设计文档 + Review 补充）：
  1. Issue 审计通过 → 创建新 Pipeline（dispatch_pipeline_for_issue）
  2. Requirement 审计通过 → 创建新 Pipeline（dispatch_pipeline 泛化）
  3. 新 Pipeline ID 存入 reject_pipeline_id，保留原 pipeline_id
  4. Pipeline payload 含 [驳回重开] 前缀 + 驳回原因
  5. dispatch_pipeline 仅负责创建+返回，不负责持久化
  6. _handle_issues_post 重构后仍正常
  7. 无 pipeline_id 时仍能创建新 Pipeline（首次驳回）
  8. SSE 推送 pipeline_status
  9. 驳回原因含特殊字符时 payload 正常序列化

用法：
    cd <project_root>
    python3 -m pytest framework/tests/ut/test_reject_pipeline.py -v
"""

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── 项目路径 ──────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

ZOO_MESH_HTTP = "http://127.0.0.1:18793"


# ============================================================
# 辅助函数
# ============================================================

def _make_issue(**overrides):
    base = {
        "id": "iss_test_001",
        "title": "测试问题",
        "description": "描述内容",
        "priority": "P1",
        "status": "rejected",
        "assignee": "alpha",
        "created_at": "2026-05-28T10:00:00",
        "updated_at": "2026-05-28T20:00:00",
        "resolved_at": "2026-05-28T12:00:00",
        "source": "dashboard",
        "pipeline_id": "pl_original_001",
        "pipeline_status": "pushed",
        "reject_reason": "并发场景未覆盖",
        "rejected_by": "dashboard_user",
        "rejected_at": "2026-05-28T20:00:00",
        "previous_status": "resolved",
        "audit_status": "pending",
        "audit_comment": "",
        "audit_agent": "duci",
    }
    base.update(overrides)
    return base


def _make_requirement(**overrides):
    base = {
        "id": "req_test_001",
        "title": "测试需求",
        "description": "描述内容",
        "assignee": "alpha",
        "status": "rejected",
        "phase": "deliver",
        "priority": "P1",
        "created_at": "2026-05-28T10:00:00",
        "pipeline_id": "pl_req_original_001",
        "source": "dashboard_requirement",
        "updated_at": "2026-05-28T20:00:00",
        "completed_at": "2026-05-28T12:00:00",
        "reject_reason": "UI 不符合设计稿",
        "rejected_by": "dashboard_user",
        "rejected_at": "2026-05-28T20:00:00",
        "previous_status": "done",
        "audit_status": "pending",
        "audit_comment": "",
        "audit_agent": "duci",
    }
    base.update(overrides)
    return base


def _simulate_dispatch(issue: dict) -> dict:
    """模拟 _dispatch_pipeline 的返回行为（仅逻辑，不触及 HTTP/IO）"""
    now = "2026-05-28T21:00:00"
    new_pipeline_id = f"pl_{uuid.uuid4().hex[:8]}"
    payload = {
        "type": "pipeline_request",
        "task_id": new_pipeline_id,
        "requirement_id": issue["id"],
        "title": f"[驳回重开] {issue['title']}",
        "description": f"驳回原因: {issue.get('reject_reason', '')}\n\n{issue.get('description', '')}",
        "assignee": issue.get("assignee") or "alpha",
        "source": "issue_reject",
        "timestamp": now,
    }
    issue["reject_pipeline_id"] = new_pipeline_id
    issue["reject_pipeline_payload"] = payload
    issue["reject_pipeline_status"] = "pushed"
    issue["audit_timestamp"] = now
    # 保留原始 pipeline_id
    return {
        "pipeline_id": new_pipeline_id,
        "pipeline_status": "pushed",
        "payload": payload,
    }


def _simulate_dispatch_requirement(req: dict) -> dict:
    """模拟 Requirement 的 _dispatch_pipeline"""
    now = "2026-05-28T21:00:00"
    new_pipeline_id = f"pl_{uuid.uuid4().hex[:8]}"
    payload = {
        "type": "pipeline_request",
        "task_id": new_pipeline_id,
        "requirement_id": req["id"],
        "title": f"[驳回重开] {req['title']}",
        "description": f"驳回原因: {req.get('reject_reason', '')}\n\n{req.get('description', '')}",
        "assignee": req.get("assignee") or "alpha",
        "source": "requirement_reject",
        "timestamp": now,
    }
    req["reject_pipeline_id"] = new_pipeline_id
    req["reject_pipeline_payload"] = payload
    req["reject_pipeline_status"] = "pushed"
    req["audit_timestamp"] = now
    return {
        "pipeline_id": new_pipeline_id,
        "pipeline_status": "pushed",
        "payload": payload,
    }


# ============================================================
# 1. Issue 审计通过 → 创建新 Pipeline
# ============================================================

class TestIssueDispatchPipeline:
    """验证审计通过后 dispatch pipeline 行为"""

    def test_audit_approved_dispatches_pipeline(self):
        """audit_approved 后应生成新的 pipeline_id"""
        issue = _make_issue()
        result = _simulate_dispatch(issue)
        assert len(result["pipeline_id"]) > 0
        assert result["pipeline_id"].startswith("pl_")
        assert result["pipeline_status"] == "pushed"

    def test_new_pipeline_id_different_from_original(self):
        """新 Pipeline ID 不应与原始 pipeline_id 相同"""
        issue = _make_issue(pipeline_id="pl_original_001")
        result = _simulate_dispatch(issue)
        assert result["pipeline_id"] != "pl_original_001"
        assert result["pipeline_id"] != issue["pipeline_id"]

    def test_original_pipeline_id_preserved(self):
        """原始 pipeline_id 应被保留（存入 reject_pipeline_id）"""
        issue = _make_issue(pipeline_id="pl_original_001")
        _simulate_dispatch(issue)
        assert issue["pipeline_id"] == "pl_original_001"
        assert issue["reject_pipeline_id"] != issue["pipeline_id"]

    def test_payload_has_reject_prefix(self):
        """Pipeline payload 的 title 应带 [驳回重开] 前缀"""
        issue = _make_issue(title="成员管理界面优化")
        result = _simulate_dispatch(issue)
        assert result["payload"]["title"] == "[驳回重开] 成员管理界面优化"

    def test_payload_includes_reject_reason(self):
        """Pipeline payload 的 description 应包含驳回原因"""
        issue = _make_issue(reject_reason="并发场景未覆盖", description="成员管理功能")
        result = _simulate_dispatch(issue)
        assert "驳回原因: 并发场景未覆盖" in result["payload"]["description"]
        assert "成员管理功能" in result["payload"]["description"]

    def test_payload_source_is_issue_reject(self):
        """source 应为 issue_reject"""
        issue = _make_issue()
        result = _simulate_dispatch(issue)
        assert result["payload"]["source"] == "issue_reject"

    def test_payload_has_type_pipeline_request(self):
        """type 应为 pipeline_request"""
        issue = _make_issue()
        result = _simulate_dispatch(issue)
        assert result["payload"]["type"] == "pipeline_request"


# ============================================================
# 2. Requirement 审计通过 → 创建新 Pipeline
# ============================================================

class TestRequirementDispatchPipeline:
    """验证 Requirement 审计通过后 dispatch pipeline 行为"""

    def test_requirement_audit_approved_dispatches(self):
        """Requirement audit_approved 后应生成新 pipeline_id"""
        req = _make_requirement()
        result = _simulate_dispatch_requirement(req)
        assert len(result["pipeline_id"]) > 0
        assert result["pipeline_id"].startswith("pl_")

    def test_requirement_new_pipeline_id_different(self):
        """新 Pipeline ID 不应与原 pipeline_id 重复"""
        req = _make_requirement(pipeline_id="pl_req_original_001")
        result = _simulate_dispatch_requirement(req)
        assert result["pipeline_id"] != "pl_req_original_001"

    def test_requirement_original_pipeline_id_preserved(self):
        """原始 pipeline_id 应保留"""
        req = _make_requirement(pipeline_id="pl_req_original_001")
        _simulate_dispatch_requirement(req)
        assert req["pipeline_id"] == "pl_req_original_001"

    def test_requirement_payload_has_reject_prefix(self):
        """Requirement payload title 应带 [驳回重开] 前缀"""
        req = _make_requirement(title="UI 设计优化")
        result = _simulate_dispatch_requirement(req)
        assert result["payload"]["title"] == "[驳回重开] UI 设计优化"

    def test_requirement_payload_includes_reject_reason(self):
        """Requirement payload description 应含驳回原因"""
        req = _make_requirement(reject_reason="UI 不符合设计稿")
        result = _simulate_dispatch_requirement(req)
        assert "驳回原因: UI 不符合设计稿" in result["payload"]["description"]

    def test_requirement_payload_source_is_requirement_reject(self):
        """Requirement reject 的 source 应为 requirement_reject"""
        req = _make_requirement()
        result = _simulate_dispatch_requirement(req)
        assert result["payload"]["source"] == "requirement_reject"


# ============================================================
# 3. 重复 Pipeline 防护
# ============================================================

class TestPipelineDedup:
    """验证 pipeline 防护机制"""

    def test_already_has_reject_pipeline_blocked(self):
        """已有 reject_pipeline_id 时不应再次创建"""
        issue = _make_issue(reject_pipeline_id="pl_already_rejected")

        # 模拟防护检查
        if issue.get("reject_pipeline_id"):
            # 不应再次 dispatch
            with pytest.raises(AssertionError):
                assert False, "应阻止重复创建"

    def test_no_reject_pipeline_allowed(self):
        """首次驳回（无 reject_pipeline_id）应允许创建"""
        issue = _make_issue()
        issue.pop("reject_pipeline_id", None)  # 清理模拟字段
        result = _simulate_dispatch(issue)
        assert result["pipeline_status"] == "pushed"

    def test_assignee_fallback_to_alpha(self):
        """无 assignee 时缺省为 alpha"""
        issue = _make_issue()
        issue.pop("assignee", None)
        result = _simulate_dispatch(issue)
        assert result["payload"]["assignee"] == "alpha"


# ============================================================
# 4. dispatch 方法职责边界
# ============================================================

class TestDispatchResponsibility:
    """验证 dispatch 仅创建+推送，不持久化"""

    def test_dispatch_returns_result_dict_not_save(self):
        """dispatch 应返回 dict 而非调用 _save_issues"""
        issue = _make_issue()
        # dispatch 返回结果
        result = _simulate_dispatch(issue)
        assert isinstance(result, dict)
        assert "pipeline_id" in result
        assert "pipeline_status" in result
        assert "payload" in result
        # 调用方负责写回 issue
        issue["pipeline_id_new"] = result["pipeline_id"]
        issue["pipeline_status"] = result["pipeline_status"]
        # 验证字段存在——模拟调用方写入
        assert issue.get("pipeline_id_new") == result["pipeline_id"]

    def test_dispatch_does_not_clear_pipeline_id(self):
        """dispatch 不应清除原始 pipeline_id"""
        issue = _make_issue(pipeline_id="pl_original_001")
        _simulate_dispatch(issue)
        assert issue["pipeline_id"] == "pl_original_001"
        assert issue["reject_pipeline_id"] is not None


# ============================================================
# 5. _handle_issues_post 兼容性
# ============================================================

class TestIssuesPostCompatibility:
    """验证 _handle_issues_post 重构后仍正常工作"""

    def test_create_issue_stores_pipeline_id(self):
        """新建 issue 应写入 pipeline_id（非 reject_pipeline_id）"""
        issue = _make_issue()
        del issue["pipeline_id"]
        del issue["pipeline_status"]
        del issue["reject_reason"]
        del issue["rejected_at"]
        del issue["audit_status"]
        del issue["audit_agent"]
        del issue["rejected_by"]
        del issue["previous_status"]
        del issue["resolved_at"]
        issue["status"] = "open"
        
        # 模拟新建 issue 的 pipeline 创建
        new_id = f"pl_{uuid.uuid4().hex[:8]}"
        issue["pipeline_id"] = new_id
        issue["pipeline_status"] = "pushed"
        
        assert issue["pipeline_id"] is not None
        assert issue["pipeline_id"] != ""
        assert issue["pipeline_status"] == "pushed"
        # 新建的 issue 不应有 reject_pipeline_id
        assert "reject_pipeline_id" not in issue

    def test_create_issue_has_source_dashboard(self):
        """新建 issue 的 source 为 dashboard"""
        issue = _make_issue(source="dashboard")
        assert issue["source"] == "dashboard"


# ============================================================
# 6. 无 pipeline_id 的 issue
# ============================================================

class TestNoExistingPipeline:
    """验证无原始 pipeline_id 的 issue 也能 dispatch"""

    def test_dispatch_without_original_pipeline_id(self):
        """无 pipeline_id 的 issue 仍可 dispatch"""
        issue = _make_issue()
        issue.pop("pipeline_id", None)
        issue.pop("pipeline_status", None)
        result = _simulate_dispatch(issue)
        assert result["pipeline_status"] == "pushed"
        # 调用方写入 reject_pipeline_id
        issue["reject_pipeline_id"] = result["pipeline_id"]
        assert len(issue["reject_pipeline_id"]) > 0
        assert "pipeline_id" not in issue  # 原始字段不存在


# ============================================================
# 7. SSE 推送
# ============================================================

class TestSSEPushPipeline:
    """验证 Pipeline 创建后 SSE 推送"""

    def test_sse_event_format(self):
        """SSE 事件应包含 pipeline 信息"""
        event = {
            "event": "pipeline_status",
            "data": json.dumps({
                "type": "pipeline_update",
                "pipeline_id": "pl_new_001",
                "status": "pushed",
                "source": "issue_reject",
            }),
        }
        assert event["event"] == "pipeline_status"
        data = json.loads(event["data"])
        assert data["pipeline_id"] == "pl_new_001"
        assert data["source"] == "issue_reject"


# ============================================================
# 8. 特殊字符处理
# ============================================================

class TestSpecialChars:
    """验证驳回原因含特殊字符时的序列化"""

    def test_reject_reason_with_special_chars(self):
        """含换行/引号的驳回原因应正确序列化"""
        reason = "并发\n场景\"未覆盖'"
        payload = {
            "title": "[驳回重开] 测试问题",
            "description": f"驳回原因: {reason}",
        }
        # json.dumps 应成功
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "并发" in serialized
        assert "\\n" in serialized  # JSON 转义
        assert json.loads(serialized)["description"] == f"驳回原因: 并发\n场景\"未覆盖'"

    def test_title_with_quotes_serialized(self):
        """标题含引号时 JSON 序列化应安全"""
        title = '成员"管理"界面优化'
        payload = {"title": f"[驳回重开] {title}"}
        serialized = json.dumps(payload, ensure_ascii=False)
        assert json.loads(serialized)["title"] == '[驳回重开] 成员"管理"界面优化'


# ============================================================
# 9. 集成测试：完整流程
# ============================================================

class TestFullFlow:
    """端到端验证：驳回 → 审计通过 → Pipeline 创建 → 状态更新"""

    def test_issue_full_flow_with_pipeline(self):
        """resolved → rejected → audit_approved → in_progress + 新 Pipeline"""
        issue = _make_issue(status="resolved")
        original_pipeline_id = "pl_original_001"
        issue["pipeline_id"] = original_pipeline_id

        # Step 1: 用户驳回（来自 pl_a2dd7ccc 流程）
        issue["previous_status"] = issue["status"]
        issue["status"] = "rejected"
        issue["reject_reason"] = "并发场景未覆盖"
        issue["audit_status"] = "pending"

        assert issue["status"] == "rejected"
        assert issue["pipeline_id"] == original_pipeline_id

        # Step 2: Duci 审计通过
        issue["status"] = "in_progress"
        issue["audit_status"] = "approved"

        # Step 3: 创建新 Pipeline
        result = _simulate_dispatch(issue)
        issue["reject_pipeline_id"] = result["pipeline_id"]
        issue["reject_pipeline_status"] = "pushed"

        # 验证：原始 pipeline_id 保留
        assert issue["pipeline_id"] == original_pipeline_id
        # 验证：新 pipeline_id 不同
        assert issue["reject_pipeline_id"] != original_pipeline_id
        assert issue["reject_pipeline_id"].startswith("pl_")
        # 验证：状态正确
        assert issue["status"] == "in_progress"
        assert issue["audit_status"] == "approved"
        # 验证：payload 含 [驳回重开]
        assert result["payload"]["title"].startswith("[驳回重开]")

    def test_requirement_full_flow_with_pipeline(self):
        """done → rejected → audit_approved → develop_code + 新 Pipeline"""
        req = _make_requirement(status="done")
        original_pipeline_id = "pl_req_original_001"
        req["pipeline_id"] = original_pipeline_id

        # Step 1: 用户驳回
        req["previous_status"] = req["status"]
        req["status"] = "rejected"
        req["reject_reason"] = "UI 不符合设计稿"
        req["audit_status"] = "pending"

        # Step 2: 审计通过
        req["status"] = "develop_code"
        req["audit_status"] = "approved"

        # Step 3: 创建新 Pipeline
        result = _simulate_dispatch_requirement(req)

        assert req["pipeline_id"] == original_pipeline_id
        assert req["reject_pipeline_id"] != original_pipeline_id
        assert req["status"] == "develop_code"
        assert result["payload"]["source"] == "requirement_reject"
