"""Deliver 阶段执行器。

负责交付阶段：产物归档、文档生成、交付通知。
"""

from typing import Optional

from framework.core.harness.phase_executor import PhaseExecutor
from framework.core.harness.pipeline import ZooPipeline
from framework.core.mesh.zoo_mesh import ZooMesh


class DeliverExecutor(PhaseExecutor):
    """交付阶段执行器。"""

    def __init__(
        self,
        pipeline: ZooPipeline,
        zoo_mesh: Optional[ZooMesh] = None,
    ):
        super().__init__(pipeline, "deliver", zoo_mesh)

    def execute(self) -> bool:
        """
        执行交付阶段。

        工作内容：
        1. 归档所有产出自 shared/ 目录
        2. 生成交付文档和摘要
        3. 通知相关方任务完成

        Returns:
            True 表示交付完成
        """
        # 发布阶段开始事件
        self.zoo_mesh.publish_event(
            "phase_started",
            {
                "task_id": self.pipeline.task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
            },
        )

        # TODO: 实现具体的交付逻辑
        # - 归档所有产出物
        # - 生成交付文档
        # - 通知任务完成

        # 标记 Pipeline 为完成（正常路径）
        self.pipeline.mark_done()

        # 发布阶段完成事件
        self.zoo_mesh.publish_event(
            "phase_completed",
            {
                "task_id": self.pipeline.task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
                "status": "success",
            },
        )

        return True
