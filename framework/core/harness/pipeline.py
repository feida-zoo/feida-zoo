"""
ZooPipeline 主引擎 —— 飝龘动物园 Harness 核心

设计约束来自 §2.3, §2.7：
- 单例模式
- 内置 StateMachine
- 阶段列表 + 状态转换
- 回退计数保护（MAX_RETRIES_PER_PHASE）
- 错误兜底 → escalated
- 取消（仅园长可调用）
"""

from typing import Optional, Dict, Any
from framework.core.harness.state_machine import StateMachine, InvalidTransition
from framework.core.mesh.zoo_mesh import ZooMesh


class ZooPipelineError(Exception):
    """Pipeline 相关异常基类"""
    pass


class InvalidPhase(ZooPipelineError):
    """非法阶段"""
    pass


class PipelineCancelled(ZooPipelineError):
    """Pipeline 被取消"""
    pass


class ZooPipeline:
    """
    飝龘动物园 Pipeline 主引擎

    单例模式，驱动整个任务生命周期。
    """

    # 阶段执行顺序（不含终态）
    PHASES = [
        "request", "validate", "design", "ui_design", "review",
        "develop", "test", "audit", "final_check", "deliver"
    ]

    # 各阶段最大回退次数（来自 §2.7）
    MAX_RETRIES_PER_PHASE: Dict[str, int] = {
        "ui_design": 2,
        "review":  3,
        "audit":   3,
        "develop": 2,
        "test":    2,
        "design":  2,
    }

    # 全局回退计数上限（超过 → 强制 escalate）
    MAX_TOTAL_ROLLBACKS = 10

    _instance: Optional["ZooPipeline"] = None

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        zoo_mesh: Optional[ZooMesh] = None,
    ):
        """
        初始化 Pipeline 实例。

        Args:
            task_id: 任务唯一标识
            agent_id: 负责的 Agent ID
            zoo_mesh: ZooMesh 总线实例（可选）
        """
        self.task_id = task_id
        self.agent_id = agent_id
        self.zoo_mesh = zoo_mesh

        # 状态机
        self._sm = StateMachine()
        self._current_state = "request"
        self._current_phase = "request"

        # 回退计数
        self._retry_counts: Dict[str, int] = {p: 0 for p in self.PHASES}
        self._total_rollbacks = 0

        # 终态标志
        self._cancelled = False
        self._done = False

    @classmethod
    def get_instance(cls, **kwargs) -> "ZooPipeline":
        """单例获取或创建实例"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None

    @property
    def current_phase(self) -> str:
        """当前阶段"""
        return self._current_phase

    @property
    def current_state(self) -> str:
        """当前状态"""
        return self._current_state

    @property
    def is_done(self) -> bool:
        """是否已完成"""
        return self._done

    @property
    def is_cancelled(self) -> bool:
        """是否已取消"""
        return self._cancelled

    def advance_to(self, next_phase: str) -> bool:
        """
        安全推进到下一阶段。

        使用 StateMachine 进行状态转换验证。
        """
        if self._done or self._cancelled:
            return False

        if next_phase not in self.PHASES:
            raise InvalidPhase(f"未知阶段: {next_phase}")

        # 验证状态转换合法
        StateMachine.transition(self._current_state, next_phase)
        self._current_state = next_phase
        self._current_phase = next_phase
        return True

    def handle_error(self, error: Exception) -> str:
        """
        处理阶段执行中的错误。

        调用 StateMachine.handle_error() 进行错误兜底：
        - 非终态 → escalated
        - 终态 → 返回 True（表示已处理，不改变状态）
        """
        result = StateMachine.handle_error(self._current_state, error)
        if result and self._current_state != "done" and self._current_state != "cancelled":
            self._current_state = "escalated"
        return "escalated" if result and not StateMachine.is_terminal(self._current_state) else "done"

    def rollback(self, phase: str) -> str:
        """
        记录一次回退。

        Returns:
            "retry": 可继续重试
            "escalate": 超过阈值，需要 Panda/园长介入
        """
        if phase not in self._retry_counts:
            return "escalate"

        self._retry_counts[phase] += 1
        self._total_rollbacks += 1

        max_r = self.MAX_RETRIES_PER_PHASE.get(phase, 3)

        # 超过单阶段阈值
        if self._retry_counts[phase] > max_r:
            return "escalate"

        # 超过全局阈值
        if self._total_rollbacks > self.MAX_TOTAL_ROLLBACKS:
            return "escalate"

        return "retry"

    # 授权取消者白名单（仅园长和 Panda）
    AUTHORIZED_CANCELLERS = {"owner", "panda"}

    def cancel(self, requester: str) -> bool:
        """
        取消 Pipeline（仅园长/Panda 可调用）。

        Args:
            requester: 请求取消的操作者 ID

        Returns:
            True if cancelled, False if already done/cancelled
        """
        if self._done or self._cancelled:
            return False

        # P1-3 fix: 验证取消者身份
        if requester not in self.AUTHORIZED_CANCELLERS:
            raise PermissionError(f"取消权限不足: {requester} 不在白名单 {self.AUTHORIZED_CANCELLERS}")

        StateMachine.transition(self._current_state, "cancelled")
        self._current_state = "cancelled"
        self._current_phase = "cancelled"
        self._cancelled = True
        return True

    def mark_done(self) -> bool:
        """标记为完成"""
        if self._cancelled:
            return False
        StateMachine.transition(self._current_state, "done")
        self._current_state = "done"
        self._done = True
        return True

    def get_status(self) -> Dict[str, Any]:
        """获取完整状态快照"""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "current_state": self._current_state,
            "current_phase": self._current_phase,
            "is_done": self._done,
            "is_cancelled": self._cancelled,
            "retry_counts": dict(self._retry_counts),
            "total_rollbacks": self._total_rollbacks,
        }

    def run(self) -> Dict[str, Any]:
        """
        驱动整个 Pipeline 执行。

        按 PHASES 顺序执行各阶段。
        实际阶段执行逻辑由 PhaseExecutor 子类实现。
        """
        if self._done or self._cancelled:
            return self.get_status()

        for phase in self.PHASES:
            if self._done or self._cancelled:
                break
            if phase == self._current_state:
                continue
            # P1-1 fix: 必须通过 advance_to() 进行状态转换校验
            try:
                self.advance_to(phase)
            except InvalidTransition as e:
                # 非法转换 → escalated
                self.handle_error(e)
                break

        if not self._done and not self._cancelled:
            self.mark_done()

        return self.get_status()