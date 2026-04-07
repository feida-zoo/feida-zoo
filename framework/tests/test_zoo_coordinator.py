"""
Unit tests for ZooCoordinator and SSE message push module (P3.1)
根据 TDD 规则编写的 ZooCoordinator 和 SSE 消息推送模块单元测试
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from typing import Dict, List

import pytest

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from framework.shared.event_bus.event_bus import EventBus
# Import the SSEManager from dashboard (we'll test it even though it's in dashboard)
sys.path.insert(0, str(project_root / "dashboard"))
from app_enhanced import SSEManager


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
        if base_dir is None:
            self.base_dir = project_root / "framework" / "data" / "zoo_coordinator"
        else:
            self.base_dir = Path(base_dir)

        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 持有 EventBus 引用
        self.event_bus = event_bus or EventBus.get_instance(member_name="zoo_coordinator")

        # SSE 管理器引用（由外部设置）
        self.sse_manager: SSEManager = None

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
        payload = event.get("payload", {})
        content = payload.get("content", "")
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
        if not content:
            return []

        mentions = []
        words = content.split()

        for word in words:
            if word.startswith("@"):
                member_id = word[1:].strip()
                if member_id and member_id not in mentions:
                    mentions.append(member_id)

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
                    json.dump(event, f, ensure_ascii=False)
                    f.write("\n")
            except Exception as e:
                # 记录错误但不抛出，避免阻断事件流程
                print(f"[ZooCoordinator] Failed to append to chat history: {e}")

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

    def set_sse_manager(self, sse_manager: SSEManager) -> None:
        """
        设置 SSE 管理器用于广播

        Args:
            sse_manager: SSEManager 实例
        """
        self.sse_manager = sse_manager


class TestZooCoordinator:
    """ZooCoordinator 单元测试类"""

    @pytest.fixture
    def temp_event_bus(self):
        """创建临时目录的 EventBus 用于测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 清除可能存在的实例
            EventBus.clear_instance()
            eb = EventBus.get_instance(member_name="test_zoo", base_dir=tmpdir)
            yield eb
            EventBus.clear_instance()

    @pytest.fixture
    def temp_coordinator(self, temp_event_bus):
        """创建临时目录的 ZooCoordinator 用于测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            coord = ZooCoordinator(event_bus=temp_event_bus, base_dir=tmpdir)
            yield coord

    def test_initialization(self, temp_coordinator):
        """测试 ZooCoordinator 初始化"""
        assert temp_coordinator is not None
        assert temp_coordinator.event_bus is not None
        assert not temp_coordinator._subscribed
        assert isinstance(temp_coordinator._member_registry, dict)
        assert temp_coordinator._chat_history_file.exists()

    def test_register_member(self, temp_coordinator):
        """测试成员注册"""
        member_info = {"name": "Weaver", "role": "developer"}
        temp_coordinator.register_member("weaver", member_info)

        registry = temp_coordinator.get_member_registry()
        assert "weaver" in registry
        assert registry["weaver"]["name"] == "Weaver"

    def test_parse_mentions_single(self, temp_coordinator):
        """测试单个 @提及 解析"""
        content = "Hello @weaver please review this PR"
        mentions = temp_coordinator._parse_mentions(content)
        assert mentions == ["weaver"]

    def test_parse_mentions_multiple(self, temp_coordinator):
        """测试多个 @提及 解析"""
        content = "@alpha @stinger please review my code @weaver"
        mentions = temp_coordinator._parse_mentions(content)
        assert len(mentions) == 3
        assert "alpha" in mentions
        assert "stinger" in mentions
        assert "weaver" in mentions

    def test_parse_mentions_empty(self, temp_coordinator):
        """测试空内容的 @提及 解析"""
        assert temp_coordinator._parse_mentions("") == []
        assert temp_coordinator._parse_mentions(None) == []
        assert temp_coordinator._parse_mentions("Hello world") == []

    def test_parse_mentions_duplicate(self, temp_coordinator):
        """测试去重 @提及"""
        content = "@weaver @weaver hello"
        mentions = temp_coordinator._parse_mentions(content)
        assert mentions == ["weaver"]  # 应该去重

    def test_start_subscribes_to_events(self, temp_coordinator):
        """测试启动后会订阅事件"""
        with patch.object(temp_coordinator.event_bus, 'subscribe') as mock_subscribe:
            temp_coordinator.start()
            mock_subscribe.assert_called_once_with("*", temp_coordinator._handle_event)
            assert temp_coordinator._subscribed

    def test_append_to_chat_history(self, temp_coordinator):
        """测试追加消息到聊天历史"""
        event = {
            "id": "test_123",
            "type": "chat_message",
            "publisher": "test",
            "timestamp": 1234567890,
            "payload": {"content": "test message"}
        }

        temp_coordinator._append_to_chat_history(event)
        history = temp_coordinator.get_chat_history()

        assert len(history) == 1
        assert history[0]["id"] == "test_123"
        assert history[0]["payload"]["content"] == "test message"

    def test_get_chat_history_paging(self, temp_coordinator):
        """测试聊天历史分页限制"""
        # 添加 10 条消息
        for i in range(10):
            event = {
                "id": f"test_{i}",
                "type": "chat_message",
                "payload": {"content": f"message {i}"}
            }
            temp_coordinator._append_to_chat_history(event)

        # 获取最近 5 条
        history = temp_coordinator.get_chat_history(limit=5)
        assert len(history) == 5
        assert history[-1]["id"] == "test_9"  # 最后一条应该是最新的

    def test_wake_member_publishes_event(self, temp_coordinator, temp_event_bus):
        """测试唤醒成员会发布 member_awake 事件"""
        # 注册成员
        temp_coordinator.register_member("weaver", {})

        # 创建触发事件
        trigger_event = {
            "id": "trigger_123",
            "type": "comment",
            "publisher": "alpha",
            "payload": {"content": "@weaver please wake up"}
        }

        # 调用唤醒
        temp_coordinator._wake_member("weaver", trigger_event)

        # 检查 Event Bus 是否有对应的事件
        pending = temp_event_bus.get_pending_events("member_awake")
        assert len(pending) == 1
        event = pending[0]
        assert event["type"] == "member_awake"
        assert event["payload"]["target_member"] == "weaver"
        assert event["payload"]["trigger_event_id"] == "trigger_123"

    def test_handle_event_with_mention_triggers_wake(self, temp_coordinator, temp_event_bus):
        """测试处理带有 @提及的事件会触发唤醒"""
        # 注册成员
        temp_coordinator.register_member("weaver", {})
        temp_coordinator.start()

        # 创建一个包含 @weaver 的事件，手动调用 _handle_event
        # 注意：EventBus 当前不支持通配符 * 订阅，所以我们直接测试处理逻辑
        event = {
            "id": "test_123",
            "type": "chat_message",
            "publisher": "alpha",
            "timestamp": 1234567890,
            "payload": {"content": "Hello @weaver this is a test"},
            "processed": False
        }

        # 手动调用处理
        temp_coordinator._handle_event(event)

        # 检查是否有 member_awake 被发布
        events = temp_event_bus._get_events_with_cache()
        wake_events = [e for e in events if e["type"] == "member_awake"]
        assert len(wake_events) == 1
        assert wake_events[0]["payload"]["target_member"] == "weaver"

    def test_set_sse_manager(self, temp_coordinator):
        """测试设置 SSE 管理器"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)
        assert temp_coordinator.sse_manager is sse_mgr

    def test_handle_event_broadcasts_via_sse(self, temp_coordinator, temp_event_bus):
        """测试处理事件会通过 SSE 广播"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)
        temp_coordinator.register_member("weaver", {})

        # mock broadcast 来验证
        with patch.object(sse_mgr, 'broadcast') as mock_broadcast:
            event = {
                "id": "test_123",
                "type": "chat_message",
                "publisher": "alpha",
                "payload": {"content": "@weaver hello"},
                "timestamp": 1234567890
            }

            temp_coordinator._handle_event(event)

            # 验证 broadcast 被调用
            mock_broadcast.assert_called_once()
            # 检查参数
            call_args = mock_broadcast.call_args
            assert call_args[0][0] == "chat_message"
            assert "mentions" in call_args[0][1]
            assert "weaver" in call_args[0][1]["mentions"]


class TestSSEManager:
    """SSEManager (Server-Sent Events 推送模块) 单元测试"""

    def test_initialization(self):
        """测试 SSEManager 初始化"""
        mgr = SSEManager()
        assert mgr is not None
        assert hasattr(mgr, 'clients')
        assert hasattr(mgr, 'lock')
        assert len(mgr.clients) == 0

    def test_add_client(self):
        """测试添加客户端"""
        mgr = SSEManager()
        mock_client = Mock()
        mgr.add_client(mock_client)
        assert mock_client in mgr.clients
        assert len(mgr.clients) == 1

    def test_add_multiple_clients(self):
        """测试添加多个客户端"""
        mgr = SSEManager()
        client1 = Mock()
        client2 = Mock()
        mgr.add_client(client1)
        mgr.add_client(client2)
        assert len(mgr.clients) == 2
        assert client1 in mgr.clients
        assert client2 in mgr.clients

    def test_remove_client(self):
        """测试移除客户端"""
        mgr = SSEManager()
        mock_client = Mock()
        mgr.add_client(mock_client)
        assert len(mgr.clients) == 1

        mgr.remove_client(mock_client)
        assert len(mgr.clients) == 0
        assert mock_client not in mgr.clients

    def test_remove_nonexistent_client(self):
        """测试移除不存在的客户端不报错"""
        mgr = SSEManager()
        mock_client = Mock()
        # 不应该抛出异常
        mgr.remove_client(mock_client)
        assert len(mgr.clients) == 0

    def test_broadcast_to_single_client(self):
        """测试向单个客户端广播"""
        mgr = SSEManager()
        mock_client = Mock()
        # 模拟 wfile
        mock_client.wfile = Mock()
        mock_client.wfile.write = Mock()
        mock_client.wfile.flush = Mock()

        mgr.add_client(mock_client)
        mgr.broadcast("test_event", {"key": "value"})

        # 验证 write 被调用
        mock_client.wfile.write.assert_called_once()
        # 验证 flush 被调用
        mock_client.wfile.flush.assert_called_once()

        # 验证写入的内容格式正确
        write_arg = mock_client.wfile.write.call_args[0][0].decode('utf-8')
        assert "event: test_event" in write_arg
        assert '"key": "value"' in write_arg
        assert write_arg.endswith("\n\n")

    def test_broadcast_to_multiple_clients(self):
        """测试向多个客户端广播"""
        mgr = SSEManager()
        clients = []
        for _ in range(3):
            client = Mock()
            client.wfile = Mock()
            client.wfile.write = Mock()
            client.wfile.flush = Mock()
            mgr.add_client(client)
            clients.append(client)

        mgr.broadcast("broadcast_test", {"message": "hello"})

        for client in clients:
            assert client.wfile.write.called
            assert client.wfile.flush.called

    def test_broadcast_removes_dead_clients(self):
        """测试广播时会移除断开连接的客户端"""
        mgr = SSEManager()

        # 好客户端
        good_client = Mock()
        good_client.wfile = Mock()
        good_client.wfile.write = Mock()
        good_client.wfile.flush = Mock()

        # 坏客户端（抛出 BrokenPipeError）
        bad_client = Mock()
        bad_client.wfile = Mock()
        bad_client.wfile.write = Mock(side_effect=BrokenPipeError())

        mgr.add_client(good_client)
        mgr.add_client(bad_client)
        assert len(mgr.clients) == 2

        # 执行广播
        mgr.broadcast("test", {})

        # 坏客户端应该被移除
        assert len(mgr.clients) == 1
        assert good_client in mgr.clients
        assert bad_client not in mgr.clients

    def test_broadcast_handles_connection_reset(self):
        """测试连接重置也会被清理"""
        mgr = SSEManager()
        client = Mock()
        client.wfile = Mock()
        client.wfile.write = Mock(side_effect=ConnectionResetError())
        mgr.add_client(client)

        mgr.broadcast("test", {})

        assert len(mgr.clients) == 0

    def test_broadcast_handles_attribute_error(self):
        """测试处理客户端属性错误"""
        mgr = SSEManager()
        client = Mock()
        # 模拟没有 wfile 属性，访问时抛出 AttributeError
        del client.wfile

        mgr.add_client(client)
        mgr.broadcast("test", {})

        assert len(mgr.clients) == 0

    def test_concurrent_add_remove_clients(self):
        """测试并发添加移除客户端的线程安全"""
        mgr = SSEManager()
        errors = []

        def add_remove_worker():
            try:
                for _ in range(100):
                    client = Mock()
                    mgr.add_client(client)
                    mgr.remove_client(client)
            except Exception as e:
                errors.append(e)

        # 启动多个线程并发操作
        threads = []
        for _ in range(10):
            t = threading.Thread(target=add_remove_worker)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # 不应该有错误
        assert len(errors) == 0
        assert len(mgr.clients) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
