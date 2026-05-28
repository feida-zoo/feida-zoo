#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_b5e6038b — issue done 但问题管理界面状态还是待处理
测试套件：验证 pipeline done 时 _handle_phase_complete 同步更新 issues.json

覆盖：
1.  pipeline done → 找到关联 issue → status=resolved, resolved_at=now
2.  pipeline done → 无匹配 issue → gracefully skip
3.  pipeline done → issues.json 不存在 → gracefully skip
4.  pipeline done → 写 issues.json 异常 → gracefully skip（降级）
5.  pipeline 未到 done → 不触发 issue 更新
6.  已 done pipeline 重复上报 → 幂等，不重复更新

用法：
    cd <project_root>
    ./venv/bin/pytest framework/tests/ut/test_pipeline_done_syncs_issue_status.py -v
"""

import copy
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")
sys.path.insert(0, str(PROJECT_ROOT / "framework" / "core" / "mesh"))

# 导入待测函数
from zoo_mesh_daemon import _handle_phase_complete


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_deps():
    """Mock _handle_phase_complete 的所有外部依赖。"""
    # requirements mock data
    reqs = [
        {
            "id": "req-001",
            "pipeline_id": "pl_test1234",
            "title": "Test Issue",
            "status": "request",
            "phase": "request",
        }
    ]

    issues_data = [
        {
            "id": "issue-001",
            "title": "Test Issue",
            "status": "open",
            "pipeline_id": "pl_test1234",
            "created_at": "2026-05-26T10:00:00",
            "updated_at": "2026-05-26T10:00:00",
            "resolved_at": None,
        }
    ]

    with patch("zoo_mesh_daemon._load_requirements", side_effect=lambda: copy.deepcopy(reqs)) as m_load_reqs, \
         patch("zoo_mesh_daemon._save_requirements") as m_save_reqs, \
         patch("zoo_mesh_daemon._get_next_phase", return_value="done") as m_next_phase, \
         patch("zoo_mesh_daemon._publish_phase_advancement") as m_publish, \
         patch("zoo_mesh_daemon._clear_pending_for_pipeline") as m_clear, \
         patch("zoo_mesh_daemon.mesh") as m_mesh, \
         patch("zoo_mesh_daemon.logger") as m_logger, \
         patch("zoo_mesh_daemon.ZooPipeline") as m_pipeline_cls, \
         patch("zoo_mesh_daemon.time.strftime", return_value="2026-05-26T12:00:00") as m_strftime:

        m_mesh.get_pipeline_state.return_value = "request"

        yield {
            "load_reqs": m_load_reqs,
            "save_reqs": m_save_reqs,
            "next_phase": m_next_phase,
            "publish": m_publish,
            "clear": m_clear,
            "mesh": m_mesh,
            "logger": m_logger,
            "pipeline_cls": m_pipeline_cls,
            "strftime": m_strftime,
            "issues_data": issues_data,
            "reqs_data": reqs,
        }


# ── 测试类 ────────────────────────────────────────────────────────────────


class TestPipelineDoneSyncsIssueStatus:
    """核心测试：pipeline done 时同步更新 issue status。"""

    def test_done_updates_issue_to_resolved(self, mock_deps, tmp_path):
        """pipeline 完成 → 关联 issue status 变为 resolved，resolved_at 设置。"""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps(mock_deps["issues_data"], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_instance = MagicMock()
            m_path_instance.exists.return_value = True
            m_path_instance.__truediv__ = lambda self, other: self
            # 模拟 issues.json 路径
            def path_side(*args):
                path_str = "/".join(str(a) for a in args)
                if "issues.json" in path_str:
                    return issues_file
                return Path(*args)
            m_path_cls.side_effect = path_side

            _handle_phase_complete(
                "phase_complete:pl_test1234:pass",
                "alpha"
            )

        # 验证 issues.json 被更新
        updated_issues = json.loads(issues_file.read_text(encoding="utf-8"))
        issue = updated_issues[0]
        assert issue["status"] == "resolved"
        assert issue["resolved_at"] == "2026-05-26T12:00:00"
        assert issue["updated_at"] == "2026-05-26T12:00:00"

    def test_done_no_matching_issue_gracefully_skips(self, mock_deps, tmp_path):
        """pipeline 完成但 issues.json 中无匹配 pipeline_id → skip。"""
        issues_no_match = [
            {
                "id": "issue-002",
                "status": "open",
                "pipeline_id": "pl_other5678",  # 不同 pipeline
            }
        ]
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(issues_no_match), encoding="utf-8")

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = issues_file
            _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        # issues.json 不应被修改
        issues_after = json.loads(issues_file.read_text(encoding="utf-8"))
        assert issues_after[0]["status"] == "open"
        assert issues_after[0]["pipeline_id"] == "pl_other5678"

    def test_done_issues_json_not_exists_gracefully_skips(self, mock_deps, tmp_path):
        """issues.json 不存在 → gracefully skip，不抛异常。"""
        non_existent = tmp_path / "no_issues.json"

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = non_existent
            # 不应抛异常
            _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        assert not non_existent.exists()

    def test_done_write_issues_json_exception_degrades(self, mock_deps, tmp_path):
        """写 issues.json 异常 → 降级，不影响 pipeline 完成流程。"""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(mock_deps["issues_data"]), encoding="utf-8")

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = issues_file
            with patch("builtins.open", side_effect=OSError("disk full")):
                # 不应抛异常
                _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        # pipeline 仍应完成（requirements 已保存）
        mock_deps["save_reqs"].assert_called_once()

    def test_not_done_does_not_touch_issues(self, mock_deps, tmp_path):
        """pipeline 未到 done 阶段 → 不更新 issues.json。"""
        mock_deps["next_phase"].return_value = "design"  # 不是 done

        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(mock_deps["issues_data"]), encoding="utf-8")

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = issues_file
            _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        # issues.json 不应被修改
        issues_after = json.loads(issues_file.read_text(encoding="utf-8"))
        assert issues_after[0]["status"] == "open"

    def test_idempotent_done_pipeline_skips(self, mock_deps, tmp_path):
        """已 done 的 pipeline 重复上报 → 幂等，不重复更新。"""
        # 设置 requirement 已为 done
        mock_deps["reqs_data"][0]["status"] = "done"
        mock_deps["mesh"].get_pipeline_state.return_value = "done"

        issues_file = tmp_path / "issues.json"
        original_issues = [
            {
                "id": "issue-001",
                "status": "resolved",
                "pipeline_id": "pl_test1234",
                "resolved_at": "2026-05-26T11:00:00",
            }
        ]
        issues_file.write_text(json.dumps(original_issues), encoding="utf-8")

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = issues_file
            _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        # issues.json 不应被修改
        issues_after = json.loads(issues_file.read_text(encoding="utf-8"))
        assert issues_after[0]["status"] == "resolved"
        assert issues_after[0]["resolved_at"] == "2026-05-26T11:00:00"
        # 验证 logger 提示已跳过（state 文件先触发 return）
        mock_deps["logger"].info.assert_any_call(
            "Pipeline pl_test1234 state 文件已 done，跳过重复处理"
        )


class TestPipelineDoneEdgeCases:
    """边界测试。"""

    def test_extract_pipeline_id_from_various_formats(self, mock_deps, tmp_path):
        """从不同格式的 body 中提取 pipeline_id，并验证 done 分支触发。"""
        # 设置 requirement 状态为 deliver，使 next_phase = done
        mock_deps["reqs_data"][0]["status"] = "deliver"
        mock_deps["reqs_data"][0]["phase"] = "deliver"

        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(mock_deps["issues_data"]), encoding="utf-8")

        test_cases = [
            "phase_complete:pl_test1234:pass",
            "pl_test1234",
            "PI_DONE:pl_test1234",
            "Phase: deliver pl_test1234",
        ]

        for body in test_cases:
            with patch("zoo_mesh_daemon.Path") as m_path_cls:
                m_path_cls.return_value = issues_file
                # 重置 issues 文件
                issues_file.write_text(json.dumps(mock_deps["issues_data"]), encoding="utf-8")

                _handle_phase_complete(body, "alpha")

                issues_after = json.loads(issues_file.read_text(encoding="utf-8"))
                assert issues_after[0]["status"] == "resolved", f"Failed for body: {body}"

    def test_multiple_issues_only_updates_matching_one(self, mock_deps, tmp_path):
        """多个 issue 中只有一个匹配 pipeline_id → 只更新匹配的。"""
        issues_data = [
            {
                "id": "issue-001",
                "status": "open",
                "pipeline_id": "pl_test1234",
                "resolved_at": None,
            },
            {
                "id": "issue-002",
                "status": "open",
                "pipeline_id": "pl_other5678",
                "resolved_at": None,
            },
        ]
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(issues_data), encoding="utf-8")

        with patch("zoo_mesh_daemon.Path") as m_path_cls:
            m_path_cls.return_value = issues_file
            _handle_phase_complete("phase_complete:pl_test1234:pass", "alpha")

        updated = json.loads(issues_file.read_text(encoding="utf-8"))
        assert updated[0]["status"] == "resolved"
        assert updated[1]["status"] == "open"  # 未匹配的不变


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
