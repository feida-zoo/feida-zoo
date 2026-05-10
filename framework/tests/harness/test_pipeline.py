"""
Tests for ZooPipeline 主引擎
"""

import pytest
from framework.core.harness.pipeline import (
    ZooPipeline, InvalidPhase, PipelineCancelled,
    ZooPipelineError,
)
from framework.core.harness.state_machine import StateMachine


class TestZooPipelineSingleton:
    """测试单例模式"""

    def test_get_instance_creates_instance(self):
        ZooPipeline.reset_instance()
        p1 = ZooPipeline.get_instance(task_id="t1", agent_id="weaver")
        assert p1 is not None
        assert p1.task_id == "t1"
        assert p1.agent_id == "weaver"
        ZooPipeline.reset_instance()

    def test_get_instance_returns_same_instance(self):
        ZooPipeline.reset_instance()
        p1 = ZooPipeline.get_instance(task_id="t1", agent_id="weaver")
        p2 = ZooPipeline.get_instance(task_id="t2", agent_id="alpha")
        assert p1 is p2
        assert p1.task_id == "t1"  # 首次创建时锁定
        ZooPipeline.reset_instance()


class TestZooPipelineInit:
    """测试初始化"""

    def test_init_sets_properties(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        assert p.task_id == "t1"
        assert p.agent_id == "weaver"
        assert p.zoo_mesh is None
        assert p.current_phase == "request"
        assert p.current_state == "request"
        ZooPipeline.reset_instance()

    def test_retry_counts_initialized(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        for phase in ZooPipeline.PHASES:
            assert p._retry_counts[phase] == 0
        assert p._total_rollbacks == 0
        ZooPipeline.reset_instance()


class TestZooPipelineAdvanceTo:
    """测试阶段推进"""

    def test_advance_to_valid_phase(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        assert p.advance_to("validate") is True
        assert p.current_phase == "validate"
        assert p.current_state == "validate"
        ZooPipeline.reset_instance()

    def test_advance_to_invalid_phase_raises(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        with pytest.raises(InvalidPhase):
            p.advance_to("nonexistent")
        ZooPipeline.reset_instance()

    def test_advance_to_after_done_returns_false(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        p.advance_to("review")
        p.advance_to("develop")
        p.advance_to("audit")
        p.advance_to("final_check")
        p.advance_to("deliver")
        p.mark_done()
        assert p.advance_to("validate") is False
        ZooPipeline.reset_instance()

    def test_advance_to_after_cancelled_returns_false(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.cancel("owner")
        assert p.advance_to("validate") is False
        ZooPipeline.reset_instance()


class TestZooPipelineRollback:
    """测试回退计数"""

    def test_rollback_increments_count(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        result = p.rollback("design")
        assert result == "retry"
        assert p._retry_counts["design"] == 1
        ZooPipeline.reset_instance()

    def test_rollback_exceeds_phase_limit_returns_escalate(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        # design max = 2
        p.rollback("design")
        p.rollback("design")
        result = p.rollback("design")
        assert result == "escalate"
        ZooPipeline.reset_instance()

    def test_rollback_exceeds_total_limit_returns_escalate(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        # 触发超过 MAX_TOTAL_ROLLBACKS (10)
        for _ in range(11):
            result = p.rollback("design")
        assert result == "escalate"
        assert p._total_rollbacks == 11
        ZooPipeline.reset_instance()


class TestZooPipelineCancel:
    """测试取消"""

    def test_cancel_sets_cancelled(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        assert p.cancel("owner") is True
        assert p.is_cancelled is True
        assert p.current_state == "cancelled"
        ZooPipeline.reset_instance()

    def test_cancel_after_done_returns_false(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        p.advance_to("review")
        p.advance_to("develop")
        p.advance_to("audit")
        p.advance_to("final_check")
        p.advance_to("deliver")
        p.mark_done()
        assert p.cancel("owner") is False
        ZooPipeline.reset_instance()

    def test_cancel_idempotent(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.cancel("owner")
        second = p.cancel("owner")
        assert second is False
        ZooPipeline.reset_instance()


class TestZooPipelineMarkDone:
    """测试完成标记"""

    def test_mark_done_sets_done(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        p.advance_to("review")
        p.advance_to("develop")
        p.advance_to("audit")
        p.advance_to("final_check")
        p.advance_to("deliver")
        assert p.mark_done() is True
        assert p.is_done is True
        assert p.current_state == "done"
        ZooPipeline.reset_instance()

    def test_mark_done_after_cancelled_returns_false(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        p.advance_to("review")
        p.advance_to("develop")
        p.advance_to("audit")
        p.advance_to("final_check")
        p.advance_to("deliver")
        p.cancel("owner")
        assert p.mark_done() is False
        ZooPipeline.reset_instance()


class TestZooPipelineHandleError:
    """测试错误处理"""

    def test_handle_error_escalates(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        result = p.handle_error(RuntimeError("boom"))
        assert result == "escalated"
        assert p.current_state == "escalated"
        ZooPipeline.reset_instance()

    def test_handle_error_from_terminal_does_not_escalate(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        p.advance_to("validate")
        p.advance_to("design")
        p.advance_to("review")
        p.advance_to("develop")
        p.advance_to("audit")
        p.advance_to("final_check")
        p.advance_to("deliver")
        p.mark_done()
        result = p.handle_error(RuntimeError("boom"))
        assert result == "done"  # 终态不escalate，返回done
        assert p.current_state == "done"
        ZooPipeline.reset_instance()


class TestZooPipelineGetStatus:
    """测试状态快照"""

    def test_get_status_returns_dict(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        status = p.get_status()
        assert isinstance(status, dict)
        assert status["task_id"] == "t1"
        assert status["agent_id"] == "weaver"
        assert status["current_state"] == "request"
        assert status["is_done"] is False
        assert status["is_cancelled"] is False
        ZooPipeline.reset_instance()


class TestZooPipelinePhases:
    """测试阶段列表"""

    def test_phases_list_complete(self):
        expected = [
            "request", "validate", "design", "review",
            "develop", "audit", "final_check", "deliver"
        ]
        assert ZooPipeline.PHASES == expected

    def test_all_phases_have_retry_entry(self):
        ZooPipeline.reset_instance()
        p = ZooPipeline(task_id="t1", agent_id="weaver")
        for phase in ZooPipeline.PHASES:
            assert phase in p._retry_counts
        ZooPipeline.reset_instance()