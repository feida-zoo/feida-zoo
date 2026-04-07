"""
Event Bus for Feida Zoo - Task 2.1
跨成员事件总线原型 - 修复P0级安全漏洞

基于文件系统的异步消息队列，支持订阅/发布模式。
修复了原子写入、事件去重、单例模式和锁竞争问题。
"""
import json
import os
import time
import uuid
import threading
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional, Set
import fcntl
import logging
import shutil

logger = logging.getLogger(__name__)


class EventBus:
    """
    事件总线类，提供基于文件系统的发布/订阅功能。
    """
    
    # 类级别的实例缓存，按成员名称存储
    _instances: Dict[str, 'EventBus'] = {}
    _instances_lock = threading.RLock()
    
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
        self.processed_events: Set[str] = set()
        
        # 文件读写锁 - 使用线程锁替代部分文件锁以降低竞争
        self.file_write_lock = threading.RLock()
        self.events_cache_lock = threading.RLock()
        
        # 事件缓存，减少文件读取次数
        self._events_cache: Optional[List[Dict]] = None
        self._cache_timestamp = 0.0
        
        # 初始化文件
        self._init_files()
        
        # 加载已处理事件
        self._load_processed_events()
        
        logger.info(f"EventBus initialized for member: {member_name}, base_dir: {self.base_dir}")
    
    def _init_files(self):
        """初始化必要的JSON文件，使用原子写入"""
        with self.file_write_lock:
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
            
        Returns:
            bool: 写入是否成功
        """
        # 创建临时文件
        temp_dir = file_path.parent
        temp_file = None
        
        try:
            # 创建唯一的临时文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                encoding='utf-8', 
                dir=temp_dir, 
                suffix='.tmp',
                delete=False
            ) as f:
                temp_file = Path(f.name)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 原子重命名 - 这是关键操作，确保数据完整性
            temp_file.replace(file_path)
            logger.debug(f"Atomic write completed: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed atomic write to {file_path}: {e}")
            # 清理临时文件
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            return False
    
    def _atomic_read(self, file_path: Path, default: Any = None):
        """
        原子化读取文件，确保读取到完整数据。
        
        Args:
            file_path: 文件路径
            default: 读取失败时的默认值
            
        Returns:
            读取到的数据或默认值
        """
        try:
            # 使用文件锁确保读取时文件不被修改
            with open(file_path, 'r', encoding='utf-8') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to read {file_path}: {e}, using default")
            return default
        except Exception as e:
            logger.error(f"Unexpected error reading {file_path}: {e}")
            return default
    
    def _load_processed_events(self):
        """加载已处理的事件ID，使用原子读取"""
        try:
            processed = self._atomic_read(self.processed_events_file, [])
            self.processed_events = set(processed)
        except Exception as e:
            logger.error(f"Failed to load processed events: {e}")
            self.processed_events = set()
    
    def _save_processed_events(self):
        """保存已处理的事件ID，使用原子写入"""
        with self.file_write_lock:
            self._atomic_write(self.processed_events_file, list(self.processed_events))
    
    def _generate_event_id(self, event_type: str, payload: Dict) -> str:
        """
        生成事件ID，用于去重。
        修复：移除时间戳，确保相同内容的事件有相同ID
        
        Args:
            event_type: 事件类型
            payload: 事件载荷
            
        Returns:
            事件ID字符串
        """
        # 基于事件内容和成员名称生成唯一ID，不包含时间戳
        # 对payload进行排序以确保相同内容的JSON生成相同哈希
        sorted_payload = json.dumps(payload, sort_keys=True) if payload else "{}"
        content_hash = hashlib.sha256(
            f"{event_type}:{sorted_payload}:{self.member_name}".encode()
        ).hexdigest()[:24]
        
        return f"{self.member_name}_{event_type}_{content_hash}"
    
    def _get_events_with_cache(self) -> List[Dict]:
        """
        获取事件列表，使用缓存减少文件读取。
        
        Returns:
            事件列表
        """
        with self.events_cache_lock:
            current_time = time.time()
            # 缓存有效期5秒
            if (self._events_cache is not None and 
                current_time - self._cache_timestamp < 5.0):
                return self._events_cache.copy()
            
            # 读取并更新缓存
            events = self._atomic_read(self.events_file, [])
            self._events_cache = events
            self._cache_timestamp = current_time
            return events.copy()
    
    def publish(self, event_type: str, payload: Dict, delay_seconds: int = 0) -> str:
        """
        发布事件到总线，使用原子写入确保数据完整性。
        
        Args:
            event_type: 事件类型（如：member_awake, task_completed, error_occurred）
            payload: 事件载荷（字典格式）
            delay_seconds: 延迟处理时间（秒）
            
        Returns:
            事件ID
        """
        with self.file_write_lock:
            # 生成事件ID（修复去重问题）
            event_id = self._generate_event_id(event_type, payload)
            
            # 检查是否已存在相同事件
            existing_events = self._get_events_with_cache()
            for event in existing_events:
                if event["id"] == event_id and not event.get("processed", False):
                    logger.debug(f"Event {event_id} already exists and is pending")
                    return event_id
            
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
            events = self._get_events_with_cache()
            
            # 添加新事件
            events.append(event)
            
            # 原子写入文件
            success = self._atomic_write(self.events_file, events)
            if success:
                # 更新缓存
                with self.events_cache_lock:
                    self._events_cache = events
                    self._cache_timestamp = time.time()
                
                logger.info(f"Event published: {event_type} (id: {event_id}) by {self.member_name}")
                return event_id
            else:
                logger.error(f"Failed to publish event: {event_type}")
                raise RuntimeError(f"Failed to publish event {event_type}")
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        订阅指定类型的事件。
        
        Args:
            event_type: 要订阅的事件类型
            callback: 事件处理回调函数，接收(event_dict)作为参数
        """
        with self.file_write_lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            # 检查是否已订阅
            for existing_callback in self.subscribers[event_type]:
                if existing_callback == callback:
                    logger.debug(f"Callback already subscribed to {event_type}")
                    return
            
            self.subscribers[event_type].append(callback)
            
            # 保存订阅信息到文件
            try:
                subscriptions = self._atomic_read(self.subscriptions_file, {})
            except Exception as e:
                logger.error(f"Failed to read subscriptions: {e}")
                subscriptions = {}
            
            if event_type not in subscriptions:
                subscriptions[event_type] = []
            
            # 记录订阅者信息
            subscriber_info = {
                "member": self.member_name,
                "subscribed_at": time.time(),
                "callback_id": id(callback)
            }
            
            # 检查是否已记录
            for sub in subscriptions[event_type]:
                if (sub.get("member") == self.member_name and 
                    sub.get("callback_id") == id(callback)):
                    logger.debug(f"Subscription already recorded for {self.member_name}")
                    break
            else:
                subscriptions[event_type].append(subscriber_info)
            
            # 原子写入订阅信息
            self._atomic_write(self.subscriptions_file, subscriptions)
            
            logger.info(f"Member {self.member_name} subscribed to {event_type}")
    
    def process_events(self, max_events: int = 10) -> int:
        """
        处理待处理的事件，优化锁使用。
        
        Args:
            max_events: 最大处理事件数量
            
        Returns:
            实际处理的事件数量
        """
        processed_count = 0
        
        with self.file_write_lock:
            # 读取事件（使用缓存）
            events = self._get_events_with_cache()
            
            current_time = time.time()
            events_to_process = []
            event_indices = []
            
            # 筛选需要处理的事件
            for idx, event in enumerate(events):
                if (not event.get("processed", False) and 
                    event["id"] not in self.processed_events and
                    event.get("process_after", 0) <= current_time):
                    events_to_process.append(event)
                    event_indices.append(idx)
            
            # 限制处理数量
            if len(events_to_process) > max_events:
                events_to_process = events_to_process[:max_events]
                event_indices = event_indices[:max_events]
            
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
                for idx in event_indices:
                    if idx < len(events):
                        events[idx]["processed"] = True
                
                # 原子写入文件
                success = self._atomic_write(self.events_file, events)
                if success:
                    # 更新缓存
                    with self.events_cache_lock:
                        self._events_cache = events
                        self._cache_timestamp = time.time()
                    
                    # 保存已处理事件
                    self._save_processed_events()
                else:
                    logger.error("Failed to save processed events")
            
            return processed_count
    
    def get_pending_events(self, event_type: str = None) -> List[Dict]:
        """
        获取待处理的事件，使用缓存优化。
        
        Args:
            event_type: 可选，指定事件类型
            
        Returns:
            待处理事件列表
        """
        events = self._get_events_with_cache()
        
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
        events = self._get_events_with_cache()
        
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
            "subscribers": {k: len(v) for k, v in self.subscribers.items()},
            "cache_hit": self._events_cache is not None
        }
    
    def clear_processed_events(self, older_than_days: int = 7):
        """
        清理已处理的事件。
        
        Args:
            older_than_days: 清理多少天前的已处理事件
        """
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        
        with self.file_write_lock:
            events = self._get_events_with_cache()
            
            # 过滤掉已处理且超过时间阈值的事件
            filtered_events = []
            events_to_remove = []
            
            for event in events:
                if (not event.get("processed", False) or 
                    event.get("timestamp", 0) > cutoff_time):
                    filtered_events.append(event)
                else:
                    events_to_remove.append(event["id"])
            
            # 更新文件
            if len(filtered_events) < len(events):
                success = self._atomic_write(self.events_file, filtered_events)
                if success:
                    # 更新缓存
                    with self.events_cache_lock:
                        self._events_cache = filtered_events
                        self._cache_timestamp = time.time()
                    
                    # 从已处理缓存中移除
                    for event_id in events_to_remove:
                        self.processed_events.discard(event_id)
                    
                    # 保存已处理事件缓存
                    self._save_processed_events()
                    
                    logger.info(f"Cleaned {len(events) - len(filtered_events)} processed events older than {older_than_days} days")
                else:
                    logger.error("Failed to clean processed events")
    
    @classmethod
    def get_instance(cls, member_name: str = "unknown", base_dir: str = None) -> 'EventBus':
        """
        获取事件总线实例（修复单例模式问题）。
        每个成员有独立的实例，相同成员返回相同实例。
        
        Args:
            member_name: 成员名称
            base_dir: 基础目录
            
        Returns:
            EventBus实例
        """
        with cls._instances_lock:
            # 构建实例键
            instance_key = f"{member_name}:{base_dir}" if base_dir else member_name
            
            if instance_key not in cls._instances:
                if base_dir:
                    cls._instances[instance_key] = cls(base_dir=base_dir, member_name=member_name)
                else:
                    cls._instances[instance_key] = cls(member_name=member_name)
            
            return cls._instances[instance_key]
    
    @classmethod
    def clear_instance(cls, member_name: str = None, base_dir: str = None):
        """
        清除事件总线实例缓存。
        
        Args:
            member_name: 成员名称，如果为None则清除所有实例
            base_dir: 基础目录
        """
        with cls._instances_lock:
            if member_name is None:
                cls._instances.clear()
                logger.info("Cleared all EventBus instances")
            else:
                # 构建实例键
                instance_key = f"{member_name}:{base_dir}" if base_dir else member_name
                if instance_key in cls._instances:
                    del cls._instances[instance_key]
                    logger.info(f"Cleared EventBus instance for {instance_key}")


# 向后兼容的函数
def get_event_bus(member_name: str = "unknown", base_dir: str = None) -> EventBus:
    """
    获取事件总线实例（兼容旧版本）。
    
    Args:
        member_name: 成员名称
        base_dir: 基础目录
        
    Returns:
        EventBus实例
    """
    return EventBus.get_instance(member_name=member_name, base_dir=base_dir)