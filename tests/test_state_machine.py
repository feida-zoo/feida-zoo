"""
StateMachine 单元测试

覆盖范围：
- 所有合法正向/回退/异常状态转换
- 非法转换抛出 InvalidTransition
- 终态判断 (is_terminal)
- handle_error 错误兜底 → escalated
- 边界条件（未知状态、终态上的 handle_error）
"""

import importlib.util
import os
import pytest

# 直接加载目标模块，避免 framework/core/__init__.py 的连锁导入
_module_path = os.path.join(
    os.path.dirname(__file__), "..", "framework", "core", "harness", "state_machine.py"
)
spec = importlib.util.spec_from_file_location("state_machine", _module_path)
_state_machine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_state_machine)

InvalidTransition = _state_machine.InvalidTransition
StateMachine = _state_machine.StateMachine


class TestValidTransitions:
    """测试所有合法状态转换"""

    def test_request_to_validate(self):
        assert StateMachine.transition("request", "validate") is True

    def test_request_to_cancelled(self):
        assert StateMachine.transition("request", "cancelled") is True

    def test_validate_to_request(self):
        assert StateMachine.transition("validate", "request") is True

    def test_validate_to_design(self):
        assert StateMachine.transition("validate", "design") is True

    def test_validate_to_cancelled(self):
        assert StateMachine.transition("validate", "cancelled") is True

    def test_design_to_review(self):
        assert StateMachine.transition("design", "review") is True

    def test_design_to_cancelled(self):
        assert StateMachine.transition("design", "cancelled") is True

    def test_design_to_timed_out(self):
        assert StateMachine.transition("design", "timed_out") is True

    def test_review_to_design(self):
        assert StateMachine.transition("review", "design") is True

    def test_review_to_develop(self):
        assert StateMachine.transition("review", "develop") is True

    def test_review_to_cancelled(self):
        assert StateMachine.transition("review", "cancelled") is True

    def test_review_to_timed_out(self):
        assert StateMachine.transition("review", "timed_out") is True

    def test_develop_to_audit(self):
        assert StateMachine.transition("develop", "audit") is True

    def test_develop_to_cancelled(self):
        assert StateMachine.transition("develop", "cancelled") is True

    def test_develop_to_timed_out(self):
        assert StateMachine.transition("develop", "timed_out") is True

    def test_audit_to_develop(self):
        assert StateMachine.transition("audit", "develop") is True

    def test_audit_to_final_check(self):
        assert StateMachine.transition("audit", "final_check") is True

    def test_audit_to_cancelled(self):
        assert StateMachine.transition("audit", "cancelled") is True

    def test_audit_to_timed_out(self):
        assert StateMachine.transition("audit", "timed_out") is True

    def test_final_check_to_deliver(self):
        assert StateMachine.transition("final_check", "deliver") is True

    def test_final_check_to_develop(self):
        assert StateMachine.transition("final_check", "develop") is True

    def test_final_check_to_cancelled(self):
        assert StateMachine.transition("final_check", "cancelled") is True

    def test_deliver_to_done(self):
        assert StateMachine.transition("deliver", "done") is True

    def test_deliver_to_cancelled(self):
        assert StateMachine.transition("deliver", "cancelled") is True

    def test_timed_out_to_escalated(self):
        assert StateMachine.transition("timed_out", "escalated") is True

    def test_timed_out_to_cancelled(self):
        assert StateMachine.transition("timed_out", "cancelled") is True

    def test_escalated_to_request(self):
        assert StateMachine.transition("escalated", "request") is True

    def test_escalated_to_cancelled(self):
        assert StateMachine.transition("escalated", "cancelled") is True

    def test_all_states_exist(self):
        expected = {
            "request", "validate", "design", "review",
            "develop", "audit", "final_check", "deliver",
            "done", "cancelled", "timed_out", "escalated",
        }
        assert set(StateMachine.ALL_STATES) == expected


class TestInvalidTransitions:
    """测试非法状态转换，应抛出 InvalidTransition"""

    def test_request_to_request(self):
        with pytest.raises(InvalidTransition) as exc:
            StateMachine.transition("request", "request")
        assert "request" in str(exc.value)
        assert "request" in str(exc.value)

    def test_request_to_design(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("request", "design")

    def test_done_to_any(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("done", "request")

    def test_cancelled_to_any(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("cancelled", "request")

    def test_develop_to_review(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("develop", "review")

    def test_escalated_to_escalated(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("escalated", "escalated")

    def test_validate_to_escalated(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("validate", "escalated")

    def test_unknown_from_state(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("unknown", "request")

    def test_unknown_to_state(self):
        with pytest.raises(InvalidTransition):
            StateMachine.transition("request", "unknown")


class TestCanTransition:
    """测试 can_transition 查询接口"""

    def test_can_request_to_validate(self):
        assert StateMachine.can_transition("request", "validate") is True

    def test_cannot_request_to_design(self):
        assert StateMachine.can_transition("request", "design") is False

    def test_cannot_done_to_any(self):
        assert StateMachine.can_transition("done", "cancelled") is False

    def test_unknown_states(self):
        assert StateMachine.can_transition("foo", "bar") is False
        assert StateMachine.can_transition("request", "bar") is False


class TestGetValidTransitions:
    """测试 get_valid_transitions"""

    def test_request_valid_transitions(self):
        assert set(StateMachine.get_valid_transitions("request")) == {"validate", "cancelled"}

    def test_done_no_transitions(self):
        assert StateMachine.get_valid_transitions("done") == []

    def test_unknown_state_empty(self):
        assert StateMachine.get_valid_transitions("unknown") == []


class TestIsTerminal:
    """测试终态判断"""

    def test_done_is_terminal(self):
        assert StateMachine.is_terminal("done") is True

    def test_cancelled_is_terminal(self):
        assert StateMachine.is_terminal("cancelled") is True

    def test_request_not_terminal(self):
        assert StateMachine.is_terminal("request") is False

    def test_escalated_not_terminal(self):
        assert StateMachine.is_terminal("escalated") is False

    def test_timed_out_not_terminal(self):
        assert StateMachine.is_terminal("timed_out") is False


class TestHandleError:
    """测试 handle_error 错误兜底"""

    def test_error_from_design_goes_to_escalated(self):
        err = ValueError("设计出错")
        assert StateMachine.handle_error("design", err) is True

    def test_error_from_review_goes_to_escalated(self):
        err = RuntimeError("审核异常")
        assert StateMachine.handle_error("review", err) is True

    def test_error_from_develop_goes_to_escalated(self):
        err = TypeError("实现异常")
        assert StateMachine.handle_error("develop", err) is True

    def test_error_from_audit_goes_to_escalated(self):
        err = ZeroDivisionError("审计异常")
        assert StateMachine.handle_error("audit", err) is True

    def test_error_from_timed_out_goes_to_escalated(self):
        err = TimeoutError("超时")
        assert StateMachine.handle_error("timed_out", err) is True

    def test_error_from_request_cannot_escalated_raises_original(self):
        err = KeyError("未知状态")
        with pytest.raises(KeyError):
            StateMachine.handle_error("request", err)

    def test_error_from_validate_cannot_escalated_raises_original(self):
        err = ConnectionError("连接失败")
        with pytest.raises(ConnectionError):
            StateMachine.handle_error("validate", err)

    def test_error_from_final_check_goes_to_escalated(self):
        err = PermissionError("权限不足")
        assert StateMachine.handle_error("final_check", err) is True

    def test_error_from_deliver_goes_to_escalated(self):
        err = IOError("写入失败")
        assert StateMachine.handle_error("deliver", err) is True

    def test_error_on_terminal_done_raises_original(self):
        err = RuntimeError("终态错误")
        with pytest.raises(RuntimeError):
            StateMachine.handle_error("done", err)

    def test_error_on_terminal_cancelled_raises_original(self):
        err = RuntimeError("终态错误")
        with pytest.raises(RuntimeError):
            StateMachine.handle_error("cancelled", err)


class TestInvalidTransitionException:
    """测试异常类属性"""

    def test_exception_attributes(self):
        exc = InvalidTransition("request", "design")
        assert exc.from_state == "request"
        assert exc.to_state == "design"
        assert "request → design 非法" in str(exc)


class TestHappyPath:
    """测试完整正向流程"""

    def test_full_pipeline_happy_path(self):
        """从 request 到 done 的完整正向流程"""
        assert StateMachine.transition("request", "validate") is True
        assert StateMachine.transition("validate", "design") is True
        assert StateMachine.transition("design", "review") is True
        assert StateMachine.transition("review", "develop") is True
        assert StateMachine.transition("develop", "audit") is True
        assert StateMachine.transition("audit", "final_check") is True
        assert StateMachine.transition("final_check", "deliver") is True
        assert StateMachine.transition("deliver", "done") is True

    def test_rollback_then_continue(self):
        """review → design → review → develop 回退后继续"""
        assert StateMachine.transition("design", "review") is True
        assert StateMachine.transition("review", "design") is True
        assert StateMachine.transition("design", "review") is True
        assert StateMachine.transition("review", "develop") is True

    def test_timeout_then_escalated_then_restart(self):
        """design → timed_out → escalated → request 重启"""
        assert StateMachine.transition("design", "timed_out") is True
        assert StateMachine.transition("timed_out", "escalated") is True
        assert StateMachine.transition("escalated", "request") is True
