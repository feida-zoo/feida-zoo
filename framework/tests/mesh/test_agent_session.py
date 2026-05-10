"""Tests for AgentSession inbox operations."""

import json
import os
import time
import uuid

import pytest

from framework.core.mesh.agent_session import AgentSession, InboxConfig


class TestInboxConfig:
    """Test InboxConfig defaults."""

    def test_default_config(self):
        cfg = InboxConfig()
        assert cfg.max_delivery_attempts == 3
        assert cfg.visibility_timeout == 300
        assert cfg.ttl == 3600

    def test_custom_config(self):
        cfg = InboxConfig(max_delivery_attempts=5, visibility_timeout=60, ttl=1800)
        assert cfg.max_delivery_attempts == 5
        assert cfg.visibility_timeout == 60
        assert cfg.ttl == 1800


class TestAgentSessionSend:
    """Test message sending."""

    def test_send_creates_message_file(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "design the arch")

        queue_dir = inbox_dir / "queue"
        assert queue_dir.exists()
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 1

    def test_send_message_content(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "hello weaver")

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        with open(files[0]) as f:
            msg = json.load(f)

        assert msg["id"] == msg_id
        assert msg["from"] == "alpha"
        assert msg["to"] == "weaver"
        assert msg["body"] == "hello weaver"
        assert "timestamp" in msg
        assert msg["delivery_count"] == 0
        assert "ttl" in msg

    def test_send_returns_uuid(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "test")
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36  # UUID4

    def test_send_multiple_messages(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        ids = [session.send("alpha", f"msg-{i}") for i in range(5)]

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 5
        assert len(set(ids)) == 5

    def test_send_preserves_existing_messages(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        first_id = session.send("alpha", "first")
        second_id = session.send("alpha", "second")

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 2


class TestAgentSessionReceive:
    """Test message receiving."""

    def test_receive_empty_inbox(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg = session.receive()
        assert msg is None

    def test_receive_returns_oldest_message(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))

        # Send two messages with a small time gap
        session.send("alpha", "first")
        time.sleep(0.01)
        session.send("alpha", "second")

        msg = session.receive()
        assert msg is not None
        assert msg["body"] == "first"

    def test_receive_returns_message_dict(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        session.send("alpha", "hello")

        msg = session.receive()
        assert isinstance(msg, dict)
        assert "id" in msg
        assert "from" in msg
        assert "body" in msg
        assert "delivery_count" in msg


class TestAgentSessionAck:
    """Test message acknowledgment."""

    def test_ack_removes_message(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "hello")

        session.ack(msg_id)

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 0

    def test_ack_updates_checkpoint(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "hello")

        session.ack(msg_id)

        checkpoint = inbox_dir / "checkpoint.json"
        assert checkpoint.exists()
        with open(checkpoint) as f:
            cp = json.load(f)
        assert cp["last_id"] == msg_id
        assert "updated_at" in cp

    def test_ack_nonexistent_message(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        session.ack("nonexistent-id")  # should not raise


class TestAgentSessionNack:
    """Test negative acknowledgment."""

    def test_nack_increments_delivery_count(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "hello")

        result = session.nack(msg_id)
        assert result == "retry"

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 1
        with open(files[0]) as f:
            msg = json.load(f)
        assert msg["delivery_count"] == 1

    def test_nack_moves_to_dlq_after_max_retries(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg_id = session.send("alpha", "hello")

        # Default max_delivery_attempts = 3
        # After 3 nacks (delivery_count reaches 3), should move to DLQ
        for _ in range(2):
            result = session.nack(msg_id)
            assert result == "retry"

        result = session.nack(msg_id)
        assert result == "dlq"

        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 0

        dlq_dir = inbox_dir / "dlq"
        dlq_files = list(dlq_dir.glob("msg_*.json"))
        assert len(dlq_files) == 1

    def test_nack_nonexistent_message(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        result = session.nack("nonexistent-id")
        assert result == "not_found"


class TestAgentSessionRecovery:
    """Test restart recovery behavior."""

    def test_recovery_reads_checkpoint(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"

        # Simulate: send messages, ack one
        session1 = AgentSession("weaver", str(inbox_dir))
        msg1 = session1.send("alpha", "first")
        msg2 = session1.send("alpha", "second")
        session1.ack(msg1)

        # New session (restart)
        session2 = AgentSession("weaver", str(inbox_dir))
        cp = session2.get_checkpoint()
        assert cp["last_id"] == msg1

    def test_recovery_filtering(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"

        session1 = AgentSession("weaver", str(inbox_dir))
        msg1 = session1.send("alpha", "first")
        msg2 = session1.send("alpha", "second")
        session1.ack(msg1)

        # After ack(msg1), msg2 should still be in queue
        queue_dir = inbox_dir / "queue"
        files = list(queue_dir.glob("msg_*.json"))
        assert len(files) == 1

    def test_get_unacked_messages(self, tmp_path):
        inbox_dir = tmp_path / "inbound" / "weaver"
        session = AgentSession("weaver", str(inbox_dir))
        msg1 = session.send("alpha", "first")
        msg2 = session.send("alpha", "second")
        session.ack(msg1)

        unacked = session.get_unacked_messages()
        assert len(unacked) == 1
        assert unacked[0]["body"] == "second"
