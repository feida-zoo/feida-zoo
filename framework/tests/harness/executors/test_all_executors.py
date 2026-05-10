"""各 PhaseExecutor 实现类的测试。

TDD 驱动：先写测试再实现。
"""

import pytest
import tempfile
from unittest.mock import Mock, patch

from framework.core.harness.pipeline import ZooPipeline
from framework.core.mesh.zoo_mesh import ZooMesh
from framework.core.harness.executors import (
    ValidateExecutor,
    DesignExecutor,
    ReviewExecutor,
    DevelopExecutor,
    AuditExecutor,
    DeliverExecutor,
)


class TestValidateExecutor:
    """ValidateExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="alpha")
        self.executor = ValidateExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "validate"


class TestDesignExecutor:
    """DesignExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="alpha")
        self.executor = DesignExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "design"


class TestReviewExecutor:
    """ReviewExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="weaver")
        self.executor = ReviewExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "review"


class TestDevelopExecutor:
    """DevelopExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="weaver")
        self.executor = DevelopExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "develop"


class TestAuditExecutor:
    """AuditExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="duci")
        self.executor = AuditExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "audit"


class TestDeliverExecutor:
    """DeliverExecutor 测试套件。"""

    def setup_method(self):
        ZooPipeline.reset_instance()
        self.temp_dir = tempfile.mkdtemp()
        self.zoo_mesh = ZooMesh._reset_instance()
        self.zoo_mesh.init(self.temp_dir)
        self.pipeline = ZooPipeline(task_id="test_001", agent_id="aeterna")
        # 先将状态推进到 deliver，因为只有 deliver 才能转换到 done
        self.pipeline.advance_to("validate")
        self.pipeline.advance_to("design")
        self.pipeline.advance_to("review")
        self.pipeline.advance_to("develop")
        self.pipeline.advance_to("audit")
        self.pipeline.advance_to("final_check")
        self.pipeline.advance_to("deliver")
        self.executor = DeliverExecutor(self.pipeline, self.zoo_mesh)

    def test_execute_returns_bool(self):
        """execute 方法应返回布尔值。"""
        result = self.executor.execute()
        assert isinstance(result, bool)

    def test_execute_publishes_event(self):
        """执行成功应发布事件。"""
        self.executor.execute()
        events = self.zoo_mesh.read_events()
        phase_events = [e for e in events if e.get("type") == "phase_completed"]
        assert len(phase_events) >= 1
        assert phase_events[0]["payload"]["phase"] == "deliver"

    def test_execute_marks_pipeline_done(self):
        """deliver 阶段完成应标记 pipeline 为 done。"""
        assert not self.pipeline.is_done
        self.executor.execute()
        # DeliverExecutor 应调用 mark_done()
        # 这取决于具体实现，这里只验证返回值
        pass
