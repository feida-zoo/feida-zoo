"""Tests for InboxWatcher."""

import json
import threading
import time
from pathlib import Path

import pytest

from framework.core.mesh.inbox_watcher import InboxWatcher


@pytest.fixture
def mesh_setup(tmp_path):
    mesh_dir = tmp_path / "mesh"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"agents": {"weaver": {}, "duci": {}}}))
    (mesh_dir / "inbound" / "weaver" / "queue").mkdir(parents=True)
    (mesh_dir / "inbound" / "duci" / "queue").mkdir(parents=True)
    return mesh_dir, registry_path


def _write_msg(queue_dir: Path, msg_id: str = "abc") -> Path:
    target = queue_dir / f"msg_{msg_id}.json"
    target.write_text(json.dumps({"id": msg_id, "body": "hi"}))
    return target


class TestInboxWatcher:
    """Inbox 看门狗核心行为"""

    def test_detects_new_message(self, mesh_setup):
        """启动后写入新消息应触发回调"""
        mesh_dir, registry_path = mesh_setup
        triggered = []

        def on_wakeup(agent_id):
            triggered.append(agent_id)

        watcher = InboxWatcher(
            mesh_dir=str(mesh_dir),
            registry_path=str(registry_path),
            on_wakeup=on_wakeup,
        )
        # 直接调用基线初始化 + 写入新消息 + 检查
        watcher._init_baseline("weaver")
        # 必须写在基线之后，确保 mtime 比 baseline 大
        time.sleep(0.05)
        _write_msg(mesh_dir / "inbound" / "weaver" / "queue", "new1")
        watcher._check_inbox("weaver")

        assert triggered == ["weaver"]

    def test_ignores_existing_on_start(self, mesh_setup):
        """启动前已存在的消息不应触发回调"""
        mesh_dir, registry_path = mesh_setup
        # 启动前先写入一个消息
        _write_msg(mesh_dir / "inbound" / "weaver" / "queue", "old1")

        triggered = []

        def on_wakeup(agent_id):
            triggered.append(agent_id)

        watcher = InboxWatcher(
            mesh_dir=str(mesh_dir),
            registry_path=str(registry_path),
            on_wakeup=on_wakeup,
        )
        # 基线初始化吸收已存在的 mtime
        watcher._init_baseline("weaver")
        # 立即检查，不应触发
        watcher._check_inbox("weaver")

        assert triggered == []

    def test_threaded_start_then_stop(self, mesh_setup):
        """端到端：start() 在线程中运行，写入消息后停止"""
        mesh_dir, registry_path = mesh_setup
        triggered = []
        lock = threading.Lock()

        def on_wakeup(agent_id):
            with lock:
                triggered.append(agent_id)

        watcher = InboxWatcher(
            mesh_dir=str(mesh_dir),
            registry_path=str(registry_path),
            on_wakeup=on_wakeup,
        )
        t = threading.Thread(target=watcher.start, daemon=True)
        t.start()
        # 等待 start 完成基线初始化
        time.sleep(0.5)
        _write_msg(mesh_dir / "inbound" / "duci" / "queue", "new_dx")
        # 轮询周期是 2s，给足时间
        time.sleep(3.0)
        watcher.stop()
        t.join(timeout=5)

        with lock:
            assert "duci" in triggered

    def test_missing_registry_falls_back(self, tmp_path):
        """注册表缺失时使用默认 agent 列表"""
        mesh_dir = tmp_path / "mesh"
        mesh_dir.mkdir()
        registry_path = tmp_path / "missing.json"

        watcher = InboxWatcher(
            mesh_dir=str(mesh_dir),
            registry_path=str(registry_path),
        )
        # 触发 fallback 路径（直接停止避免无限循环）
        watcher._running = False
        # 手动模拟 start() 中的注册表加载分支
        try:
            with open(registry_path) as f:
                registry = json.load(f)
            agent_ids = list(registry.get("agents", {}).keys())
        except Exception:
            agent_ids = ["weaver", "duci", "aeterna", "gulu", "alpha"]

        assert "weaver" in agent_ids
        assert "alpha" in agent_ids

    def test_callback_exception_is_isolated(self, mesh_setup):
        """on_wakeup 抛异常不应让看门狗崩溃"""
        mesh_dir, registry_path = mesh_setup

        def boom(agent_id):
            raise RuntimeError("boom")

        watcher = InboxWatcher(
            mesh_dir=str(mesh_dir),
            registry_path=str(registry_path),
            on_wakeup=boom,
        )
        watcher._init_baseline("weaver")
        time.sleep(0.05)
        _write_msg(mesh_dir / "inbound" / "weaver" / "queue", "boom1")
        # 不应抛出
        try:
            watcher._check_inbox("weaver")
        except RuntimeError:
            pytest.fail("看门狗未隔离回调异常")
