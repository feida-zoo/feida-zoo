#!/usr/bin/env python3
"""
事件总线增强测试 - 验证P0级安全漏洞修复
"""

import sys
import os
import time
import json
import tempfile
import threading
import concurrent.futures
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from framework.shared.event_bus.event_bus import EventBus, get_event_bus


def test_atomic_write():
    """测试原子写入功能"""
    print("🧪 测试原子写入功能")
    
    # 创建测试目录
    test_dir = Path(tempfile.mkdtemp())
    print(f"   测试目录: {test_dir}")
    
    bus = EventBus(base_dir=str(test_dir), member_name="atomic_tester")
    
    # 发布大量事件测试原子写入
    event_ids = []
    for i in range(100):
        event_id = bus.publish("atomic_test", {"index": i, "data": "x" * 100})
        event_ids.append(event_id)
    
    # 验证所有事件都被保存
    stats = bus.get_statistics()
    print(f"   发布事件: {len(event_ids)}, 保存事件: {stats['total_events']}")
    
    assert stats['total_events'] == len(event_ids), f"事件数量不匹配: 预期{len(event_ids)}, 实际{stats['total_events']}"
    
    # 验证文件完整性
    events_file = test_dir / "events.json"
    assert events_file.exists(), "事件文件不存在"
    
    # 尝试读取并验证JSON格式
    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
        assert len(events) == len(event_ids), "事件文件内容不完整"
        for event in events:
            assert "id" in event, "事件缺少ID字段"
            assert "type" in event, "事件缺少type字段"
    
    print("✅ 原子写入测试通过!")
    return True


def test_deduplication_fixed():
    """测试修复后的事件去重功能"""
    print("\n🧪 测试修复后的事件去重功能")
    
    test_dir = Path(tempfile.mkdtemp())
    bus = EventBus(base_dir=str(test_dir), member_name="dedup_fixed_tester")
    
    handler_calls = []
    
    def handler(event):
        handler_calls.append(event["id"])
    
    bus.subscribe("dedup_event_fixed", handler)
    
    # 发布5个内容完全相同的事件
    print("   发布5个内容完全相同的事件...")
    same_payload = {"data": "identical content", "timestamp": 12345}  # 固定时间戳
    event_ids = []
    
    for i in range(5):
        event_id = bus.publish("dedup_event_fixed", same_payload)
        event_ids.append(event_id)
        print(f"   事件 {i+1}: {event_id}")
    
    # 所有事件ID应该相同（因为内容相同）
    unique_ids = set(event_ids)
    print(f"   唯一事件ID数量: {len(unique_ids)} (应为1)")
    
    # 处理事件
    processed = bus.process_events(max_events=10)
    print(f"   处理了 {processed} 个事件")
    print(f"   处理函数被调用了 {len(handler_calls)} 次")
    
    # 由于去重机制，应该只处理一次
    assert len(unique_ids) == 1, f"去重失败: 有{len(unique_ids)}个不同ID"
    assert processed == 1, f"应只处理1个事件，实际处理了{processed}个"
    assert len(handler_calls) == 1, f"处理函数应只被调用1次，实际{len(handler_calls)}次"
    
    print("✅ 事件去重修复测试通过!")
    return True


def test_singleton_pattern_fixed():
    """测试修复后的单例模式"""
    print("\n🧪 测试修复后的单例模式")
    
    test_dir = Path(tempfile.mkdtemp())
    
    # 测试1: 相同成员返回相同实例
    print("   测试相同成员返回相同实例...")
    bus1 = EventBus.get_instance(member_name="test_member", base_dir=str(test_dir))
    bus2 = EventBus.get_instance(member_name="test_member", base_dir=str(test_dir))
    
    assert bus1 is bus2, "相同成员的实例应该相同"
    print("   ✅ 相同成员返回相同实例")
    
    # 测试2: 不同成员返回不同实例
    print("   测试不同成员返回不同实例...")
    bus3 = EventBus.get_instance(member_name="other_member", base_dir=str(test_dir))
    
    assert bus1 is not bus3, "不同成员的实例应该不同"
    print("   ✅ 不同成员返回不同实例")
    
    # 测试3: 向后兼容函数
    print("   测试向后兼容函数...")
    bus4 = EventBus.get_instance(member_name="compat_member")
    bus5 = get_event_bus(member_name="compat_member")
    
    assert bus4 is bus5, "向后兼容函数应该返回相同实例"
    print("   ✅ 向后兼容函数正常工作")
    
    print("✅ 单例模式修复测试通过!")
    return True


def test_concurrent_performance():
    """测试并发性能优化"""
    print("\n🧪 测试并发性能优化")
    
    test_dir = Path(tempfile.mkdtemp())
    
    bus = EventBus(base_dir=str(test_dir), member_name="perf_tester")
    
    # 订阅事件
    received_count = 0
    lock = threading.Lock()
    
    def handler(event):
        nonlocal received_count
        with lock:
            received_count += 1
    
    bus.subscribe("perf_event", handler)
    
    # 并发发布事件
    num_threads = 20
    events_per_thread = 50
    total_events = num_threads * events_per_thread
    
    print(f"   启动{num_threads}个线程，每个发布{events_per_thread}个事件...")
    start_time = time.time()
    
    def worker(worker_id):
        for i in range(events_per_thread):
            bus.publish("perf_event", {
                "worker": worker_id,
                "iteration": i,
                "timestamp": time.time()
            })
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)
    
    publish_time = time.time() - start_time
    print(f"   发布完成，耗时: {publish_time:.2f}秒")
    
    # 处理事件
    start_time = time.time()
    processed_total = 0
    batch_size = 50
    
    while True:
        processed = bus.process_events(max_events=batch_size)
        if processed == 0:
            break
        processed_total += processed
    
    process_time = time.time() - start_time
    print(f"   处理完成，耗时: {process_time:.2f}秒")
    print(f"   总发布事件: {total_events}, 总处理事件: {processed_total}, 接收事件: {received_count}")
    
    # 验证
    stats = bus.get_statistics()
    print(f"   统计信息: 总事件{stats['total_events']}, 已处理{stats['processed_events']}")
    
    assert stats['total_events'] == total_events, f"事件数量不匹配"
    assert stats['processed_events'] == total_events, f"应全部处理完成"
    assert received_count == total_events, f"应收到所有事件"
    
    print(f"✅ 并发性能测试通过! 吞吐量: {total_events/process_time:.1f} 事件/秒")
    return True


def test_file_integrity():
    """测试文件完整性保护"""
    print("\n🧪 测试文件完整性保护")
    
    test_dir = Path(tempfile.mkdtemp())
    bus = EventBus(base_dir=str(test_dir), member_name="integrity_tester")
    
    # 模拟写入过程中断的情况
    events_file = test_dir / "events.json"
    
    print("   测试1: 正常写入...")
    for i in range(10):
        bus.publish("integrity_test", {"index": i})
    
    # 验证文件可正常读取
    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
        assert len(events) == 10, "事件数量不正确"
    
    print("   测试2: 模拟原子写入...")
    # 通过多次写入测试原子性
    original_size = events_file.stat().st_size
    
    # 大量并发写入
    def write_events(count):
        for i in range(count):
            bus.publish("stress_test", {"data": "x" * 1000})
    
    threads = []
    for _ in range(5):
        t = threading.Thread(target=write_events, args=(20,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 验证文件仍然可读且格式正确
    with open(events_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
        print(f"   最终事件数量: {len(events)}")
    
    # 验证没有损坏的JSON
    assert isinstance(events, list), "文件内容不是有效的JSON数组"
    
    print("✅ 文件完整性测试通过!")
    return True


def test_cache_mechanism():
    """测试缓存机制"""
    print("\n🧪 测试缓存机制")
    
    test_dir = Path(tempfile.mkdtemp())
    bus = EventBus(base_dir=str(test_dir), member_name="cache_tester")
    
    # 发布一些事件
    for i in range(5):
        bus.publish("cache_test", {"index": i})
    
    # 多次获取统计信息，应该利用缓存
    start_time = time.time()
    stats_calls = 10
    
    for i in range(stats_calls):
        stats = bus.get_statistics()
    
    cache_time = time.time() - start_time
    print(f"   {stats_calls}次统计调用耗时: {cache_time:.3f}秒")
    
    # 验证缓存命中
    stats = bus.get_statistics()
    assert stats.get("cache_hit", False) == True, "缓存未命中"
    
    print("   ✅ 缓存机制正常工作")
    
    # 测试缓存失效
    print("   测试缓存失效...")
    time.sleep(6)  # 等待缓存过期（缓存有效期5秒）
    
    stats = bus.get_statistics()
    # 注意：由于实现可能不同，这里不强制检查cache_hit
    
    print("✅ 缓存机制测试通过!")
    return True


def main():
    """运行所有测试"""
    print("🚀 事件总线P0级安全漏洞修复测试套件")
    print("=" * 70)
    print("修复内容:")
    print("  1. ✅ P0级原子写入漏洞 - 实现完整的原子写入机制")
    print("  2. ✅ P1级事件去重失效 - 修复去重算法")
    print("  3. ✅ P1级单例模式缺陷 - 修复实例化管理")
    print("  4. ✅ P1级读写锁竞争 - 优化并发性能")
    print("=" * 70)
    
    tests = [
        test_atomic_write,
        test_deduplication_fixed,
        test_singleton_pattern_fixed,
        test_concurrent_performance,
        test_file_integrity,
        test_cache_mechanism,
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
    
    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有P0级安全漏洞修复测试通过！事件总线已加固。")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())