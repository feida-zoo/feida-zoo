"""
交付等待器
双重检测机制：Event Bus 事件（主）+ 文件系统 inotify（兜底）
设计来源：alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md §2.2
"""
import logging
import os
import time
import threading
from pathlib import Path
from threading import Timer
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class DeliveryExpectation:
    """一次交付期望"""
    def __init__(
        self,
        task_id: str,
        from_agent: str,
        expected_pattern: str,
        delivery_dir: str,
        timeout: int = 3600,
        on_delivered: Optional[Callable] = None,
        on_timeout: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.task_id = task_id
        self.from_agent = from_agent
        self.expected_pattern = expected_pattern
        self.delivery_dir = delivery_dir
        self.timeout = timeout
        self.on_delivered = on_delivered
        self.on_timeout = on_timeout or self._default_timeout_handler
        self.on_error = on_error or self._default_error_handler
        self._timer: Optional[Timer] = None

    def start(self) -> None:
        """启动超时计时器"""
        self._timer = Timer(self.timeout, self._on_timeout_wrapper)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self) -> None:
        if self._timer:
            self._timer.cancel()

    def _on_timeout_wrapper(self) -> None:
        logger.warning(f"交付超时: task_id={self.task_id}")
        self.on_timeout(self.task_id)

    @staticmethod
    def _default_timeout_handler(task_id: str) -> None:
        logger.error(f"交付超时未处理: {task_id}")

    @staticmethod
    def _default_error_handler(task_id: str, error: str) -> None:
        logger.error(f"交付错误: task_id={task_id}, error={error}")


class AsyncDeliveryWatcher:
    """
    异步交付等待器

    双重检测：
    1. 主：Event Bus 事件订阅（file_delivered 事件）
    2. 兜底：文件系统轮询（每 2 秒检查 delivery_dir）
    """

    def __init__(self, mesh_dir: str):
        self.mesh_dir = Path(mesh_dir)
        self._expectations: Dict[str, DeliveryExpectation] = {}
        self._running = False
        self._lock = threading.Lock()

    def expect_delivery(
        self,
        task_id: str,
        from_agent: str,
        expected_pattern: str,
        delivery_dir: str,
        timeout: int = 3600,
        on_delivered: Optional[Callable] = None,
        on_timeout: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> None:
        """注册一个交付期望"""
        exp = DeliveryExpectation(
            task_id=task_id,
            from_agent=from_agent,
            expected_pattern=expected_pattern,
            delivery_dir=delivery_dir,
            timeout=timeout,
            on_delivered=on_delivered,
            on_timeout=on_timeout,
            on_error=on_error,
        )
        with self._lock:
            self._expectations[task_id] = exp
        exp.start()
        logger.info(f"注册交付期望: task_id={task_id}, from={from_agent}, pattern={expected_pattern}")

    def cancel_expectation(self, task_id: str) -> None:
        """取消一个交付期望"""
        with self._lock:
            if task_id in self._expectations:
                self._expectations[task_id].cancel()
                del self._expectations[task_id]
                logger.info(f"取消交付期望: task_id={task_id}")

    def notify_delivered(self, task_id: str, file_path: str) -> None:
        """Event Bus 调用此方法通知交付完成"""
        with self._lock:
            if task_id not in self._expectations:
                return
            exp = self._expectations[task_id]
            del self._expectations[task_id]
        exp.cancel()
        if exp.on_delivered:
            exp.on_delivered(task_id, file_path)
        logger.info(f"交付完成: task_id={task_id}, file={file_path}")

    def start_filesystem_watch(self) -> None:
        """启动文件系统兜底检测（轮询模式）"""
        self._running = True
        logger.info("AsyncDeliveryWatcher 文件系统兜底检测已启动")

        while self._running:
            self._check_filesystem()
            time.sleep(2)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        # 取消所有未完成期望的计时器，避免守护线程在解释器退出后仍触发
        for task_id in list(self._expectations.keys()):
            self._expectations[task_id].cancel()

    def _check_filesystem(self) -> None:
        """检查所有期望的交付目录"""
        import fnmatch

        with self._lock:
            expectations = list(self._expectations.items())

        for task_id, exp in expectations:
            try:
                delivery_path = Path(exp.delivery_dir)
                if not delivery_path.exists():
                    continue

                files = list(delivery_path.iterdir())
                for f in files:
                    if fnmatch.fnmatch(f.name, exp.expected_pattern):
                        self.notify_delivered(task_id, str(f))
                        break
            except Exception as e:
                logger.warning(f"检查文件系统交付失败: task_id={task_id}, error={e}")
                with self._lock:
                    if task_id in self._expectations:
                        self._expectations[task_id].on_error(task_id, str(e))
