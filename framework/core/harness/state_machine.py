"""
有限状态机 (FSM) —— 飝龘动物园 Harness 核心

设计约束来自 §2.3 完整状态机规范：
- 12 个状态，覆盖任务全生命周期
- TRANSITIONS 字典定义合法转换
- 异常兜底：handle_error → escalated
"""


class InvalidTransition(Exception):
    """状态转换非法时抛出"""

    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"{from_state} → {to_state} 非法")


class StateMachine:
    """
    飝龘动物园任务状态机

    完整状态：
      request → validate → design → review → develop → test → audit → final_check → deliver → done
      (cancelled, timed_out, escalated 为异常/终态分支)
    """

    TRANSITIONS = {
        "request":     ["validate", "cancelled"],
        "validate":    ["request", "design", "cancelled"],
        "design":      ["ui_design", "cancelled", "timed_out", "escalated"],
        "ui_design":   ["review", "design", "cancelled", "timed_out", "escalated"],
        "review":      ["design", "develop", "develop_wt", "cancelled", "timed_out", "escalated"],
        "develop":     ["develop_wt", "test", "cancelled", "timed_out", "escalated"],
        "develop_wt":  ["review_test", "cancelled", "timed_out", "escalated"],
        "review_test": ["develop_code", "develop_wt", "cancelled", "timed_out", "escalated"],
        "develop_code":["test", "cancelled", "timed_out", "escalated"],
        "test":        ["audit", "develop", "develop_code", "cancelled", "timed_out", "escalated"],
        "audit":       ["develop", "final_check", "cancelled", "timed_out", "escalated"],
        "final_check": ["deliver", "develop", "cancelled", "escalated"],
        "deliver":     ["done", "cancelled", "escalated"],
        "done":        [],
        "timed_out":   ["escalated", "cancelled"],
        "cancelled":   [],
        "escalated":   ["request", "cancelled"],
    }

    ALL_STATES = list(TRANSITIONS.keys())

    # 终态：转换出去为空
    TERMINAL_STATES = {"done", "cancelled"}

    @classmethod
    def transition(cls, from_state: str, to_state: str) -> bool:
        """
        安全的状态转换

        合法返回 True，不合法抛出 InvalidTransition
        """
        if from_state not in cls.TRANSITIONS:
            raise InvalidTransition(from_state, to_state)
        if to_state not in cls.TRANSITIONS:
            raise InvalidTransition(from_state, to_state)

        allowed = cls.TRANSITIONS[from_state]
        if to_state in allowed:
            return True
        raise InvalidTransition(from_state, to_state)

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        """查询是否允许转换，不抛出异常"""
        if from_state not in cls.TRANSITIONS:
            return False
        if to_state not in cls.TRANSITIONS:
            return False
        return to_state in cls.TRANSITIONS[from_state]

    @classmethod
    def get_valid_transitions(cls, state: str) -> list[str]:
        """获取从给定状态可合法转换到的所有目标状态"""
        return list(cls.TRANSITIONS.get(state, []))

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """判断是否为终态（不可再转换）"""
        return state in cls.TERMINAL_STATES

    @classmethod
    def get_valid_targets(cls, state: str) -> list[str]:
        """get_valid_transitions 的别名（测试兼容）"""
        return cls.get_valid_transitions(state)

    @classmethod
    def handle_error(cls, current_state: str, error: Exception) -> bool:
        """
        错误兜底：无法处理的异常 → escalated

        从任意状态（只要不是终态）尝试转到 escalated。
        如果当前状态不支持 escalated，则直接抛出原始异常。
        """
        if cls.is_terminal(current_state):
            return True  # 终态上错误已发生，返回 True 表示已处理
        if cls.can_transition(current_state, "escalated"):
            return cls.transition(current_state, "escalated")
        # 兜底 escalated 不可达时抛出原始异常，让调用方处理
        raise error
