"""Tests for ZooMesh."""

import json
import os
import tempfile
import threading
import time

import pytest

from framework.core.mesh.zoo_mesh import ZooMesh


class TestZooMeshBasic:
    """Test basic ZooMesh operations."""

    def test_singleton(self):
        m1 = ZooMesh()
        m2 = ZooMesh()
        assert m1 is m2

    def test_init_creates_directories(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        assert (tmp_path / "inbound").is_dir()
        assert (tmp_path / "events").is_dir()
        assert (tmp_path / "sessions").is_dir()
        assert (tmp_path / "pipeline").is_dir()

    def test_get_session_creates_inbox(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        session = mesh.get_session("weaver")
        assert session is not None
        assert session.agent_id == "weaver"
        assert (tmp_path / "inbound" / "weaver" / "queue").is_dir()


class TestZooMeshEventBus:
    """Test Event Bus functionality."""

    def test_publish_event(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.publish_event("task_created", {"task_id": "t1"})
        events = mesh.read_events()

        # Events file may contain other events from previous tests, filter
        task_events = [e for e in events if e.get("type") == "task_created"]
        assert len(task_events) >= 1
        assert task_events[-1]["payload"]["task_id"] == "t1"

    def test_publish_multiple_events(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        for i in range(5):
            mesh.publish_event("heartbeat", {"seq": i})

        events = mesh.read_events()
        heartbeats = [e for e in events if e.get("type") == "heartbeat"]
        assert len(heartbeats) >= 5

    def test_event_timestamp(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.publish_event("test", {})
        events = mesh.read_events()
        test_events = [e for e in events if e.get("type") == "test"]
        assert "timestamp" in test_events[-1]


class TestZooMeshSubscribe:
    """Test event subscription."""

    def test_subscribe_and_notify(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        received = []

        def handler(event):
            received.append(event)

        mesh.subscribe("test_event", handler)
        mesh.publish_event("test_event", {"data": "hello"})

        # Give background thread time to process
        time.sleep(0.2)
        assert len(received) >= 1
        assert received[-1]["type"] == "test_event"

    def test_multiple_subscribers(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        received1 = []
        received2 = []

        mesh.subscribe("multi", lambda e: received1.append(e))
        mesh.subscribe("multi", lambda e: received2.append(e))

        mesh.publish_event("multi", {"x": 1})
        time.sleep(0.2)

        assert len(received1) >= 1
        assert len(received2) >= 1

    def test_unsubscribe(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        received = []
        handler = lambda e: received.append(e)

        mesh.subscribe("temp", handler)
        mesh.unsubscribe("temp", handler)
        mesh.publish_event("temp", {})

        time.sleep(0.2)
        # Should not receive after unsubscribe
        temp_events = [e for e in received if e.get("type") == "temp"]
        assert len(temp_events) == 0


class TestZooMeshSendReceive:
    """Test send/receive via mesh."""

    def test_send_creates_message(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.send("weaver", "alpha", "hello")
        session = mesh.get_session("weaver")
        msg = session.receive()

        assert msg is not None
        assert msg["from"] == "alpha"
        assert msg["body"] == "hello"

    def test_send_nonexistent_agent(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        # Should create inbox for any agent on demand
        mesh.send("nobody", "alpha", "hello")
        session = mesh.get_session("nobody")
        msg = session.receive()
        assert msg is not None


class TestZooMeshRollbackCounter:
    """Test task rollback counting."""

    def test_initial_rollback_counts(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.init_task("task-1")
        counts = mesh.get_rollback_counts("task-1")
        assert all(v == 0 for v in counts.values())

    def test_record_rollback(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.init_task("task-1")
        result = mesh.record_rollback("task-1", "review", "design")
        assert result == "retry"

        counts = mesh.get_rollback_counts("task-1")
        assert counts["review"] == 1

    def test_rollback_exceeds_max(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.init_task("task-1")
        for _ in range(3):
            result = mesh.record_rollback("task-1", "review", "design")
            assert result == "retry"

        result = mesh.record_rollback("task-1", "review", "design")
        assert result == "escalate"

    def test_global_rollback_limit(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.init_task("task-2")
        for i in range(11):
            mesh.record_rollback("task-2", "review", "design")

        result = mesh.record_rollback("task-2", "review", "design")
        assert result == "escalate"

    def test_rollback_resets_target_phase(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.init_task("task-3")
        # First rollback: review -> design
        mesh.record_rollback("task-3", "review", "design")
        # Now design has some work, then review again
        mesh.record_rollback("task-3", "review", "design")
        # design count should be reset to 0 after rollback
        counts = mesh.get_rollback_counts("task-3")
        assert counts["design"] == 0


class TestZooMeshAgentStatus:
    """Test agent status management."""

    def test_set_agent_status(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.set_agent_status("weaver", "online")
        assert mesh.get_agent_status("weaver") == "online"

    def test_default_status(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        # Unregistered agent returns default
        assert mesh.get_agent_status("unknown") == "online"

    def test_status_persistence(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.set_agent_status("weaver", "idle")
        # Get fresh reference
        assert mesh.get_agent_status("weaver") == "idle"


class TestZooMeshPipelineState:
    """Test pipeline state persistence."""

    def test_set_pipeline_state(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        mesh.set_pipeline_state("task-1", "validate")
        assert mesh.get_pipeline_state("task-1") == "validate"

    def test_pipeline_state_nonexistent(self, tmp_path):
        mesh = ZooMesh._reset_instance()
        mesh.init(str(tmp_path))

        assert mesh.get_pipeline_state("nonexistent") is None
