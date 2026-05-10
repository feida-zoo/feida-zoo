"""PhaseExecutor ABC 基类。

所有阶段执行器的基类，定义了统一的接口。

设计约束来自 §2.1：
- 五件套检查：task_id, from, to, body, timestamp
- 回退计数保护
- 升级机制
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from framework.core.harness.pipeline import ZooPipeline
from framework.core.mesh.zoo_mesh import ZooMesh


class PhaseExecutor(ABC):
    """阶段执行器抽象基类。

    所有具体的阶段执行器都必须继承此类并实现 execute() 方法。
    """

    # 五件套字段名（来自 §2.1）
    REQUIRED_FIELDS = ["task_id", "from", "to", "body", "timestamp"]

    def __init__(
        self,
        pipeline: ZooPipeline,
        phase_name: str,
        zoo_mesh: Optional[ZooMesh] = None,
    ):
        """
        初始化阶段执行器。

        Args:
            pipeline: 所属的 Pipeline 实例
            phase_name: 阶段名称
            zoo_mesh: ZooMesh 总线实例（可选，为空则使用单例）
        """
        self.pipeline = pipeline
        self.phase_name = phase_name
        self.zoo_mesh = zoo_mesh if zoo_mesh is not None else ZooMesh()

    @abstractmethod
    def execute(self) -> bool:
        """
        执行该阶段的具体逻辑。

        Returns:
            True 表示执行成功，False 表示执行失败需要回退
        """
        pass

    def validate_delivery(self, delivery: Dict[str, Any]) -> bool:
        """
        验证交付物是否包含完整的五件套。

        设计约束来自 §2.1：必须包含 task_id, from, to, body, timestamp

        Args:
            delivery: 待验证的交付物字典

        Returns:
            True 表示验证通过，False 表示验证失败
        """
        if not isinstance(delivery, dict):
            return False

        for field in self.REQUIRED_FIELDS:
            if field not in delivery:
                return False
            value = delivery[field]
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return False

        return True

    def rollback(self, from_phase: str, to_phase: str) -> str:
        """
        记录一次回退，并返回建议动作。

        Args:
            from_phase: 回退的源阶段
            to_phase: 回退的目标阶段

        Returns:
            "retry": 可继续重试
            "escalate": 超过阈值，需要 Panda/园长介入
        """
        return self.zoo_mesh.record_rollback(
            self.pipeline.task_id,
            from_phase,
            to_phase,
        )

    def escalate(self) -> None:
        """
        升级处理：将任务标记为 escalated 状态。

        当回退次数超过阈值时调用此方法。
        """
        # 设置 Pipeline 状态为 escalated
        if hasattr(self.pipeline, "_current_state"):
            self.pipeline._current_state = "escalated"

        # 发布升级事件到事件总线
        self.zoo_mesh.publish_event(
            "phase_escalated",
            {
                "task_id": self.pipeline.task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
                "reason": "rollback_threshold_exceeded",
            },
        )
