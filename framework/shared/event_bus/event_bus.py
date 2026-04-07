"""
Event Bus for Feida Zoo - Task 2.1
跨成员事件总线原型

基于文件系统的异步消息队列，支持订阅/发布模式。
"""
import json
import os
import time
import uuid
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional
import fcntl
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    事件总线类，提供基于文件系统的发布/订阅功能。
    """
    
    def __init__(self, base_dir: str = None, member_name: str = "unknown"):
        """
        初始化事件总线。
        
        Args:
            base_dir: 事件存储的基础目录，默认为 framework/shared/event_bus/
            member_name: 当前成员名称，用于标识事件发布者
        """
        if base_dir is None:
            # 默认使用项目中的共享目录
            project_root = Path(__file__).parent.parent.parent.parent
            self.base_dir = project_root / "framework" / "shared" / "event_bus"
        else:
            self.base_dir = Path(base_dir)
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.member_name = member_name
        self.events_file = self.base_dir / "events.json"
        self.subscriptions_file = self.base_dir / "subscriptions.json"
        self.processed_events_file = self.base_dir / "processed_events.json"
        
        # 订阅者映射：事件类型 -> [回调函数列表]
        self.subscribers: Dict[str, List[Callable]] = {}
        
        # 已处理事件ID缓存（用于去重）
        self.processed_events: set = set()
        
        # 文件锁
        self.lock = threading.RLock()
        
        # 初始化文件
        self._init_files()
        
        # 加载已处理事件
        self._load_processed_events()
        
        logger.info(f"EventBus initialized for member: {member_name}, base_dir: {self.base_dir}")
    
    def _init_files(self):
        """初始化必要的JSON文件"""
        with self.lock:
            # 初始化事件文件
            if not self.events_file.exists():
                self._atomic_write(self.events_file, [])
            
            # 初始化订阅文件
            if not self.subscriptions_file.exists():
                self._atomic_write(self.subscriptions_file, {})
            
            # 初始化已处理事件文件
            if not self.processed_events_file.exists():
                self._atomic_write(self.processed_events_file, [])
    
    def _atomic_write(self, file_path: Path, data: Any):
        """
        原子化写入文件，确保并发安全。
        
        Args:
            file_path: 文件路径
            data: 要写入的数据
        """
        temp_file = file_path.with_suffix('.tmp')
        
        try:
            # 写入临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子重命名
            temp_file.rename(file_path)
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise
    
    def _load_processed_events(self):
        """加载已处理的事件ID"""
        try:
            with open(self.processed_events_file, 'r', encoding='utf-8') as f:
                processed = json.load(f)
                self.processed_events = set(processed)
        except (FileNotFoundError, json.JSONDecodeError):
            self.processed_events = set()
    
    def _save_processed_events(self):
        """保存已处理的事件ID"""
        with self.lock:
            self._atomic_write(self.processed_events_file, list(self.processed_events))
    
    def _generate_event_id(self, event_type: str, payload: Dict) -> str:
        """
        生成事件ID，用于去重。
        
        Args:
            event_type: 事件类型
            payload: 事件载荷
            
        Returns:
            事件ID字符串
        """
        # 基于事件内容和时间戳生成唯一ID
        content_hash = hashlib.md5(
            f"{event_type}:{json.dumps(payload, sort_keys=True)}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        return f"{self.member_name}_{event_type}_{content_hash}"
    
    def publish(self, event_type: str, payload: Dict, delay_seconds: int = 0) -> str:
        """
        发布事件到总线。
        
        Args:
            event_type: 事件类型（如：member_awake, task_completed, error_occurred）
            payload: 事件载荷（字典格式）
            delay_seconds: 延迟处理时间（秒）
            
        Returns:
            事件ID
        """
        with self.lock:
            # 生成事件ID
            event_id = self._generate_event_id(event_type, payload)
            
            # 创建事件对象
            event = {
                "id": event_id,
                "type": event_type,
                "publisher": self.member_name,
                "timestamp": time.time(),
                "payload": payload,
                "processed": False,
                "process_after": time.time() + delay_seconds if delay_seconds > 0 else 0
            }
            
            # 读取现有事件
            try:
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    # 使用文件锁确保并发安全
                    fcntl.flock(f, fcntl.LOCK_SH)
                    events = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except (FileNotFoundError, json.JSONDecodeError):
                events = []
            
            # 添加新事件
            events.append(event)
            
            # 写入文件
            with open(self.events_file, 'w', encoding='utf-8') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(events, f, ensure_ascii=False, indent=2)
                fcntl.flock(f, fcntl.LOCK_UN)
            
            logger.info(f"Event published: {event_type} (id: {event_id}) by {self.member_name}")
            
            return event_id
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        订阅指定类型的事件。
        
        Args:
            event_type: 要订阅的事件类型
            callback: 事件处理回调函数，接收(event_dict)作为参数
        """
        with self.lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            self.subscribers[event_type].append(callback)
            
            # 保存订阅信息到文件
            try:
                with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                    subscriptions = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                subscriptions = {}
            
            if event_type not in subscriptions:
                subscriptions[event_type] = []
            
            # 记录订阅者信息
            subscriber_info = {
                "member": self.member_name,
                "subscribed_at": time.time()
            }
            
            if subscriber_info not in subscriptions[event_type]:
                subscriptions[event_type].append(subscriber_info)
            
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(subscriptions, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Member {self.member_name} subscribed to {event_type}")
    
    def process_events(self, max_events: int = 10) -> int:
        """
        处理待处理的事件。
        
        Args:
            max_events: 最大处理事件数量
            
        Returns:
            实际处理的事件数量
        """
        processed_count = 0
        
        with self.lock:
            # 读取事件
            try:
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    events = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except (FileNotFoundError, json.JSONDecodeError):
                events = []
            
            current_time = time.time()
            events_to_process = []
            
            # 筛选需要处理的事件
            for event in events:
                if (not event.get("processed", False) and 
                    event["id"] not in self.processed_events and
                    event.get("process_after", 0) <= current_time):
                    events_to_process.append(event)
            
            # 限制处理数量
            events_to_process = events_to_process[:max_events]
            
            # 处理事件
            for event in events_to_process:
                event_type = event["type"]
                
                # 检查是否有订阅者
                if event_type in self.subscribers:
                    for callback in self.subscribers[event_type]:
                        try:
                            callback(event)
                            logger.debug(f"Event {event['id']} processed by {self.member_name}")
                        except Exception as e:
                            logger.error(f"Error processing event {event['id']}: {e}")
                
                # 标记为已处理
                event["processed"] = True
                self.processed_events.add(event["id"])
                processed_count += 1
            
            # 更新事件文件
            if processed_count > 0:
                # 更新事件状态
                for i, event in enumerate(events):
                    if event["id"] in [e["id"] for e in events_to_process]:
                        events[i]["processed"] = True
                
                # 写入文件
                with open(self.events_file, 'w', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    json.dump(events, f, ensure_ascii=False, indent=2)
                    fcntl.flock(f, fcntl.LOCK_UN)
                
                # 保存已处理事件
                self._save_processed_events()
            
            return processed_count
    
    def get_pending_events(self, event_type: str = None) -> List[Dict]:
        """
        获取待处理的事件。
        
        Args:
            event_type: 可选，指定事件类型
            
        Returns:
            待处理事件列表
        """
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                events = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        
        current_time = time.time()
        pending_events = []
        
        for event in events:
            if (not event.get("processed", False) and 
                event.get("process_after", 0) <= current_time):
                if event_type is None or event["type"] == event_type:
                    pending_events.append(event)
        
        return pending_events
    
    def get_statistics(self) -> Dict:
        """
        获取事件总线统计信息。
        
        Returns:
            统计信息字典
        """
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                events = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
        except (FileNotFoundError, json.JSONDecodeError):
            events = []
        
        total_events = len(events)
        processed_events = sum(1 for e in events if e.get("processed", False))
        pending_events = total_events - processed_events
        
        # 按事件类型统计
        type_stats = {}
        for event in events:
            event_type = event["type"]
            if event_type not in type_stats:
                type_stats[event_type] = {"total": 0, "processed": 0}
            
            type_stats[event_type]["total"] += 1
            if event.get("processed", False):
                type_stats[event_type]["processed"] += 1
        
        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "pending_events": pending_events,
            "processed_events_cache": len(self.processed_events),
            "event_types": type_stats,
            "subscribers": {k: len(v) for k, v in self.subscribers.items()}
        }
    
    def clear_processed_events(self, older_than_days: int = 7):
        """
        清理已处理的事件。
        
        Args:
            older_than_days: 清理多少天前的已处理事件
        """
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        
        with self.lock:
            try:
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_SH)
                    events = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except (FileNotFoundError, json.JSONDecodeError):
                return
            
            # 过滤掉已处理且超过时间阈值的事件
            filtered_events = []
            for event in events:
                if (not event.get("processed", False) or 
                    event.get("timestamp", 0) > cutoff_time):
                    filtered_events.append(event)
                else:
                    # 从已处理缓存中移除
                    self.processed_events.discard(event["id"])
            
            # 写入文件
            if len(filtered_events) < len(events):
                with open(self.events_file, 'w', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    json.dump(filtered_events, f, ensure_ascii=False, indent=2)
                    fcntl.flock(f, fcntl.LOCK_UN)
                
                # 保存已处理事件缓存
                self._save_processed_events()
                
                logger.info(f"Cleaned {len(events) - len(filtered_events)} processed events older than {older_than_days} days")


# 全局事件总线实例（可选）
_event_bus_instance = None

def get_event_bus(member_name: str = "unknown") -> EventBus:
    """
    获取全局事件总线实例（单例模式）。
    
    Args:
        member_name: 成员名称
        
    Returns:
        EventBus实例
    """
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus(member_name=member_name)
    return _event_bus_instance