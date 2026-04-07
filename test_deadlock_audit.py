#!/usr/bin/env python3
"""
毒刺 🦂 死锁审计脚本
专门测试 RegistryManager 的 RLock 实现和并发安全性
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from framework.core.registry_manager import RegistryManager


class DeadlockAuditor:
    """死锁审计器"""
    
    def __init__(self):
        self.passed_tests = 0
        self.failed_tests = 0
        self.errors = []
    
    def test_rlock_reentrancy(self):
        """测试 RLock 可重入性"""
        print("🧪 测试 RLock 可重入性...")
        
        temp_dir = tempfile.TemporaryDirectory()
        registry_path = Path(temp_dir.name) / "registry.json"
        manager = RegistryManager(registry_path)
        manager.load()
        
        # 测试基本可重入性
        with manager._lock:
            # 第一次获取锁
            print("  ✅ 外层锁获取成功")
            
            # 尝试嵌套获取（应该成功，因为这是 RLock）
            with manager._lock:
                print("  ✅ 嵌套锁获取成功")
                
                # 再嵌套一层
                with manager._lock:
                    print("  ✅ 三层嵌套锁获取成功")
                    
                    # 在锁内执行操作
                    manager.register_member({"id": "test1", "name": "Test1"})
                    print("  ✅ 在锁内注册成员成功")
        
        # 验证结果
        if manager.member_count == 1:
            print("✅ RLock 可重入性测试通过")
            self.passed_tests += 1
            return True
        else:
            print(f"❌ RLock 可重入性测试失败，成员数: {manager.member_count}")
            self.failed_tests += 1
            return False
    
    def test_concurrent_nested_calls(self):
        """测试并发嵌套调用"""
        print("🧪 测试并发嵌套调用...")
        
        temp_dir = tempfile.TemporaryDirectory()
        registry_path = Path(temp_dir.name) / "registry.json"
        
        results = []
        errors = []
        
        def nested_worker(worker_id, registry_path):
            """工作线程：模拟复杂嵌套调用"""
            manager = RegistryManager(registry_path)
            manager.load()
            
            try:
                # 复杂嵌套场景
                for i in range(10):
                    member_id = f"worker{worker_id}_member{i}"
                    
                    # 嵌套调用模式
                    with manager._lock:
                        # 注册成员
                        manager.register_member({
                            "id": member_id,
                            "name": f"Worker {worker_id} Member {i}",
                            "status": "active"
                        })
                        
                        # 嵌套更新
                        manager.update_member(member_id, {"iteration": i})
                        
                        # 嵌套保存
                        if i % 3 == 0:
                            manager.save()
                        
                        # 嵌套读取
                        member = manager.get_member(member_id)
                        if member is None:
                            errors.append(f"Worker {worker_id}: 成员 {member_id} 未找到")
                
                results.append(True)
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")
                results.append(False)
        
        # 创建并启动多个线程
        threads = []
        num_workers = 15
        
        for i in range(num_workers):
            t = threading.Thread(target=nested_worker, args=(i, registry_path))
            t.daemon = True
            threads.append(t)
        
        # 同时启动所有线程
        for t in threads:
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join(timeout=5.0)
        
        # 加载最终状态验证
        final_manager = RegistryManager(registry_path)
        final_manager.load()
        
        success_count = sum(1 for r in results if r)
        
        print(f"  ✅ 成功线程: {success_count}/{num_workers}")
        print(f"  ✅ 最终成员数: {final_manager.member_count}")
        print(f"  ✅ 错误数: {len(errors)}")
        
        if errors:
            print(f"  ⚠️  错误示例: {errors[:3]}")
        
        # 检查文件完整性
        if registry_path.exists():
            try:
                with open(registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"  ✅ JSON 文件完整性验证通过")
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON 文件损坏: {e}")
                self.errors.append(f"JSON损坏: {e}")
                self.failed_tests += 1
                return False
        
        if success_count > 0 and final_manager.member_count > 0:
            print("✅ 并发嵌套调用测试通过")
            self.passed_tests += 1
            return True
        else:
            print("❌ 并发嵌套调用测试失败")
            self.failed_tests += 1
            return False
    
    def test_circular_deadlock_scenario(self):
        """测试循环死锁场景"""
        print("🧪 测试循环死锁场景...")
        
        temp_dir = tempfile.TemporaryDirectory()
        registry_path = Path(temp_dir.name) / "registry.json"
        
        # 创建两个管理器实例（模拟不同组件）
        manager1 = RegistryManager(registry_path)
        manager2 = RegistryManager(registry_path)
        manager1.load()
        manager2.load()
        
        deadlock_detected = False
        completed = False
        
        def worker1():
            nonlocal deadlock_detected, completed
            try:
                # 获取 manager1 锁
                with manager1._lock:
                    time.sleep(0.01)  # 让 worker2 有机会获取锁
                    
                    # 尝试获取 manager2 锁（模拟交叉依赖）
                    # 注意：这是模拟死锁场景，RLock 应该能防止这种情况
                    with manager2._lock:
                        manager1.register_member({"id": "from_worker1", "name": "Worker1"})
                        manager2.save()  # 会获取自己的锁
                
                completed = True
            except Exception as e:
                print(f"  Worker1 错误: {e}")
        
        def worker2():
            nonlocal deadlock_detected
            try:
                # 获取 manager2 锁
                with manager2._lock:
                    time.sleep(0.01)  # 让 worker1 有机会获取锁
                    
                    # 尝试获取 manager1 锁
                    with manager1._lock:
                        manager2.register_member({"id": "from_worker2", "name": "Worker2"})
                        manager1.save()
            except Exception as e:
                print(f"  Worker2 错误: {e}")
        
        # 启动线程
        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.daemon = True
        t2.daemon = True
        
        t1.start()
        t2.start()
        
        # 等待或超时
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        
        if not completed:
            print("  ⚠️  可能发生死锁或超时")
            # 检查是否是死锁
            if t1.is_alive() or t2.is_alive():
                print("  ❌ 检测到线程死锁！")
                deadlock_detected = True
            else:
                print("  ✅ 线程正常结束（无死锁）")
        else:
            print("  ✅ 操作完成，无死锁")
        
        if deadlock_detected:
            print("❌ 循环死锁测试失败（检测到死锁）")
            self.failed_tests += 1
            return False
        else:
            print("✅ 循环死锁测试通过（无死锁）")
            self.passed_tests += 1
            return True
    
    def test_file_corruption_under_load(self):
        """测试高负载下的文件损坏"""
        print("🧪 测试高负载下的文件损坏...")
        
        temp_dir = tempfile.TemporaryDirectory()
        registry_path = Path(temp_dir.name) / "registry.json"
        
        operations_count = 0
        corruption_count = 0
        
        def stress_worker(worker_id, stop_event):
            nonlocal operations_count, corruption_count
            manager = RegistryManager(registry_path)
            
            while not stop_event.is_set():
                try:
                    # 随机操作
                    import random
                    op_type = random.choice(['register', 'update', 'delete', 'save'])
                    
                    with manager._lock:
                        manager.load()  # 重新加载确保最新状态
                        
                        if op_type == 'register':
                            member_id = f"stress_{worker_id}_{operations_count}"
                            manager.register_member({
                                "id": member_id,
                                "name": f"Stress Test {operations_count}",
                                "timestamp": time.time()
                            })
                            operations_count += 1
                        
                        elif op_type == 'update' and manager.member_count > 0:
                            # 随机更新一个成员
                            members = list(manager._registry.get("members", {}).keys())
                            if members:
                                member_id = random.choice(members)
                                manager.update_member(member_id, {
                                    "updated": time.time(),
                                    "worker": worker_id
                                })
                                operations_count += 1
                        
                        elif op_type == 'delete' and manager.member_count > 0:
                            # 随机删除一个成员
                            members = list(manager._registry.get("members", {}).keys())
                            if members:
                                member_id = random.choice(members)
                                manager.delete_member(member_id)
                                operations_count += 1
                        
                        elif op_type == 'save':
                            manager.save()
                            operations_count += 1
                            
                            # 验证保存后的文件
                            try:
                                with open(registry_path, 'r', encoding='utf-8') as f:
                                    json.load(f)
                            except json.JSONDecodeError:
                                corruption_count += 1
                
                except Exception as e:
                    # 忽略竞争条件导致的特定错误
                    if "已存在" not in str(e) and "不存在" not in str(e):
                        print(f"  Worker {worker_id} 错误: {e}")
        
        # 创建停止事件
        stop_event = threading.Event()
        
        # 启动高压力线程
        threads = []
        num_workers = 20
        
        for i in range(num_workers):
            t = threading.Thread(target=stress_worker, args=(i, stop_event))
            t.daemon = True
            threads.append(t)
        
        # 启动
        for t in threads:
            t.start()
        
        # 运行一段时间
        time.sleep(3.0)  # 3秒高压力测试
        
        # 停止
        stop_event.set()
        
        # 等待线程结束
        for t in threads:
            t.join(timeout=1.0)
        
        # 最终验证
        final_manager = RegistryManager(registry_path)
        final_manager.load()
        
        print(f"  ✅ 总操作数: {operations_count}")
        print(f"  ✅ 最终成员数: {final_manager.member_count}")
        print(f"  ✅ 文件损坏次数: {corruption_count}")
        
        # 验证最终文件
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                final_data = json.load(f)
            
            # 检查基本结构
            assert isinstance(final_data, dict), "数据应该是字典"
            assert "members" in final_data, "应该包含 members 字段"
            assert "version" in final_data, "应该包含 version 字段"
            
            print(f"  ✅ 最终文件完整性验证通过")
            
            if corruption_count == 0:
                print("✅ 高负载文件损坏测试通过")
                self.passed_tests += 1
                return True
            else:
                print(f"❌ 高负载文件损坏测试失败，检测到 {corruption_count} 次损坏")
                self.failed_tests += 1
                return False
                
        except Exception as e:
            print(f"❌ 最终文件验证失败: {e}")
            self.failed_tests += 1
            return False
    
    def run_all_tests(self):
        """运行所有死锁测试"""
        print("=" * 80)
        print("🦂 毒刺死锁审计开始")
        print("=" * 80)
        
        tests = [
            ("RLock 可重入性测试", self.test_rlock_reentrancy),
            ("并发嵌套调用测试", self.test_concurrent_nested_calls),
            ("循环死锁场景测试", self.test_circular_deadlock_scenario),
            ("高负载文件损坏测试", self.test_file_corruption_under_load),
        ]
        
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            try:
                test_func()
            except Exception as e:
                print(f"💥 测试异常: {e}")
                self.failed_tests += 1
        
        # 总结
        print("\n" + "=" * 80)
        print("📊 死锁审计结果总结")
        print("=" * 80)
        print(f"✅ 通过: {self.passed_tests}")
        print(f"❌ 失败: {self.failed_tests}")
        
        if self.errors:
            print(f"\n⚠️  错误列表:")
            for error in self.errors[:5]:
                print(f"  - {error}")
        
        if self.failed_tests == 0:
            print("\n🎉 所有死锁测试通过！RLock 实现正确，无死锁风险。")
            return True
        else:
            print("\n⚠️  部分死锁测试失败，需要进一步检查。")
            return False


if __name__ == "__main__":
    auditor = DeadlockAuditor()
    success = auditor.run_all_tests()
    exit(0 if success else 1)