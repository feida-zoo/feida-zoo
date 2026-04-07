"""
ZooCoordinator - 全员协作系统协调器
监听 Event Bus，处理 @消息，触发目标成员唤醒，通过 SSE 推送聊天消息

P3.1 Collab System - 核心业务模块
"""

import json
import os
import tempfile
import threading
import time
import re
from pathlib import Path
from typing import Dict, List, Optional

from framework.shared.event_bus.event_bus import EventBus


class ZooCoordinator:
    """
    ZooCoordinator - 全员协作系统协调器
    监听 Event Bus，处理 @消息，触发目标成员唤醒，通过 SSE 推送聊天消息
    """

    def __init__(self, event_bus: EventBus = None, base_dir: str = None):
        """
        初始化 ZooCoordinator

        Args:
            event_bus: EventBus 实例，如果为 None 会创建新实例
            base_dir: 数据存储目录，用于聊天历史
        """
        project_root = Path(__file__).parent.parent.parent
        if base_dir is None:
            self.base_dir = project_root / "framework" / "data" / "zoo_coordinator"
        else:
            self.base_dir = Path(base_dir)

        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 持有 EventBus 引用
        self.event_bus = event_bus or EventBus.get_instance(member_name="zoo_coordinator")

        # SSE 管理器引用（由外部设置）
        self.sse_manager = None

        # 订阅的回调记录
        self._subscribed = False

        # 成员注册表
        self._member_registry: Dict[str, Dict] = {}

        # 聊天历史文件
        self._chat_history_file = self.base_dir / "events_latest.jsonl"
        self._chat_history_lock = threading.RLock()

        # 确保聊天文件存在
        if not self._chat_history_file.exists():
            self._chat_history_file.touch()

    def register_member(self, member_id: str, member_info: Dict) -> None:
        """
        注册成员到协调器

        Args:
            member_id: 成员ID
            member_info: 成员信息（名称、角色、回调等）
        """
        self._member_registry[member_id] = member_info

    def start(self) -> None:
        """
        启动协调器，开始监听 Event Bus 事件
        """
        if not self._subscribed:
            # 订阅所有事件，因为我们需要监听所有消息来提取 @ 提及
            self.event_bus.subscribe("*", self._handle_event)
            self._subscribed = True

    def stop(self) -> None:
        """
        停止协调器，取消订阅
        """
        # 注意：EventBus 当前没有取消订阅 API，这里仅标记停止
        self._subscribed = False

    def _handle_event(self, event: Dict) -> None:
        """
        处理 Event Bus 事件，检查是否有 @提及，触发唤醒和 SSE 推送

        Args:
            event: 事件字典
        """
        # 提取消息内容
        payload = event.get("payload", {}) or {}
        content = payload.get("content", "") if isinstance(payload, dict) else ""
        mentions = self._parse_mentions(content)

        # 保存到聊天历史
        self._append_to_chat_history(event)

        # 通过 SSE 广播新消息给所有前端客户端
        if self.sse_manager:
            chat_event = {
                "type": "new_message",
                "event": event,
                "mentions": mentions,
                "timestamp": time.time()
            }
            self.sse_manager.broadcast("chat_message", chat_event)

        # 唤醒被 @ 的成员（通过发布唤醒事件）
        for member_id in mentions:
            if member_id in self._member_registry:
                self._wake_member(member_id, event)

    def _parse_mentions(self, content: str) -> List[str]:
        """
        解析内容中的 @提及，提取被 @ 的成员 ID

        Args:
            content: 文本内容

        Returns:
            被 @ 的成员ID列表
        """
        if not content or not isinstance(content, str):
            return []

        # 使用正则表达式精确匹配 @ 后跟合法成员ID字符（字母、数字、下划线、连字符）
        # 要求 @ 前面是单词边界（非单词字符或字符串开始），后面跟合法ID字符
        # 这样可以避免匹配到 @weaver@stinger 中的 @stinger
        pattern = r'(?:^|[^a-zA-Z0-9_-])@([a-zA-Z0-9_-]+)'
        matches = re.findall(pattern, content)

        # 去重并返回
        mentions = []
        for match in matches:
            if match and match not in mentions:
                mentions.append(match)

        return mentions

    def _wake_member(self, member_id: str, trigger_event: Dict) -> None:
        """
        唤醒指定成员，发布唤醒事件到 Event Bus

        Args:
            member_id: 成员ID
            trigger_event: 触发本次唤醒的源事件
        """
        self.event_bus.publish(
            "member_awake",
            {
                "target_member": member_id,
                "trigger_event_id": trigger_event["id"],
                "trigger_event_type": trigger_event["type"],
                "trigger_publisher": trigger_event["publisher"],
                "timestamp": time.time()
            }
        )

    def _append_to_chat_history(self, event: Dict) -> None:
        """
        将事件追加到聊天历史文件

        Args:
            event: 事件字典
        """
        with self._chat_history_lock:
            try:
                with open(self._chat_history_file, "a", encoding="utf-8") as f:
                    json.dump(event, f, ensure_ascii=False, default=str)
                    f.write("\n")
            except (PermissionError, OSError) as e:
                # 文件权限错误或磁盘空间不足
                print(f"[ZooCoordinator] File access error appending to chat history: {e}")
                # 尝试创建备份文件或降级处理
                try:
                    # 尝试写入临时文件
                    temp_file = tempfile.NamedTemporaryFile(mode="w", prefix="zoo_chat_backup_", suffix=".jsonl", delete=False)
                    json.dump({"error": "Main chat file inaccessible, event lost", "original_event_id": event.get("id", "unknown"), "timestamp": time.time()}, temp_file, ensure_ascii=False)
                    temp_file.write("\n")
                    temp_file.close()
                    print(f"[ZooCoordinator] Backup event saved to {temp_file.name}")
                except Exception as backup_error:
                    print(f"[ZooCoordinator] Backup also failed: {backup_error}")
            except TypeError as e:
                # JSON 编码错误（不可序列化对象）
                print(f"[ZooCoordinator] JSON encode error: {e}")
                try:
                    # 尝试保存错误信息
                    with open(self._chat_history_file, "a", encoding="utf-8") as f:
                        simplified_event = {
                            "id": event.get("id", "unknown"),
                            "type": event.get("type", "unknown"),
                            "publisher": event.get("publisher", "unknown"),
                            "timestamp": event.get("timestamp", time.time()),
                            "error": "Original event failed JSON encoding"
                        }
                        json.dump(simplified_event, f, ensure_ascii=False)
                        f.write("\n")
                except Exception as fallback_error:
                    print(f"[ZooCoordinator] Fallback save also failed: {fallback_error}")
            except Exception as e:
                # 其他未知异常
                print(f"[ZooCoordinator] Unexpected error appending to chat history: {e}")

    def get_chat_history(self, limit: int = 100) -> List[Dict]:
        """
        获取最近的聊天历史

        Args:
            limit: 最大返回条数

        Returns:
            聊天事件列表
        """
        events = []
        with self._chat_history_lock:
            if not self._chat_history_file.exists():
                return []

            try:
                with open(self._chat_history_file, "r", encoding="utf-8") as f:
                    # 读取最后 limit 行
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        line = line.strip()
                        if line:
                            try:
                                events.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                print(f"[ZooCoordinator] Failed to read chat history: {e}")
                return []

        return events

    def get_member_registry(self) -> Dict[str, Dict]:
        """
        获取当前成员注册表

        Returns:
            成员注册表字典
        """
        return self._member_registry.copy()

    def set_sse_manager(self, sse_manager) -> None:
        """
        设置 SSE 管理器用于广播

        Args:
            sse_manager: SSEManager 实例
        """
        self.sse_manager = sse_manager
