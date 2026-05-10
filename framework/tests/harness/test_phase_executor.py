"""PhaseExecutor 基类测试。

TDD 驱动：先写测试再实现。
"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import tempfile

from framework.core.harness.phase_executor import PhaseExecutor
from framework.core.harness.pipeline import ZooPipeline
from framework.core.mesh.zoo_mesh import ZooMesh


class ConcreteExecutor(PhaseExecutor):
    """测试用的具体执行器。"""

    def execute(self) -> bool:
        return True


class TestPhaseExecutor:
    """PhaseExecutor 基类测试套件。"""

    def setup_method(self):
        """每个测试前的准备。"""
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_task_001", agent_id="test_agent")

    def test_phase_executor_is_abstract(self):
        """PhaseExecutor 不能直接实例化，必须子类化。"""
        with pytest.raises(TypeError):
            PhaseExecutor(self.pipeline, "test_phase", self.zoo_mesh)

    def test_concrete_executor_can_be_instantiated(self):
        """具体执行器可以被实例化。"""
        executor = ConcreteExecutor(self.pipeline, "test_phase", self.zoo_mesh)
        assert executor.pipeline is self.pipeline
        assert executor.phase_name == "test_phase"
        assert executor.zoo_mesh is self.zoo_mesh

    def test_validate_delivery_with_valid_delivery(self):
        """验证五件套齐全的有效交付。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "test_task_001",
            "from": "alpha",
            "to": "weaver",
            "body": "test content",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is True

    def test_validate_delivery_missing_task_id(self):
        """缺少 task_id 应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "from": "alpha",
            "to": "weaver",
            "body": "test content",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is False

    def test_validate_delivery_missing_from(self):
        """缺少 from 应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "test_task_001",
            "to": "weaver",
            "body": "test content",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is False

    def test_validate_delivery_missing_to(self):
        """缺少 to 应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "test_task_001",
            "from": "alpha",
            "body": "test content",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is False

    def test_validate_delivery_missing_body(self):
        """缺少 body 应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "test_task_001",
            "from": "alpha",
            "to": "weaver",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is False

    def test_validate_delivery_missing_timestamp(self):
        """缺少 timestamp 应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "test_task_001",
            "from": "alpha",
            "to": "weaver",
            "body": "test content",
        }
        assert executor.validate_delivery(delivery) is False

    def test_validate_delivery_with_empty_values(self):
        """空字符串值应验证失败。"""
        executor = ConcreteExecutor(self.pipeline, "validate", self.zoo_mesh)
        delivery = {
            "task_id": "",
            "from": "alpha",
            "to": "weaver",
            "body": "test content",
            "timestamp": "2026-05-10T10:00:00+00:00",
        }
        assert executor.validate_delivery(delivery) is False

    def test_rollback_records_rollback_in_zoo_mesh(self):
        """rollback 方法应在 zoo_mesh 中记录回退。"""
        executor = ConcreteExecutor(self.pipeline, "design", self.zoo_mesh)
        self.zoo_mesh.init_task(self.pipeline.task_id)

        result = executor.rollback("design", "validate")

        assert result in ["retry", "escalate"]
        counts = self.zoo_mesh.get_rollback_counts(self.pipeline.task_id)
        assert counts["design"] == 1

    def test_rollback_exceeds_threshold_returns_escalate(self):
        """超过回退阈值应返回 escalate。"""
        executor = ConcreteExecutor(self.pipeline, "design", self.zoo_mesh)
        self.zoo_mesh.init_task(self.pipeline.task_id)

        # design 阶段 MAX_RETRIES = 2，回退3次应返回 escalate
        executor.rollback("design", "validate")
        executor.rollback("design", "validate")
        result = executor.rollback("design", "validate")

        assert result == "escalate"

    def test_escalate_sets_state_to_escalated(self):
        """escalate 方法应将 pipeline 状态设置为 escalated。"""
        executor = ConcreteExecutor(self.pipeline, "design", self.zoo_mesh)
        self.zoo_mesh.init_task(self.pipeline.task_id)

        executor.escalate()

        assert self.pipeline.current_state == "escalated"

    def test_escalate_publishes_event(self):
        """escalate 方法应发布事件到事件总线。"""
        executor = ConcreteExecutor(self.pipeline, "design", self.zoo_mesh)
        self.zoo_mesh.init_task(self.pipeline.task_id)

        executor.escalate()

        events = self.zoo_mesh.read_events()
        assert len(events) >= 1
        escalation_events = [e for e in events if e.get("type") == "phase_escalated"]
        assert len(escalation_events) >= 1
        assert escalation_events[0]["payload"]["phase"] == "design"
        assert escalation_events[0]["payload"]["task_id"] == self.pipeline.task_id
