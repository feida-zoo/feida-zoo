"""Tests for the harness state machine."""

import pytest
from framework.core.harness.state_machine import StateMachine, InvalidTransition


class TestStateMachineTransitions:
    """Test valid and invalid state transitions."""

    def test_request_to_validate(self):
        sm = StateMachine()
        assert sm.transition("request", "validate") is True

    def test_request_to_cancelled(self):
        sm = StateMachine()
        assert sm.transition("request", "cancelled") is True

    def test_request_to_design_invalid(self):
        sm = StateMachine()
        with pytest.raises(InvalidTransition):
            sm.transition("request", "design")

    def test_validate_to_design(self):
        sm = StateMachine()
        assert sm.transition("validate", "design") is True

    def test_validate_to_request_rollback(self):
        sm = StateMachine()
        assert sm.transition("validate", "request") is True

    def test_design_to_review(self):
        sm = StateMachine()
        assert sm.transition("design", "review") is True

    def test_design_to_timed_out(self):
        sm = StateMachine()
        assert sm.transition("design", "timed_out") is True

    def test_review_to_design_rollback(self):
        sm = StateMachine()
        assert sm.transition("review", "design") is True

    def test_review_to_develop(self):
        sm = StateMachine()
        assert sm.transition("review", "develop") is True

    def test_develop_to_audit(self):
        sm = StateMachine()
        assert sm.transition("develop", "audit") is True

    def test_audit_to_develop_rollback(self):
        sm = StateMachine()
        assert sm.transition("audit", "develop") is True

    def test_audit_to_final_check(self):
        sm = StateMachine()
        assert sm.transition("audit", "final_check") is True

    def test_final_check_to_deliver(self):
        sm = StateMachine()
        assert sm.transition("final_check", "deliver") is True

    def test_final_check_to_develop_reject(self):
        sm = StateMachine()
        assert sm.transition("final_check", "develop") is True

    def test_deliver_to_done(self):
        sm = StateMachine()
        assert sm.transition("deliver", "done") is True

    def test_done_is_terminal(self):
        sm = StateMachine()
        with pytest.raises(InvalidTransition):
            sm.transition("done", "request")

    def test_cancelled_is_terminal(self):
        sm = StateMachine()
        with pytest.raises(InvalidTransition):
            sm.transition("cancelled", "request")

    def test_timed_out_to_escalated(self):
        sm = StateMachine()
        assert sm.transition("timed_out", "escalated") is True

    def test_timed_out_to_cancelled(self):
        sm = StateMachine()
        assert sm.transition("timed_out", "cancelled") is True

    def test_escalated_to_request(self):
        sm = StateMachine()
        assert sm.transition("escalated", "request") is True

    def test_escalated_to_cancelled(self):
        sm = StateMachine()
        assert sm.transition("escalated", "cancelled") is True

    def test_invalid_from_state(self):
        sm = StateMachine()
        with pytest.raises(InvalidTransition):
            sm.transition("nonexistent", "validate")

    def test_review_cannot_go_to_audit(self):
        sm = StateMachine()
        with pytest.raises(InvalidTransition):
            sm.transition("review", "audit")


class TestStateMachineErrorHandling:
    """Test error handling paths."""

    def test_handle_error_escalates(self):
        sm = StateMachine()
        result = sm.handle_error("design", RuntimeError("boom"))
        assert result is True  # escalated is valid from any via handle_error

    def test_error_from_done(self):
        sm = StateMachine()
        result = sm.handle_error("done", RuntimeError("boom"))
        assert result is True

    def test_error_from_cancelled(self):
        sm = StateMachine()
        result = sm.handle_error("cancelled", RuntimeError("boom"))
        assert result is True


class TestStateMachineGetValidTargets:
    """Test querying valid transition targets."""

    def test_valid_targets_request(self):
        sm = StateMachine()
        targets = sm.get_valid_targets("request")
        assert set(targets) == {"validate", "cancelled"}

    def test_valid_targets_review(self):
        sm = StateMachine()
        targets = sm.get_valid_targets("review")
        assert set(targets) == {"design", "develop", "cancelled", "timed_out", "escalated"}

    def test_valid_targets_done(self):
        sm = StateMachine()
        targets = sm.get_valid_targets("done")
        assert targets == []

    def test_valid_targets_unknown(self):
        sm = StateMachine()
        targets = sm.get_valid_targets("unknown")
        assert targets == []


class TestStateMachineIsTerminal:
    """Test terminal state detection."""

    def test_done_is_terminal(self):
        assert StateMachine.is_terminal("done") is True

    def test_cancelled_is_terminal(self):
        assert StateMachine.is_terminal("cancelled") is True

    def test_request_not_terminal(self):
        assert StateMachine.is_terminal("request") is False

    def test_develop_not_terminal(self):
        assert StateMachine.is_terminal("develop") is False
