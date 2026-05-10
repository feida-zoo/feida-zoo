"""
Inbox 看门狗
监控 inbox 目录文件变化，新消息到达时触发 Agent 唤醒
"""
import time
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class InboxWatcher:
    """
    Inbox 看门狗

    监控 <mesh_dir>/inbound/<agent_id>/queue/ 目录，
    当新的 msg_<uuid>.json 写入时触发唤醒。

    设计来源：alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md §2.13
    """

    def __init__(self, mesh_dir: str, registry_path: str, on_wakeup=None):
        """
        Args:
            mesh_dir: ZooMesh 根目录，如 "framework/shared/zoomesh"
            registry_path: agent 注册表 JSON 路径
            on_wakeup: 回调函数，签名 (agent_id: str) -> None
        """
        self.mesh_dir = Path(mesh_dir)
        self.registry_path = registry_path
        self.on_wakeup = on_wakeup
        self._running = False
        self._last_check: Dict[str, float] = {}  # agent_id -> last mtime checked

    def start(self) -> None:
        """启动看门狗（轮询模式，兼容无 watchdog 的环境）"""
        import json
        self._running = True

        # 加载注册表获取所有 agent_id
        try:
            with open(self.registry_path) as f:
                registry = json.load(f)
            agent_ids = list(registry.get("agents", {}).keys())
        except Exception as e:
            logger.warning(f"无法加载注册表: {e}，使用默认 agent 列表")
            agent_ids = ["weaver", "duci", "aeterna", "gulu", "alpha"]

        logger.info(f"InboxWatcher 启动，监控 {len(agent_ids)} 个 agent: {agent_ids}")

        # 启动时初始化 _last_check，避免首次轮询将历史消息当作新消息
        for agent_id in agent_ids:
            self._init_baseline(agent_id)

        while self._running:
            for agent_id in agent_ids:
                self._check_inbox(agent_id)
            time.sleep(2)  # 每 2 秒轮询一次

    def stop(self) -> None:
        """停止看门狗"""
        self._running = False

    def _init_baseline(self, agent_id: str) -> None:
        """启动时建立 mtime 基线，避免历史消息被误判为新消息。"""
        queue_dir = self.mesh_dir / "inbound" / agent_id / "queue"
        if not queue_dir.exists():
            self._last_check[agent_id] = 0.0
            return
        try:
            files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
            if files:
                self._last_check[agent_id] = files[-1].stat().st_mtime
            else:
                self._last_check[agent_id] = 0.0
        except Exception:
            self._last_check[agent_id] = 0.0

    def _check_inbox(self, agent_id: str) -> None:
        """检查单个 agent 的 inbox 是否有新消息"""
        queue_dir = self.mesh_dir / "inbound" / agent_id / "queue"
        if not queue_dir.exists():
            return

        try:
            files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
            if not files:
                return

            latest_mtime = files[-1].stat().st_mtime
            last_checked = self._last_check.get(agent_id, 0)

            if latest_mtime > last_checked:
                self._last_check[agent_id] = latest_mtime
                logger.info(f"检测到 {agent_id} inbox 新消息: {files[-1].name}")

                if self.on_wakeup:
                    self.on_wakeup(agent_id)
        except Exception as e:
            logger.warning(f"检查 {agent_id} inbox 出错: {e}")
