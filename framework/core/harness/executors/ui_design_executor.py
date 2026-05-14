"""UiDesign 阶段执行器。

负责 UI/视觉设计阶段：设计稿、视觉规范、交互原型。
"""

from typing import Optional

from framework.core.harness.phase_executor import PhaseExecutor
from framework.core.harness.pipeline import ZooPipeline
from framework.core.mesh.zoo_mesh import ZooMesh


class UiDesignExecutor(PhaseExecutor):
    """UI 设计阶段执行器（Gulu 咕噜）。"""

    def __init__(
        self,
        pipeline: ZooPipeline,
        zoo_mesh: Optional[ZooMesh] = None,
    ):
        super().__init__(pipeline, "ui_design", zoo_mesh)

    def execute(self) -> bool:
        """
        执行 UI 设计阶段。

        工作内容：
        1. 发送设计通知给 Gulu（咕噜）
        2. 生成 UI 视觉稿和交互原型
        3. 定义设计规范和资源

        Returns:
            True 表示 UI 设计完成
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

        # 发送通知给 Gulu 咕噜
        self.zoo_mesh.publish_event(
            "notify_gulu",
            {
                "task_id": self.pipeline.task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
                "message": f"新 UI 设计任务到达，请 Gulu 咕噜处理: {self.pipeline.task_id}",
            },
        )

        # TODO: 实现具体的 UI 设计逻辑
        # - 生成视觉设计稿
        # - 定义色彩/排版/组件规范
        # - 交互原型设计

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
