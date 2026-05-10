"""Tests for AsyncDeliveryWatcher."""

import threading
import time
from pathlib import Path

import pytest

from framework.core.mesh.delivery_watcher import AsyncDeliveryWatcher, DeliveryExpectation


@pytest.fixture
def watcher(tmp_path):
    w = AsyncDeliveryWatcher(mesh_dir=str(tmp_path / "mesh"))
    yield w
    w.stop()


class TestExpectAndNotify:
    """注册期望 + Event Bus 通知路径"""

    def test_expect_and_notify(self, watcher, tmp_path):
        delivered = []

        def on_delivered(task_id, file_path):
            delivered.append((task_id, file_path))

        watcher.expect_delivery(
            task_id="t1",
            from_agent="weaver",
            expected_pattern="result_*.json",
            delivery_dir=str(tmp_path / "delivery"),
            timeout=60,
            on_delivered=on_delivered,
        )
        watcher.notify_delivered("t1", "/some/path/result_42.json")

        assert delivered == [("t1", "/some/path/result_42.json")]
        # 已通知的期望应被清理
        assert "t1" not in watcher._expectations

    def test_notify_unknown_task_is_noop(self, watcher):
        # 不应抛异常
        watcher.notify_delivered("unknown_task", "/x.json")


class TestTimeout:
    """超时分支"""

    def test_timeout_fast(self, watcher, tmp_path):
        timed_out = []
        delivered = []

        def on_timeout(task_id):
            timed_out.append(task_id)

        def on_delivered(task_id, file_path):
            delivered.append(task_id)

        watcher.expect_delivery(
            task_id="t_timeout",
            from_agent="weaver",
            expected_pattern="never_*.json",
            delivery_dir=str(tmp_path / "delivery"),
            timeout=1,
            on_delivered=on_delivered,
            on_timeout=on_timeout,
        )
        time.sleep(1.5)

        assert timed_out == ["t_timeout"]
        assert delivered == []


class TestCancel:
    """取消期望分支"""

    def test_cancel_prevents_callbacks(self, watcher, tmp_path):
        delivered = []
        timed_out = []

        watcher.expect_delivery(
            task_id="t_cancel",
            from_agent="weaver",
            expected_pattern="x_*.json",
            delivery_dir=str(tmp_path / "d"),
            timeout=1,
            on_delivered=lambda tid, fp: delivered.append(tid),
            on_timeout=lambda tid: timed_out.append(tid),
        )
        watcher.cancel_expectation("t_cancel")
        time.sleep(1.5)

        assert delivered == []
        assert timed_out == []
        assert "t_cancel" not in watcher._expectations

    def test_cancel_unknown_is_noop(self, watcher):
        watcher.cancel_expectation("never_registered")


class TestFilesystemFallback:
    """文件系统兜底路径"""

    def test_filesystem_check_detects_match(self, watcher, tmp_path):
        delivery_dir = tmp_path / "delivery"
        delivery_dir.mkdir()

        delivered = []
        watcher.expect_delivery(
            task_id="t_fs",
            from_agent="weaver",
            expected_pattern="report_*.md",
            delivery_dir=str(delivery_dir),
            timeout=60,
            on_delivered=lambda tid, fp: delivered.append((tid, fp)),
        )
        # 写入匹配文件
        (delivery_dir / "report_v1.md").write_text("done")
        # 直接调用兜底检查
        watcher._check_filesystem()

        assert len(delivered) == 1
        assert delivered[0][0] == "t_fs"
        assert delivered[0][1].endswith("report_v1.md")

    def test_filesystem_check_skips_non_matching(self, watcher, tmp_path):
        delivery_dir = tmp_path / "delivery"
        delivery_dir.mkdir()

        delivered = []
        watcher.expect_delivery(
            task_id="t_no_match",
            from_agent="weaver",
            expected_pattern="report_*.md",
            delivery_dir=str(delivery_dir),
            timeout=60,
            on_delivered=lambda tid, fp: delivered.append(tid),
        )
        # 写入不匹配文件
        (delivery_dir / "other.txt").write_text("nope")
        watcher._check_filesystem()

        assert delivered == []
        assert "t_no_match" in watcher._expectations


class TestStop:
    """stop() 应取消所有未决计时器"""

    def test_stop_cancels_pending_timers(self, tmp_path):
        w = AsyncDeliveryWatcher(mesh_dir=str(tmp_path / "mesh"))
        timed_out = []
        w.expect_delivery(
            task_id="long",
            from_agent="weaver",
            expected_pattern="z_*.json",
            delivery_dir=str(tmp_path / "d"),
            timeout=2,
            on_timeout=lambda tid: timed_out.append(tid),
        )
        w.stop()
        time.sleep(2.5)

        # 取消后即使过了 timeout 也不应触发
        assert timed_out == []
