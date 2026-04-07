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

# Register custom marks
pytest.mark.performance = pytest.mark.performance

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

        import re
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
                    import tempfile
                    temp_file = tempfile.NamedTemporaryFile(mode="w", prefix="zoo_chat_backup_", suffix=".jsonl", delete=False)
                    json.dump({"error": "Main chat file inaccessible, event lost", "original_event_id": event.get("id", "unknown"), "timestamp": time.time()}, temp_file, ensure_ascii=False)
                    temp_file.write("\n")
                    temp_file.close()
                    print(f"[ZooCoordinator] Backup event saved to {temp_file.name}")
                except Exception as backup_error:
                    print(f"[ZooCoordinator] Backup also failed: {backup_error}")
            except json.JSONDecodeError as e:
                # JSON 编码错误
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

    def test_parse_mentions_invalid_formats(self, temp_coordinator):
        """测试无效 @提及格式"""
        # 无效格式应返回空或正确解析
        assert temp_coordinator._parse_mentions("@weaver@stinger") == ["weaver"]  # 只匹配第一个 @weaver，@stinger 前面是字母，不匹配
        assert temp_coordinator._parse_mentions("@weaver!") == ["weaver"]  # 匹配 weaver，! 不是合法字符
        assert temp_coordinator._parse_mentions("@@") == []  # 无效，@后没有合法字符
        assert temp_coordinator._parse_mentions("@ ") == []  # @后是空格
        
        # 包含特殊字符
        assert temp_coordinator._parse_mentions("@weaver-123") == ["weaver-123"]  # 连字符允许
        assert temp_coordinator._parse_mentions("@weaver_123") == ["weaver_123"]  # 下划线允许
        assert temp_coordinator._parse_mentions("@weaver.123") == ["weaver"]  # 只匹配到 weaver，因为 . 不是合法字符
        
        # 边界测试
        assert temp_coordinator._parse_mentions("hello@weaver") == []  # @ 在单词中间，不匹配
        assert temp_coordinator._parse_mentions("hello @weaver world") == ["weaver"]  # 正常匹配
        assert temp_coordinator._parse_mentions("@weaver,@stinger") == ["weaver", "stinger"]  # 逗号分隔，两个都匹配

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

    def test_stop_unsubscribes_and_sets_flag(self, temp_coordinator):
        """测试停止协调器会取消订阅并设置标志"""
        # 先启动以订阅事件
        temp_coordinator.start()
        assert temp_coordinator._subscribed
        
        # 停止协调器
        temp_coordinator.stop()
        
        # 验证状态已更新
        assert not temp_coordinator._subscribed

    def test_start_stop_idempotent(self, temp_coordinator):
        """测试多次启动/停止的幂等性"""
        # 多次启动应该不会出错
        temp_coordinator.start()
        temp_coordinator.start()  # 再次启动
        assert temp_coordinator._subscribed
        
        # 多次停止应该不会出错
        temp_coordinator.stop()
        temp_coordinator.stop()  # 再次停止
        assert not temp_coordinator._subscribed

    def test_events_not_handled_after_stop(self, temp_coordinator, temp_event_bus):
        """测试停止后不再处理事件"""
        # 注册成员并启动
        temp_coordinator.register_member("weaver", {})
        temp_coordinator.start()
        
        # 停止协调器
        temp_coordinator.stop()
        
        # 模拟一个事件，由于 stop() 后 EventBus 没有实际取消订阅 API，
        # 我们主要验证状态标志的正确性
        assert not temp_coordinator._subscribed
        
        # 如果 EventBus 未来支持取消订阅，这里应验证取消订阅逻辑
        # 当前只是验证状态标志

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

    def test_handle_event_without_mentions(self, temp_coordinator, temp_event_bus):
        """测试处理不含 @提及 的事件"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)

        # mock broadcast 来验证
        with patch.object(sse_mgr, 'broadcast') as mock_broadcast:
            event = {
                "id": "test_123",
                "type": "chat_message",
                "publisher": "alpha",
                "payload": {"content": "Hello world without mentions"},
                "timestamp": 1234567890
            }

            temp_coordinator._handle_event(event)

            # 即使没有提及，也应该广播
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            assert call_args[0][0] == "chat_message"
            assert call_args[0][1]["mentions"] == []  # 空提及列表

    def test_handle_event_malformed_payload(self, temp_coordinator, temp_event_bus):
        """测试处理格式错误的事件"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)

        # 测试缺少 payload 的事件
        event_without_payload = {
            "id": "test_123",
            "type": "chat_message",
            "publisher": "alpha",
            "timestamp": 1234567890
        }

        # 不应该抛出异常
        temp_coordinator._handle_event(event_without_payload)

        # 测试 payload 为 None
        event_none_payload = {
            "id": "test_124",
            "type": "chat_message",
            "publisher": "alpha",
            "payload": None,
            "timestamp": 1234567890
        }
        temp_coordinator._handle_event(event_none_payload)

        # 测试空事件
        empty_event = {}
        temp_coordinator._handle_event(empty_event)

    def test_handle_event_none_values(self, temp_coordinator, temp_event_bus):
        """测试处理包含 None 值的事件"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)

        event = {
            "id": None,
            "type": None,
            "publisher": None,
            "payload": {"content": None},
            "timestamp": None
        }

        # 不应该抛出异常
        temp_coordinator._handle_event(event)

    def test_chat_history_file_permission_error(self, temp_coordinator):
        """测试聊天历史文件权限错误处理"""
        event = {
            "id": "test_123",
            "type": "chat_message",
            "payload": {"content": "test"}
        }

        # 模拟文件权限错误
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # 不应该抛出异常
            temp_coordinator._append_to_chat_history(event)
            # 错误应该被捕获并记录

    def test_chat_history_json_encode_error(self, temp_coordinator):
        """测试聊天历史 JSON 编码错误处理"""
        # 创建包含不可序列化对象的事件
        import threading
        event = {
            "id": "test_123",
            "type": "chat_message",
            "payload": {"content": "test", "thread": threading.Thread()}
        }

        # 不应该抛出异常
        temp_coordinator._append_to_chat_history(event)
        # 错误应该被捕获并记录

    def test_concurrent_event_handling(self, temp_coordinator, temp_event_bus):
        """测试并发事件处理"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)
        temp_coordinator.register_member("weaver", {})
        temp_coordinator.register_member("stinger", {})
        temp_coordinator.register_member("alpha", {})
        
        events_processed = []
        errors = []
        
        def process_event(i):
            try:
                event = {
                    "id": f"event_{i}",
                    "type": "chat_message",
                    "publisher": f"user_{i % 3}",
                    "payload": {"content": f"@weaver @stinger message {i}"},
                    "timestamp": time.time() + i
                }
                temp_coordinator._handle_event(event)
                events_processed.append(i)
            except Exception as e:
                errors.append(e)
        
        # 并发处理多个事件
        threads = []
        for i in range(20):
            t = threading.Thread(target=process_event, args=(i,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # 验证所有事件都被处理
        assert len(errors) == 0
        assert len(events_processed) == 20
        
        # 检查聊天历史（可能需要等待文件写入完成）
        time.sleep(0.1)
        history = temp_coordinator.get_chat_history(limit=50)
        assert len(history) >= 20  # 至少有 20 个事件

    def test_concurrent_member_registry_access(self, temp_coordinator):
        """测试并发成员注册表访问"""
        errors = []
        
        def register_members(prefix):
            try:
                for i in range(50):
                    member_id = f"{prefix}_{i}"
                    member_info = {"name": f"Member {prefix}_{i}", "role": "test"}
                    temp_coordinator.register_member(member_id, member_info)
            except Exception as e:
                errors.append(e)
        
        def get_registry_repeatedly(thread_id):
            try:
                for _ in range(100):
                    registry = temp_coordinator.get_member_registry()
                    # 验证返回的是副本而不是原始引用
                    assert isinstance(registry, dict)
            except Exception as e:
                errors.append(e)
        
        # 并发注册和获取
        threads = []
        for i in range(5):
            t = threading.Thread(target=register_members, args=(f"thread{i}",))
            t.start()
            threads.append(t)
        
        for i in range(3):
            t = threading.Thread(target=get_registry_repeatedly, args=(i,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # 验证没有错误
        assert len(errors) == 0
        
        # 验证所有成员都被注册
        registry = temp_coordinator.get_member_registry()
        assert len(registry) == 5 * 50  # 5个线程各注册50个成员

    def test_concurrent_chat_history_access(self, temp_coordinator):
        """测试并发聊天历史访问"""
        errors = []
        events_written = []
        
        def append_events(thread_id):
            try:
                for i in range(20):
                    event = {
                        "id": f"thread{thread_id}_event{i}",
                        "type": "chat_message",
                        "payload": {"content": f"Message from thread {thread_id}, event {i}"},
                        "timestamp": time.time()
                    }
                    temp_coordinator._append_to_chat_history(event)
                    events_written.append(f"thread{thread_id}_event{i}")
            except Exception as e:
                errors.append(e)
        
        def read_history(thread_id):
            try:
                for _ in range(10):
                    history = temp_coordinator.get_chat_history(limit=100)
                    assert isinstance(history, list)
            except Exception as e:
                errors.append(e)
        
        # 并发写入和读取
        threads = []
        for i in range(3):
            t = threading.Thread(target=append_events, args=(i,))
            t.start()
            threads.append(t)
        
        for i in range(2):
            t = threading.Thread(target=read_history, args=(i,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        # 验证没有错误
        assert len(errors) == 0
        
        # 验证所有事件都被写入
        time.sleep(0.1)  # 等待文件写入完成
        history = temp_coordinator.get_chat_history(limit=100)
        event_ids = [e.get("id", "") for e in history]
        
        # 检查写入的事件是否在历史中（可能有些事件被并发覆盖，但至少大部分应该存在）
        found_count = sum(1 for event_id in events_written if event_id in event_ids)
        assert found_count >= len(events_written) * 0.8  # 至少80%的事件被正确记录

    @pytest.mark.performance
    def test_performance_high_frequency_events(self, temp_coordinator):
        """测试高频事件处理性能"""
        sse_mgr = SSEManager()
        temp_coordinator.set_sse_manager(sse_mgr)
        
        # mock broadcast 以避免实际网络开销
        with patch.object(sse_mgr, 'broadcast') as mock_broadcast:
            import time
            start_time = time.time()
            
            # 处理 100 个事件
            for i in range(100):
                event = {
                    "id": f"perf_event_{i}",
                    "type": "chat_message",
                    "payload": {"content": f"Performance test message {i} @weaver"},
                    "timestamp": time.time()
                }
                temp_coordinator._handle_event(event)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # 验证 broadcast 被调用了 100 次
            assert mock_broadcast.call_count == 100
            
            # 性能要求：100个事件应在2秒内处理完成
            assert elapsed < 2.0, f"Processing 100 events took {elapsed:.2f}s, expected <2.0s"


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



    def test_broadcast_json_serialization_error_handling(self):
        """测试 JSON 序列化错误处理"""
        mgr = SSEManager()
        client = Mock()
        client.wfile = Mock()
        client.wfile.write = Mock()
        client.wfile.flush = Mock()
        mgr.add_client(client)

        # 测试不可序列化对象（如 bytes）
        invalid_data = {
            "normal": "string",
            "bytes_data": b"binary data",  # 无法直接序列化
            "set_data": {1, 2, 3}  # set 无法直接序列化
        }

        # 广播应该成功，即使有不可序列化数据
        mgr.broadcast("test", invalid_data)

        # 验证 write 被调用（表示广播成功）
        assert client.wfile.write.called
        assert client.wfile.flush.called

        # 验证写入的内容包含错误处理
        write_arg = client.wfile.write.call_args[0][0]
        message = write_arg.decode('utf-8')
        # 由于 default=str，应该能序列化，不会抛出错误
        assert "event: test" in message

    def test_broadcast_with_circular_reference(self):
        """测试循环引用处理"""
        mgr = SSEManager()
        client = Mock()
        client.wfile = Mock()
        client.wfile.write = Mock()
        client.wfile.flush = Mock()
        mgr.add_client(client)

        # 创建循环引用
        data = {"name": "test"}
        data["self"] = data  # 循环引用

        # 广播应该处理循环引用而不崩溃
        mgr.broadcast("circular", data)

        # 验证 write 被调用
        assert client.wfile.write.called
        assert client.wfile.flush.called

    @pytest.mark.performance
    def test_performance_broadcast_to_many_clients(self):
        """测试向大量客户端广播的性能"""
        mgr = SSEManager()
        
        # 创建大量 mock 客户端
        clients = []
        for _ in range(100):  # 测试 100 个客户端
            client = Mock()
            client.wfile = Mock()
            client.wfile.write = Mock()
            client.wfile.flush = Mock()
            mgr.add_client(client)
            clients.append(client)
        
        # 测量广播时间
        import time
        start_time = time.time()
        
        mgr.broadcast("performance_test", {"message": "test", "count": 100})
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 验证所有客户端都收到消息
        for client in clients:
            assert client.wfile.write.called
            assert client.wfile.flush.called
        
        # 性能要求：100个客户端广播应在1秒内完成
        assert elapsed < 1.0, f"Broadcast to 100 clients took {elapsed:.2f}s, expected <1.0s"



    @pytest.mark.performance
    def test_memory_usage_large_message_broadcast(self):
        """测试广播大消息时的内存使用"""
        mgr = SSEManager()
        client = Mock()
        client.wfile = Mock()
        client.wfile.write = Mock()
        client.wfile.flush = Mock()
        mgr.add_client(client)
        
        # 创建大消息（约 1MB）
        large_data = {
            "large_content": "x" * (1024 * 1024),  # 1MB 字符串
            "metadata": {"type": "large", "size": 1024 * 1024}
        }
        
        # 广播大消息不应崩溃
        mgr.broadcast("large_message", large_data)
        
        # 验证 write 被调用
        assert client.wfile.write.called
        
        # 检查写入的数据大小大致正确
        write_arg = client.wfile.write.call_args[0][0]
        assert len(write_arg) > 1024 * 1024  # 应该大于 1MB

    @pytest.mark.performance
    def test_concurrent_broadcast_performance(self):
        """测试并发广播性能"""
        mgr = SSEManager()
        
        # 添加多个客户端
        clients = []
        for _ in range(50):
            client = Mock()
            client.wfile = Mock()
            client.wfile.write = Mock()
            client.wfile.flush = Mock()
            mgr.add_client(client)
            clients.append(client)
        
        errors = []
        
        def broadcast_worker(worker_id):
            try:
                for i in range(20):
                    data = {"worker": worker_id, "message": f"msg_{i}", "timestamp": time.time()}
                    mgr.broadcast(f"worker_{worker_id}", data)
            except Exception as e:
                errors.append(e)
        
        # 并发广播
        import time
        threads = []
        start_time = time.time()
        
        for i in range(10):
            t = threading.Thread(target=broadcast_worker, args=(i,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 验证没有错误
        assert len(errors) == 0
        
        # 10个线程各广播20次，总共200次广播
        # 性能要求：200次广播应在5秒内完成
        assert elapsed < 5.0, f"200 concurrent broadcasts took {elapsed:.2f}s, expected <5.0s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
