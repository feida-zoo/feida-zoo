"""
Inbox 看门狗 — 目录扫描版

不再依赖 registry_path JSON 文件，改为扫描 mesh_dir/*/queue 目录
自动发现需要监控的 agent。
"""
import threading
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)


class InboxWatcher:
    """
    Inbox 看门狗

    监控 <mesh_dir>/<agent_id>/queue/ 目录。
    <mesh_dir> 应包含各个 agent 的子目录，例如传入 "../inbound"，
    该目录下每个子目录名 = agent_id，且子目录内有 queue/ 即视为有效。

    当新的 msg_<uuid>.json 写入时触发唤醒。

    设计来源：alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md §2.13
    改造依据：pl_3833295c 成员信息配置化
    """

    def __init__(self, mesh_dir: str, registry_path: str = "", on_wakeup: Optional[Callable] = None):
        """
        Args:
            mesh_dir: 包含 inbox 子目录的路径，内部拼接为 <mesh_dir>/<agent_id>/queue
            registry_path: （已废弃）保留参数签名兼容，不再使用
            on_wakeup: 回调函数，签名 (agent_id: str) -> None
        """
        self.mesh_dir = Path(mesh_dir)
        self.on_wakeup = on_wakeup
        self._running = False
        self._last_check: Dict[str, float] = {}
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动看门狗（守护线程模式）"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("InboxWatcher 守护线程已启动（目录扫描模式）")

    def _discover_agents(self) -> list:
        """扫描 mesh_dir 下的子目录，发现有 queue/ 子目录的即视为有效 agent。"""
        if not self.mesh_dir.exists():
            return []
        agents = []
        for entry in self.mesh_dir.iterdir():
            if entry.is_dir() and (entry / "queue").is_dir():
                agents.append(entry.name)
        return agents

    def _run(self) -> None:
        """实际轮询逻辑，在守护线程中运行。
        
        不再从 registry_path 文件读取 agent 列表，
        改为扫描 mesh_dir/*/queue 目录自发现。
        """
        # 首次发现 agent 并初始化基线
        agent_ids = self._discover_agents()
        for agent_id in agent_ids:
            self._init_baseline(agent_id)

        while self._running:
            # 每次轮询重新扫描，支持动态新增 agent
            current_agents = self._discover_agents()
            for agent_id in current_agents:
                if agent_id not in self._last_check:
                    self._init_baseline(agent_id)
                    logger.info(f"InboxWatcher 发现新 agent: {agent_id}")
                self._check_inbox(agent_id)
            time.sleep(2)

    def stop(self) -> None:
        """停止看门狗"""
        self._running = False

    def _init_baseline(self, agent_id: str) -> None:
        """启动时初始化基线。"""
        self._last_check[agent_id] = 0

    def _check_inbox(self, agent_id: str) -> None:
        """检查单个 agent 的 inbox 是否有未处理消息。"""
        queue_dir = self.mesh_dir / agent_id / "queue"
        if not queue_dir.exists():
            return

        try:
            files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
            if not files:
                return

            if self.on_wakeup:
                logger.info(f"检测到 {agent_id} inbox 有待处理消息: {len(files)} 条")
                self.on_wakeup(agent_id)
        except Exception as e:
            logger.warning(f"检查 {agent_id} inbox 出错: {e}")
