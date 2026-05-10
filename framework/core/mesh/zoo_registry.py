"""成员注册表和 Session 动态解析器。

设计约束来自文档 §2.5：
- Phase 1-2 使用 sessions_list 动态查询 + 缓存
- Phase 3+ 使用 Label 路由
"""

from typing import Dict, Optional


# 静态 Label 路由表（不依赖 session_key）
_DEFAULT_LABEL_MAP = {
    "alpha":   {"label": "alpha-zoomesh",   "model": "deepseek/deepseek-v4-flash"},
    "weaver":  {"label": "weaver-zoomesh",  "model": "minimax/MiniMax-M2.7"},
    "duci":    {"label": "duci-zoomesh",    "model": "glm-5.1"},
    "aeterna": {"label": "aeterna-zoomesh", "model": "minimax/MiniMax-M2.7"},
    "gulu":    {"label": "gulu-zoomesh",    "model": "minimax/MiniMax-M2.7"},
    "panda":   {"label": "panda-zoomesh",   "model": "minimax/MiniMax-M2.7"},
}

_VALID_STATUSES = {"online", "idle", "sleeping", "dead", "terminated"}


class ZooRegistry:
    """成员注册表 —— agent_id → session_key/label 映射。

    使用单例模式确保全局唯一注册表实例。
    """

    _instance: Optional["ZooRegistry"] = None

    def __new__(cls) -> "ZooRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, dict] = {}
            cls._instance._session_cache: Dict[str, str] = {}
            cls._instance._status: Dict[str, str] = {}
        return cls._instance

    def clear(self) -> None:
        """清空所有注册信息（测试用）。"""
        self._agents.clear()
        self._session_cache.clear()
        self._status.clear()

    def register(self, agent_id: str, label: str, model: Optional[str] = None) -> None:
        """注册一个 Agent。重复注册幂等（覆盖更新）。"""
        self._agents[agent_id] = {"label": label, "model": model}
        if agent_id not in self._status:
            self._status[agent_id] = "online"

    def unregister(self, agent_id: str) -> None:
        """注销一个 Agent。"""
        self._agents.pop(agent_id, None)
        self._session_cache.pop(agent_id, None)
        self._status.pop(agent_id, None)

    def list_agents(self) -> list:
        """列出所有已注册的 agent_id。"""
        return list(self._agents.keys())

    def get_info(self, agent_id: str) -> Optional[dict]:
        """获取 Agent 的注册信息。"""
        return self._agents.get(agent_id)

    def register_defaults(self) -> None:
        """注册默认的动物园成员。"""
        for agent_id, info in _DEFAULT_LABEL_MAP.items():
            self.register(agent_id, info["label"], info["model"])

    def get_label(self, agent_id: str) -> Optional[str]:
        """获取 Agent 的 label。"""
        info = self._agents.get(agent_id)
        return info["label"] if info else None

    def get_model(self, agent_id: str) -> Optional[str]:
        """获取 Agent 的 model。"""
        info = self._agents.get(agent_id)
        return info.get("model") if info else None

    # ---- Session 缓存 ----

    def set_session_cache(self, agent_id: str, session_key: str) -> None:
        """缓存 agent_id 的最新 session_key。"""
        self._session_cache[agent_id] = session_key

    def get_session_cache(self, agent_id: str) -> Optional[str]:
        """获取缓存的 session_key。"""
        return self._session_cache.get(agent_id)

    def clear_cache(self) -> None:
        """清空 session 缓存。"""
        self._session_cache.clear()

    # ---- 生命周期状态 ----

    def set_status(self, agent_id: str, status: str) -> None:
        """设置 Agent 生命周期状态。"""
        self._status[agent_id] = status

    def get_status(self, agent_id: str) -> Optional[str]:
        """获取 Agent 生命周期状态（默认 online）。"""
        return self._status.get(agent_id)


class SessionRouter:
    """分阶段 Session 路由器。

    Phase 1-2：使用 sessions_list 动态查询 + 缓存
    Phase 3+：使用 Label 路由
    """

    def __init__(self, phase: str = "phase1"):
        self.phase = phase
        self._cache: Dict[str, str] = {}

    def connect(self, phase: str) -> None:
        """切换阶段，清空缓存。"""
        self.phase = phase
        self._cache.clear()

    def resolve(self, agent_id: str) -> Optional[str]:
        """解析 agent_id 到可路由标识。

        - phase1/phase2: 返回缓存的 session_key（如存在）
        - phase3+: 返回 label
        """
        if self.phase in ("phase1", "phase2"):
            return self._cache.get(agent_id)

        # phase3+ 使用 Label 路由
        registry = ZooRegistry()
        return registry.get_label(agent_id)
