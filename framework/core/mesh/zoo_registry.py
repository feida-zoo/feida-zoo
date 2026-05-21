"""成员注册表和 Session 动态解析器 — YAML 驱动版本。

从 zoo_members.yaml 加载成员配置，提供 Session 路由、模型展示、阶段映射功能。
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

# 尝试加载 pyyaml
try:
    import yaml as _yaml
except ImportError:
    _yaml = None


# 默认路径
_DEFAULT_YAML_PATH = Path(__file__).parent.parent.parent / "data" / "zoo_members.yaml"
_DEFAULT_OPENCLAW_PATH = Path.home() / ".openclaw" / "openclaw.json"


def _derive_label_from_session_key(session_key: str) -> Optional[str]:
    """从 session.key 推导 label。
    
    格式: agent:<id>:main  →  提取 id  →  <id>-zoomesh
    例: agent:alpha:main  →  alpha-zoomesh
    """
    if not session_key:
        return None
    parts = session_key.split(":")
    if len(parts) >= 2:
        agent_id = parts[1]
        return f"{agent_id}-zoomesh"
    return None


def _load_yaml_safe(path: str) -> dict:
    """加载 YAML 文件，失败抛出异常。"""
    if _yaml is None:
        raise RuntimeError("pyyaml not installed. Run: pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.safe_load(f)


def _load_openclaw_models(openclaw_path: str) -> dict:
    """加载 openclaw.json 的模型配置。不存在时返回空 dict。"""
    path = Path(openclaw_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("agents", {}).get("defaults", {}).get("models", {})
    except (json.JSONDecodeError, Exception):
        return {}


def _load_openclaw_primary_model(openclaw_path: str) -> Optional[str]:
    """加载 openclaw.json 的主 Agent 主用模型 ID。"""
    path = Path(openclaw_path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
    except (json.JSONDecodeError, Exception):
        return None


def _resolve_model_alias(model_id: str, models: dict) -> str:
    """将 model ID 转换为展示用 alias。"""
    if not model_id:
        return "未知"
    model_cfg = models.get(model_id, {})
    if isinstance(model_cfg, dict):
        alias = model_cfg.get("alias", "")
        if alias:
            return alias
    return model_id


# ── ZooRegistry ──────────────────────────────────────────────────────────────────


class ZooRegistry:
    """成员注册表 — 从 zoo_members.yaml + openclaw.json 双源加载。

    构造时自动加载 YAML；register() 在 YAML 模式下仍可调用
    （动态覆盖内存数据），但不会写回文件。

    使用单例模式确保全局唯一注册表实例。
    """

    _instance: Optional["ZooRegistry"] = None

    def __new__(cls, *args, **kwargs) -> "ZooRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, yaml_path: Optional[str] = None,
                 openclaw_path: Optional[str] = None):
        """初始化 ZooRegistry。

        Args:
            yaml_path: zoo_members.yaml 路径，默认 framework/data/zoo_members.yaml
            openclaw_path: openclaw.json 路径，默认 ~/.openclaw/openclaw.json
        """
        resolved_yaml = yaml_path or str(_DEFAULT_YAML_PATH)
        resolved_oc = openclaw_path or str(_DEFAULT_OPENCLAW_PATH)

        if self._initialized:
            # 路径相同 → 跳过（生产环境：首次加载后重复调用不重读）
            if (getattr(self, '_yaml_path', None) == resolved_yaml
                    and getattr(self, '_openclaw_path', None) == resolved_oc):
                return
            # 路径不同 → 清空并重新加载（测试环境：不同测试使用不同临时 YAML）
            self._clear_internal()

        self._yaml_path = resolved_yaml
        self._openclaw_path = resolved_oc

        # 内在存储
        self._agents: Dict[str, dict] = {}        # agent_id → {label, model, ...}
        self._yaml_data: Dict[str, dict] = {}     # agent_id → full YAML data
        self._session_cache: Dict[str, str] = {}
        self._status: Dict[str, str] = {}

        # 加载 openclaw.json（不强制存在）
        self._oc_models = _load_openclaw_models(self._openclaw_path)
        self._oc_primary = _load_openclaw_primary_model(self._openclaw_path)

        # 初始化时从 YAML 加载
        self._load_from_yaml(self._yaml_path)

        self._initialized = True

    def _load_from_yaml(self, yaml_path: str) -> None:
        """从 YAML 文件加载成员配置。"""
        data = _load_yaml_safe(yaml_path)
        members = data.get("members", {})
        for agent_id, info in members.items():
            self._yaml_data[agent_id] = info
            # 基础信息：label + model
            model = info.get("model")
            session = info.get("session", {})
            session_key = session.get("key") if isinstance(session, dict) else None
            label = info.get("label") or _derive_label_from_session_key(session_key)
            self._agents[agent_id] = {"label": label, "model": model}
            if agent_id not in self._status:
                self._status[agent_id] = "online"

    def reload(self) -> None:
        """重新加载 YAML。文件损坏时保留旧数据。"""
        try:
            data = _load_yaml_safe(self._yaml_path)
            members = data.get("members", {})
            # 不覆盖 _status（进程检活信息）
            existing_status = dict(self._status)
            self._agents.clear()
            self._yaml_data.clear()
            for agent_id, info in members.items():
                self._yaml_data[agent_id] = info
                model = info.get("model")
                session = info.get("session", {})
                session_key = session.get("key") if isinstance(session, dict) else None
                label = info.get("label") or _derive_label_from_session_key(session_key)
                self._agents[agent_id] = {"label": label, "model": model}
            # 恢复之前的在线状态（如果 agent 还在）
            for agent_id, s in existing_status.items():
                if agent_id in self._agents:
                    self._status[agent_id] = s
        except Exception as e:
            import logging
            logging.getLogger("zoo_registry").error(f"reload() 失败 (保留旧数据): {e}")

    def _clear_internal(self) -> None:
        """清空全部内部数据但不修改 _initialized 状态。"""
        self._agents.clear()
        self._yaml_data.clear()
        self._session_cache.clear()
        self._status.clear()
        self._oc_models = {}
        self._oc_primary = None

    def clear(self) -> None:
        """清空所有注册信息并重置初始化状态（测试用）。"""
        self._clear_internal()
        self._initialized = False

    @classmethod
    def _reset_instance(cls) -> None:
        """重置单例实例（测试用）。"""
        if cls._instance is not None:
            cls._instance._clear_internal()
            cls._instance = None

    # ── 向下兼容接口 ──

    def register(self, agent_id: str, label: str, model: Optional[str] = None) -> None:
        """注册一个 Agent。重复注册幂等（覆盖更新）。
        
        YAML 模式下仍可动态注册（临时覆盖内存数据），不会写回文件。
        """
        self._agents[agent_id] = {"label": label, "model": model}
        if agent_id not in self._status:
            self._status[agent_id] = "online"

    def unregister(self, agent_id: str) -> None:
        """注销一个 Agent。"""
        self._agents.pop(agent_id, None)
        self._yaml_data.pop(agent_id, None)
        self._session_cache.pop(agent_id, None)
        self._status.pop(agent_id, None)

    def list_agents(self) -> list:
        """列出所有已注册的 agent_id。"""
        return list(self._agents.keys())

    def get_info(self, agent_id: str) -> Optional[dict]:
        """获取 Agent 的注册信息（向下兼容，返回 {label, model}）。"""
        return self._agents.get(agent_id)

    def register_defaults(self) -> None:
        """注册默认的动物园成员。

        在 YAML 模式下，此方法委托给 reload()。
        """
        self.reload()

    def get_label(self, agent_id: str) -> Optional[str]:
        """获取 Agent 的 label。
        
        规则: session.key = agent:<id>:main  →  label = <id>-zoomesh
        如果 YAML 中有独立的 label 字段，优先使用。
        """
        info = self._agents.get(agent_id)
        if info is None:
            return None
        label = info.get("label")
        if label:
            return label
        # Fallback: 尝试从 full YAML 数据的 session.key 推导
        full = self._yaml_data.get(agent_id)
        if full:
            session = full.get("session", {})
            if isinstance(session, dict):
                return _derive_label_from_session_key(session.get("key"))
        return None

    def get_model(self, agent_id: str) -> Optional[str]:
        """获取 Agent 的 model。"""
        info = self._agents.get(agent_id)
        if info is None:
            return None
        return info.get("model")

    # ── 新增方法 ──

    def get_full_info(self, agent_id: str) -> Optional[dict]:
        """返回 YAML 中该成员的全部字段。"""
        info = self._yaml_data.get(agent_id)
        if info is None:
            return None
        return dict(info)

    def get_responsible_phases(self, agent_id: str) -> list:
        """获取成员负责的阶段列表。"""
        info = self._yaml_data.get(agent_id)
        if info is None:
            return []
        return list(info.get("responsible_phases", []))

    def get_phase_agent(self, phase: str) -> str:
        """根据阶段名反向查询负责的 Agent。
        
        冲突规则（多人负责同阶段）：
        1. 排除 is_main_agent==True 的主 Agent
        2. 按 YAML 定义顺序返回第一个
        3. 若无匹配 → 返回 'panda'（全局 fallback）
        """
        # 遍历所有 YAML 成员，收集负责此阶段且非主 Agent 的
        candidates = []
        for agent_id, info in self._yaml_data.items():
            phases = info.get("responsible_phases", [])
            if phase in phases:
                meta = info.get("metadata", {})
                is_main = meta.get("is_main_agent", False) if isinstance(meta, dict) else False
                if not is_main:
                    candidates.append(agent_id)
        if candidates:
            return candidates[0]
        # Fallback: 主 Agent（panda）也匹配
        for agent_id, info in self._yaml_data.items():
            phases = info.get("responsible_phases", [])
            if phase in phases:
                return agent_id
        # 全局 fallback
        return "panda"

    def get_model_display(self, agent_id: str) -> Optional[str]:
        """Dashboard 展示用模型名。

        - 非主 Agent: YAML 的 model 字段 → 查 openclaw.json 转 alias
        - 主 Agent (is_main_agent==true): openclaw.json defaults.model.primary → alias
        - openclaw.json 不可读 → 返回原始 model ID
        """
        full = self._yaml_data.get(agent_id)
        if full is None:
            return None

        meta = full.get("metadata", {})
        is_main = meta.get("is_main_agent", False) if isinstance(meta, dict) else False

        if is_main:
            # 主 Agent：使用 primary 模型
            primary_id = self._oc_primary
            if primary_id:
                return _resolve_model_alias(primary_id, self._oc_models)
            # primary 未配置 → fallback 到 YAML 中的 model
            model_id = full.get("model")
            return _resolve_model_alias(model_id, self._oc_models) if model_id else "未知"
        else:
            # 非主 Agent：使用 YAML 中的 model
            model_id = full.get("model")
            if not model_id:
                return "未知"
            return _resolve_model_alias(model_id, self._oc_models)

    # ── Session 缓存 ──

    def set_session_cache(self, agent_id: str, session_key: str) -> None:
        """缓存 agent_id 的最新 session_key。"""
        self._session_cache[agent_id] = session_key

    def get_session_cache(self, agent_id: str) -> Optional[str]:
        """获取缓存的 session_key。"""
        return self._session_cache.get(agent_id)

    def clear_cache(self) -> None:
        """清空 session 缓存。"""
        self._session_cache.clear()

    # ── 生命周期状态 ──

    def set_status(self, agent_id: str, status: str) -> None:
        """设置 Agent 生命周期状态。"""
        self._status[agent_id] = status

    def get_status(self, agent_id: str) -> Optional[str]:
        """获取 Agent 生命周期状态（默认 online）。"""
        return self._status.get(agent_id)


# ── SessionRouter ────────────────────────────────────────────────────────────────


class SessionRouter:
    """分阶段 Session 路由器。

    Phase 1-2：使用 sessions_list 动态查询 + 缓存
    Phase 3+：使用 Label 路由（从 session.key 推导）
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
        - phase3+: 返回 label（从 session.key 推导）
        """
        if self.phase in ("phase1", "phase2"):
            return self._cache.get(agent_id)

        # phase3+ 使用 Label 路由
        registry = ZooRegistry()
        return registry.get_label(agent_id)
