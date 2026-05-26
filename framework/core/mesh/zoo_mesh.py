"""P2P 网格总线。

整合 LockedJsonlWriter、ZooRegistry、AgentSession，
提供事件总线、消息投递、任务状态管理等功能。
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .agent_session import AgentSession
from .locked_jsonl import LockedJsonlWriter
from .zoo_registry import ZooRegistry


# 状态机回退阈值（对应文档 §2.7 / §2.12）
_MAX_RETRIES = {
    "review": 3,
    "audit": 3,
    "develop": 2,
    "design": 2,
}

_VALID_STATUSES = {"online", "idle", "sleeping", "dead", "terminated"}


class ZooMesh:
    """P2P 网格总线 —— 单例。

    提供：
    - 事件总线（基于 LockedJsonlWriter）
    - Agent 消息收发（基于 AgentSession）
    - 任务回退计数器
    - Agent 生命周期状态
    - Pipeline 状态持久化
    """

    _instance: Optional["ZooMesh"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ZooMesh":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> "ZooMesh":
        """重置单例实例（测试用）。"""
        cls._instance = None
        return cls()

    def init(self, base_dir: str) -> None:
        """初始化网格目录结构。"""
        self.base_dir = Path(base_dir)
        self.inbound_dir = self.base_dir / "inbound"
        self.events_dir = self.base_dir / "events"
        self.sessions_dir = self.base_dir / "sessions"
        self.pipeline_dir = self.base_dir / "pipeline"

        for d in (self.inbound_dir, self.events_dir, self.sessions_dir, self.pipeline_dir):
            d.mkdir(parents=True, exist_ok=True)

        self._event_writer = LockedJsonlWriter(str(self.events_dir / "events.jsonl"))
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._registry = ZooRegistry()  # 自动从 YAML 加载
        self._initialized = True

    # ---- Event Bus ----

    def publish_event(self, event_type: str, payload: dict) -> None:
        """发布事件到事件总线。"""
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": _now_iso(),
        }
        self._event_writer.append(event)

        # 触发订阅者（后台线程，避免阻塞写入）
        handlers = self._subscriptions.get(event_type, [])
        for handler in handlers:
            threading.Thread(target=handler, args=(event,), daemon=True).start()

    def read_events(self) -> List[dict]:
        """读取所有事件。"""
        return self._event_writer.read_all()

    def subscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        """订阅事件类型。"""
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        if handler not in self._subscriptions[event_type]:
            self._subscriptions[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        """取消订阅事件类型。"""
        if event_type in self._subscriptions:
            try:
                self._subscriptions[event_type].remove(handler)
            except ValueError:
                pass

    # ---- Agent 消息 ----

    def get_session(self, agent_id: str) -> AgentSession:
        """获取/创建 Agent 的收件箱会话。"""
        inbox_dir = self.inbound_dir / agent_id
        inbox_dir.mkdir(parents=True, exist_ok=True)
        return AgentSession(agent_id, str(inbox_dir))

    def send(self, agent_id: str, from_agent: str, body: str) -> str:
        """向指定 Agent 发送消息。"""
        session = self.get_session(agent_id)
        return session.send(from_agent, body)

    # ---- 任务回退计数器（§2.7 / §2.12） ----

    def init_task(self, task_id: str) -> None:
        """初始化任务的回退计数器。"""
        task_file = self.pipeline_dir / f"task_{task_id}.json"
        data = {
            "retry_count": {
                "request": 0, "validate": 0, "design": 0,
                "review": 0, "develop": 0, "audit": 0,
                "final_check": 0, "deliver": 0,
            },
            "total_rollback_count": 0,
        }
        _atomic_write_json(task_file, data)

    def _load_task(self, task_id: str) -> Optional[dict]:
        task_file = self.pipeline_dir / f"task_{task_id}.json"
        if not task_file.exists():
            return None
        with open(task_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_task(self, task_id: str, data: dict) -> None:
        task_file = self.pipeline_dir / f"task_{task_id}.json"
        _atomic_write_json(task_file, data)

    def get_rollback_counts(self, task_id: str) -> Dict[str, int]:
        """获取任务各阶段的回退次数。"""
        data = self._load_task(task_id)
        if data is None:
            return {}
        return dict(data.get("retry_count", {}))

    def record_rollback(self, task_id: str, from_phase: str, to_phase: str) -> str:
        """记录一次回退，返回建议动作（"retry" 或 "escalate"）。

        - from_phase 的 retry_count 递增
        - to_phase 的 retry_count 重置为 0
        - total_rollback_count 全局递增
        """
        data = self._load_task(task_id)
        if data is None:
            self.init_task(task_id)
            data = self._load_task(task_id)

        retry_count = data.setdefault("retry_count", {})
        retry_count[from_phase] = retry_count.get(from_phase, 0) + 1
        retry_count[to_phase] = 0  # 重置目标阶段

        total = data.get("total_rollback_count", 0) + 1
        data["total_rollback_count"] = total

        # 全局保护：总回退超过 10 次，强制 escalate
        if total > 10:
            self._save_task(task_id, data)
            return "escalate"

        # 阶段级保护
        max_r = _MAX_RETRIES.get(from_phase, 3)
        if retry_count[from_phase] > max_r:
            self._save_task(task_id, data)
            return "escalate"

        self._save_task(task_id, data)
        return "retry"

    # ---- Agent 生命周期状态 ----

    def set_agent_status(self, agent_id: str, status: str) -> None:
        """设置 Agent 生命周期状态。"""
        self._registry.set_status(agent_id, status)

    def get_agent_status(self, agent_id: str) -> str:
        """获取 Agent 生命周期状态（未注册返回 online）。"""
        status = self._registry.get_status(agent_id)
        return status if status is not None else "online"

    # ---- Pipeline 状态 ----

    def set_pipeline_state(self, task_id: str, state: str) -> None:
        """设置 Pipeline 状态。"""
        state_file = self.pipeline_dir / f"state_{task_id}.json"
        _atomic_write_json(state_file, {"state": state, "updated_at": _now_iso()})

    def get_pipeline_state(self, task_id: str) -> Optional[str]:
        """获取 Pipeline 状态。"""
        state_file = self.pipeline_dir / f"state_{task_id}.json"
        if not state_file.exists():
            return None
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f).get("state")


# ---- 工具函数 ----

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件。"""
    temp = path.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.rename(str(temp), str(path))
