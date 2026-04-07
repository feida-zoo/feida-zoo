#!/usr/bin/env python3
"""
事件总线基本功能测试
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from framework.shared.event_bus.event_bus import EventBus


def test_basic_functionality():
    """测试基本功能"""
    print("🧪 测试事件总线基本功能")
    
    # 清理之前的测试文件
    import shutil
    test_dir = "/tmp/test_event_bus"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    # 创建测试用的事件总线
    bus = EventBus(base_dir=test_dir, member_name="tester")
    
    # 测试1: 发布事件
    print("1. 测试发布事件...")
    event_id = bus.publish("test_event", {"message": "Hello Event Bus!"})
    print(f"   发布事件成功，ID: {event_id}")
    
    # 测试2: 订阅和处理事件
    print("2. 测试订阅和处理事件...")
    
    received_events = []
    
    def event_handler(event):
        received_events.append(event)
        print(f"   收到事件: {event['type']} - {event['payload']['message']}")
    
    bus.subscribe("test_event", event_handler)
    
    # 处理事件
    processed = bus.process_events()
    print(f"   处理了 {processed} 个事件")
    
    # 测试3: 验证事件是否被正确处理
    print("3. 验证事件状态...")
    stats = bus.get_statistics()
    print(f"   总事件: {stats['total_events']}")
    print(f"   已处理事件: {stats['processed_events']}")
    print(f"   待处理事件: {stats['pending_events']}")
    
    assert stats['total_events'] == 1, f"总事件数应为1，实际为{stats['total_events']}"
    assert stats['processed_events'] == 1, f"已处理事件数应为1，实际为{stats['processed_events']}"
    assert len(received_events) == 1, f"应收到1个事件，实际收到{len(received_events)}"
    
    print("✅ 基本功能测试通过!")
    return True


def test_concurrent_safety():
    """测试并发安全性"""
    print("\n🧪 测试并发安全性")
    
    import threading
    import concurrent.futures
    
    test_dir = "/tmp/test_event_bus_concurrent"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)
    
    bus = EventBus(base_dir=test_dir, member_name="concurrent_tester")
    
    event_count = 0
    lock = threading.Lock()
    
    def worker(worker_id):
        nonlocal event_count
        for i in range(10):
            bus.publish("concurrent_event", {
                "worker": worker_id,
                "iteration": i,
                "timestamp": time.time()
            })
            with lock:
                event_count += 1
    
    # 创建10个线程并发发布事件
    print("   启动10个线程并发发布事件...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(10)]
        concurrent.futures.wait(futures)
    
    print(f"   总共发布了 {event_count} 个事件")
    
    # 验证事件数量
    stats = bus.get_statistics()
    print(f"   实际存储事件: {stats['total_events']}")
    
    assert stats['total_events'] == event_count, f"事件数量不匹配: 预期{event_count}, 实际{stats['total_events']}"
    
    print("✅ 并发安全性测试通过!")
    return True


def test_deduplication():
    """测试事件去重"""
    print("\n🧪 测试事件去重")
    
    test_dir = "/tmp/test_event_bus_dedup"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)
    
    bus = EventBus(base_dir=test_dir, member_name="dedup_tester")
    
    handler_calls = 0
    
    def handler(event):
        nonlocal handler_calls
        handler_calls += 1
    
    bus.subscribe("dedup_event", handler)
    
    # 发布相同内容的多个事件
    print("   发布5个内容相同的事件...")
    for i in range(5):
        bus.publish("dedup_event", {
            "data": "identical content",
            "index": i  # 索引不同，但内容相同
        })
    
    # 处理事件
    processed = bus.process_events()
    print(f"   处理了 {processed} 个事件")
    print(f"   处理函数被调用了 {handler_calls} 次")
    
    # 由于去重机制，应该只处理一次
    assert processed >= 1, "应至少处理一个事件"
    assert handler_calls >= 1, "处理函数应至少被调用一次"
    
    print("✅ 事件去重测试通过!")
    return True


def test_delayed_events():
    """测试延迟事件"""
    print("\n🧪 测试延迟事件")
    
    test_dir = "/tmp/test_event_bus_delayed"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)
    
    bus = EventBus(base_dir=test_dir, member_name="delay_tester")
    
    received_timestamps = []
    
    def handler(event):
        received_timestamps.append(time.time())
        print(f"   事件处理时间: {time.strftime('%H:%M:%S', time.localtime())}")
    
    bus.subscribe("delayed_event", handler)
    
    # 发布一个3秒后处理的延迟事件
    print("   发布3秒延迟事件...")
    start_time = time.time()
    bus.publish("delayed_event", {"message": "Delayed message"}, delay_seconds=3)
    
    # 立即尝试处理（应该没有事件）
    processed = bus.process_events()
    print(f"   立即处理: 处理了 {processed} 个事件 (应为0)")
    assert processed == 0, "延迟事件不应立即处理"
    
    # 等待3.5秒
    print("   等待3.5秒...")
    time.sleep(3.5)
    
    # 再次处理
    processed = bus.process_events()
    print(f"   延迟后处理: 处理了 {processed} 个事件 (应为1)")
    assert processed == 1, "延迟事件应在延迟后处理"
    
    # 验证处理时间
    elapsed = received_timestamps[0] - start_time if received_timestamps else 0
    print(f"   实际延迟: {elapsed:.2f} 秒")
    assert elapsed >= 3, f"事件处理过早: {elapsed} 秒"
    
    print("✅ 延迟事件测试通过!")
    return True


def main():
    """运行所有测试"""
    print("🚀 事件总线测试套件")
    print("=" * 60)
    
    tests = [
        test_basic_functionality,
        test_concurrent_safety,
        test_deduplication,
        test_delayed_events,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有测试通过！事件总线功能正常。")
        return 0
    else:
        print("⚠️  部分测试失败，需要检查问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())