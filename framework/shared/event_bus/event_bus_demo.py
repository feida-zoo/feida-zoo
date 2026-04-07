#!/usr/bin/env python3
"""
Event Bus 演示脚本

展示事件总线的使用方式，包括发布、订阅和处理事件。
"""

import sys
import os
import time
import threading
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from framework.shared.event_bus.event_bus import EventBus, get_event_bus

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_usage():
    """演示基本使用方式"""
    print("=" * 60)
    print("演示 1: 基本使用方式")
    print("=" * 60)
    
    # 创建事件总线实例
    bus = EventBus(member_name="demo_user")
    
    # 定义事件处理函数
    def task_completed_handler(event):
        print(f"[处理任务完成事件] 任务: {event['payload']['task_name']}, 结果: {event['payload']['result']}")
    
    def error_handler(event):
        print(f"[处理错误事件] 错误: {event['payload']['error']}, 位置: {event['payload']['location']}")
    
    # 订阅事件
    bus.subscribe("task_completed", task_completed_handler)
    bus.subscribe("error_occurred", error_handler)
    
    # 发布事件
    task_id = bus.publish("task_completed", {
        "task_name": "数据导入",
        "result": "成功",
        "duration_seconds": 120
    })
    print(f"已发布任务完成事件: {task_id}")
    
    error_id = bus.publish("error_occurred", {
        "error": "文件未找到",
        "location": "/path/to/data.csv",
        "severity": "warning"
    })
    print(f"已发布错误事件: {error_id}")
    
    # 处理事件
    processed = bus.process_events()
    print(f"已处理 {processed} 个事件")
    
    # 显示统计信息
    stats = bus.get_statistics()
    print(f"统计信息: 总事件={stats['total_events']}, 待处理={stats['pending_events']}")
    
    print()


def demo_multiple_members():
    """演示多成员场景"""
    print("=" * 60)
    print("演示 2: 多成员场景")
    print("=" * 60)
    
    # 创建多个成员的事件总线
    panda_bus = EventBus(member_name="panda")
    ant_bus = EventBus(member_name="ant")
    hedgehog_bus = EventBus(member_name="hedgehog")
    
    # 熊猫订阅任务事件
    def panda_task_handler(event):
        print(f"[熊猫] 收到任务事件: {event['payload']['description']}")
    
    # 蚂蚁订阅错误事件
    def ant_error_handler(event):
        print(f"[蚂蚁] 收到错误事件: {event['payload']['error']}")
    
    # 刺猬订阅所有事件
    def hedgehog_all_handler(event):
        print(f"[刺猬] 收到 {event['type']} 事件: {event['publisher']}")
    
    panda_bus.subscribe("new_task", panda_task_handler)
    ant_bus.subscribe("error", ant_error_handler)
    hedgehog_bus.subscribe("new_task", hedgehog_all_handler)
    hedgehog_bus.subscribe("error", hedgehog_all_handler)
    
    # 熊猫发布新任务
    task_id = panda_bus.publish("new_task", {
        "description": "处理用户数据",
        "priority": "high",
        "assignee": "ant"
    })
    print(f"熊猫发布了新任务: {task_id}")
    
    # 蚂蚁发布错误
    error_id = ant_bus.publish("error", {
        "error": "内存不足",
        "suggestion": "清理缓存"
    })
    print(f"蚂蚁发布了错误: {error_id}")
    
    # 各成员处理事件
    print("\n各成员处理事件:")
    for name, bus_instance in [("熊猫", panda_bus), ("蚂蚁", ant_bus), ("刺猬", hedgehog_bus)]:
        processed = bus_instance.process_events()
        print(f"{name}: 处理了 {processed} 个事件")
    
    print()


def demo_delayed_events():
    """演示延迟事件"""
    print("=" * 60)
    print("演示 3: 延迟事件")
    print("=" * 60)
    
    bus = EventBus(member_name="scheduler")
    
    def reminder_handler(event):
        print(f"[提醒] {event['payload']['message']}")
    
    bus.subscribe("reminder", reminder_handler)
    
    # 发布一个5秒后处理的延迟事件
    reminder_id = bus.publish("reminder", {
        "message": "该开会了！",
        "meeting": "每日站会"
    }, delay_seconds=5)
    
    print(f"已发布延迟提醒事件 (ID: {reminder_id})，将在5秒后处理")
    print("等待5秒...")
    
    # 立即处理（应该没有事件）
    processed = bus.process_events()
    print(f"立即处理: 处理了 {processed} 个事件")
    
    # 等待5秒
    time.sleep(5)
    
    # 再次处理
    processed = bus.process_events()
    print(f"5秒后处理: 处理了 {processed} 个事件")
    
    print()


def demo_concurrent_access():
    """演示并发访问"""
    print("=" * 60)
    print("演示 4: 并发访问")
    print("=" * 60)
    
    bus = EventBus(member_name="concurrent_test")
    
    results = []
    
    def result_handler(event):
        results.append(event['payload']['result'])
        print(f"收到结果: {event['payload']['result']}")
    
    bus.subscribe("calculation_result", result_handler)
    
    # 并发发布事件
    def publish_events(worker_id):
        for i in range(3):
            bus.publish("calculation_result", {
                "worker": worker_id,
                "result": f"worker_{worker_id}_result_{i}",
                "timestamp": time.time()
            })
            time.sleep(0.1)  # 稍微延迟以模拟并发
    
    # 创建多个线程并发发布事件
    threads = []
    for i in range(3):
        t = threading.Thread(target=publish_events, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    print(f"所有工作线程已完成，共发布了 {3*3} 个事件")
    
    # 处理事件
    total_processed = 0
    while True:
        processed = bus.process_events()
        if processed == 0:
            break
        total_processed += processed
    
    print(f"总共处理了 {total_processed} 个事件")
    print(f"收到 {len(results)} 个结果")
    
    print()


def demo_event_deduplication():
    """演示事件去重"""
    print("=" * 60)
    print("演示 5: 事件去重")
    print("=" * 60)
    
    bus = EventBus(member_name="dedup_test")
    
    call_count = 0
    
    def duplicate_handler(event):
        nonlocal call_count
        call_count += 1
        print(f"处理重复事件 #{call_count}: {event['payload']['data']}")
    
    bus.subscribe("duplicate_test", duplicate_handler)
    
    # 发布相同内容的多个事件
    print("发布5个内容相同的事件...")
    for i in range(5):
        bus.publish("duplicate_test", {
            "data": "相同的内容",
            "index": i
        })
    
    # 处理事件
    processed = bus.process_events()
    print(f"处理了 {processed} 个事件，处理函数被调用了 {call_count} 次")
    print("注意：由于去重机制，相同内容的事件只会被处理一次")
    
    print()


def demo_singleton_pattern():
    """演示单例模式"""
    print("=" * 60)
    print("演示 6: 单例模式")
    print("=" * 60)
    
    # 使用全局单例
    bus1 = get_event_bus("singleton_user")
    bus2 = get_event_bus("another_user")  # 应该返回同一个实例
    
    print(f"bus1 id: {id(bus1)}")
    print(f"bus2 id: {id(bus2)}")
    print(f"是同一个实例: {bus1 is bus2}")
    
    # 即使成员名不同，也返回同一个实例（第一个调用的成员名）
    print(f"bus1 成员名: {bus1.member_name}")
    print(f"bus2 成员名: {bus2.member_name}")
    
    print()


def demo_statistics_and_cleanup():
    """演示统计和清理功能"""
    print("=" * 60)
    print("演示 7: 统计和清理功能")
    print("=" * 60)
    
    bus = EventBus(member_name="stats_demo")
    
    # 发布一些测试事件
    for i in range(10):
        bus.publish("test_event", {"index": i})
    
    # 处理一半事件
    for i in range(5):
        bus.process_events()
    
    # 获取统计信息
    stats = bus.get_statistics()
    print("统计信息:")
    print(f"  总事件数: {stats['total_events']}")
    print(f"  已处理事件: {stats['processed_events']}")
    print(f"  待处理事件: {stats['pending_events']}")
    print(f"  已处理事件缓存: {stats['processed_events_cache']}")
    
    print("\n按事件类型统计:")
    for event_type, type_stats in stats['event_types'].items():
        print(f"  {event_type}: 总数={type_stats['total']}, 已处理={type_stats['processed']}")
    
    # 显示待处理事件
    pending = bus.get_pending_events()
    print(f"\n待处理事件: {len(pending)} 个")
    
    # 清理演示（这里不会真正清理，因为事件都是新的）
    print("\n执行清理（清理7天前的已处理事件）...")
    bus.clear_processed_events(older_than_days=7)
    
    # 再次获取统计
    stats_after = bus.get_statistics()
    print(f"清理后总事件数: {stats_after['total_events']}")
    
    print()


def main():
    """主函数"""
    print("🚀 飝龘动物园 - 事件总线演示")
    print("=" * 60)
    
    # 运行所有演示
    demos = [
        demo_basic_usage,
        demo_multiple_members,
        demo_delayed_events,
        demo_concurrent_access,
        demo_event_deduplication,
        demo_singleton_pattern,
        demo_statistics_and_cleanup,
    ]
    
    for i, demo in enumerate(demos, 1):
        try:
            demo()
            time.sleep(1)  # 演示间暂停
        except Exception as e:
            print(f"演示 {i} 出错: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print("✅ 所有演示完成！")
    print("\n事件总线特性总结:")
    print("1. ✅ 基于文件系统的持久化存储")
    print("2. ✅ 发布/订阅模式")
    print("3. ✅ 异步处理（支持延迟事件）")
    print("4. ✅ 并发安全（文件锁）")
    print("5. ✅ 事件去重")
    print("6. ✅ 多成员支持")
    print("7. ✅ 统计和监控")
    print("8. ✅ 自动清理")
    
    # 显示最终文件状态
    print("\n生成的文件:")
    base_dir = os.path.join(os.path.dirname(__file__))
    for file in ["events.json", "subscriptions.json", "processed_events.json"]:
        file_path = os.path.join(base_dir, file)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  {file}: {size} 字节")
        else:
            print(f"  {file}: 不存在")


if __name__ == "__main__":
    main()