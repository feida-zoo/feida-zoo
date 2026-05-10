"""Agent 收件箱会话管理。

实现 send/receive/ack/nack 协议，每消息独立文件（msg_<uuid>.json），
原子写入（temp+rename）。设计约束来自文档 §2.1。
"""

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class InboxConfig:
    """收件箱投递配置。"""

    max_delivery_attempts: int = 3
    visibility_timeout: int = 300
    ttl: int = 3600


class AgentSession:
    """Agent 收件箱会话。

    目录结构：
        <inbox_dir>/
        ├── queue/          ← 待消费消息
        │   └── msg_<uuid>.json
        ├── dlq/            ← 死信队列
        │   └── msg_<uuid>.json
        └── checkpoint.json ← 最后已消费消息标记
    """

    def __init__(self, agent_id: str, inbox_dir: str):
        self.agent_id = agent_id
        self.inbox_dir = Path(inbox_dir)
        self.config = InboxConfig()

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保收件箱目录结构存在。"""
        (self.inbox_dir / "queue").mkdir(parents=True, exist_ok=True)
        (self.inbox_dir / "dlq").mkdir(parents=True, exist_ok=True)

    # ---- 核心协议 ----

    def send(self, from_agent: str, body: str) -> str:
        """发送消息到该 Agent 的收件箱。

        1. 生成 msg_<uuid>.json
        2. 原子写入 queue/msg_<uuid>.json（temp + rename）
        3. 返回消息 id
        """
        msg_id = str(uuid.uuid4())
        msg: Dict = {
            "id": msg_id,
            "from": from_agent,
            "to": self.agent_id,
            "body": body,
            "timestamp": _now_iso(),
            "delivery_count": 0,
            "ttl": self.config.ttl,
        }

        queue_dir = self.inbox_dir / "queue"
        target = queue_dir / f"msg_{msg_id}.json"
        temp = queue_dir / f".tmp_{msg_id}.json"

        with open(temp, "w", encoding="utf-8") as f:
            json.dump(msg, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        os.rename(str(temp), str(target))
        return msg_id

    def receive(self) -> Optional[Dict]:
        """接收最早的一条待消费消息。

        按 mtime 排序取最早的 msg_<uuid>.json。
        """
        queue_dir = self.inbox_dir / "queue"
        files = sorted(
            queue_dir.glob("msg_*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        if not files:
            return None

        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def ack(self, msg_id: str) -> None:
        """确认消费消息。

        1. 删除 queue/msg_<msg_id>.json
        2. 更新 checkpoint.json 的 last_id
        """
        queue_dir = self.inbox_dir / "queue"
        msg_file = queue_dir / f"msg_{msg_id}.json"

        if msg_file.exists():
            msg_file.unlink()

        checkpoint = self.inbox_dir / "checkpoint.json"
        with open(checkpoint, "w", encoding="utf-8") as f:
            json.dump({"last_id": msg_id, "updated_at": _now_iso()}, f)
            f.flush()
            os.fsync(f.fileno())

    def nack(self, msg_id: str) -> str:
        """否定确认（消费失败）。

        1. 递增 msg.json 内的 delivery_count
        2. 如果 delivery_count < max_delivery_attempts → 返回 "retry"
        3. 如果 delivery_count >= max_delivery_attempts → 移动到 dlq/，返回 "dlq"

        P2-2 fix: 使用 temp+rename 原子写入替代 r+原地更新，避免并发竞态。
        """
        queue_dir = self.inbox_dir / "queue"
        msg_file = queue_dir / f"msg_{msg_id}.json"

        if not msg_file.exists():
            return "not_found"

        with open(msg_file, "r", encoding="utf-8") as f:
            msg = json.load(f)

        msg["delivery_count"] += 1

        if msg["delivery_count"] >= self.config.max_delivery_attempts:
            # 移入死信队列（先关闭文件句柄再用 rename）
            dlq_dir = self.inbox_dir / "dlq"
            dlq_target = dlq_dir / f"msg_{msg_id}.json"
            temp_file = queue_dir / f"msg_{msg_id}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(msg, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.rename(str(temp_file), str(dlq_target))
            if msg_file.exists():
                msg_file.unlink()
            return "dlq"

        # 非 DLQ：原子写入更新 delivery_count
        temp_file = queue_dir / f"msg_{msg_id}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(msg, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.rename(str(temp_file), str(msg_file))
        return "retry"

    # ---- 恢复相关 ----

    def get_checkpoint(self) -> Optional[Dict]:
        """读取 checkpoint.json。"""
        checkpoint = self.inbox_dir / "checkpoint.json"
        if not checkpoint.exists():
            return None
        with open(checkpoint, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_unacked_messages(self) -> List[Dict]:
        """获取所有未确认的消息列表（按 mtime 排序）。"""
        queue_dir = self.inbox_dir / "queue"
        files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
        messages = []
        for f in files:
            with open(f, "r", encoding="utf-8") as fp:
                messages.append(json.load(fp))
        return messages


def _now_iso() -> str:
    """当前时间的 ISO 格式字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
