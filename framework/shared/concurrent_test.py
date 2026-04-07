#!/usr/bin/env python3
"""
并发安全测试脚本
用于测试 RegistryManager 和 WorkspaceManager 的并发读写安全性
"""

import json
import tempfile
import threading
import time
from pathlib import Path
import random
import sys
import os

# 添加框架路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.core.registry_manager import RegistryManager
from framework.core.workspace_manager import WorkspaceManager


class ConcurrentTestRunner:
    """并发测试运行器"""
    
    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.results = {"errors": [], "successes": 0, "total": 0}
        
    def test_registry_concurrent_writes(self):
        """测试注册表并发写入"""
        print("🧪 测试 RegistryManager 并发写入...")
        
        registry_path = self.base_path / "registry.json"
        manager = RegistryManager(registry_path)
        manager.load()
        
        errors = []
        success_count = 0
        total_operations = 100
        
        def worker(worker_id):
            nonlocal success_count
            for i in range(10):
                member_id = f"worker{worker_id}_member{i}"
                try:
                    manager.register_member({
                        "id": member_id,
                        "name": f"Worker {worker_id} Member {i}",
                        "status": "active"
                    })
                    manager.save()
                    success_count += 1
                except Exception as e:
                    errors.append(f"Worker {worker_id} - {member_id}: {e}")
        
        # 启动10个并发线程
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证结果
        if errors:
            print(f"❌ 发现 {len(errors)} 个并发写入错误")
            for err in errors[:5]:  # 只显示前5个错误
                print(f"  - {err}")
            if len(errors) > 5:
                print(f"  ... 还有 {len(errors)-5} 个错误")
        else:
            print(f"✅ 所有 {success_count} 个并发写入操作成功")
        
        # 验证最终状态
        final_members = manager.list_members()
        print(f"📊 最终成员数量: {len(final_members)} (期望: {total_operations})")
        
        if len(final_members) != total_operations:
            print(f"⚠️  数据丢失: 期望 {total_operations} 个成员, 实际 {len(final_members)} 个")
            
        self.results["errors"].extend(errors)
        self.results["successes"] += success_count
        self.results["total"] += total_operations
        
        return len(errors) == 0
    
    def test_workspace_concurrent_creation(self):
        """测试工作区并发创建"""
        print("\n🧪 测试 WorkspaceManager 并发创建工作区...")
        
        agents_path = self.base_path / "agents"
        manager = WorkspaceManager(agents_path)
        
        errors = []
        success_count = 0
        total_operations = 50
        
        def worker(worker_id):
            nonlocal success_count
            for i in range(5):
                member_id = f"worker{worker_id}_ws{i}"
                try:
                    # 检查是否已存在（模拟并发检查）
                    if not manager.workspace_exists(member_id):
                        manager.create_workspace(member_id)
                        
                        # 保存测试元数据
                        meta = {
                            "id": member_id,
                            "worker": worker_id,
                            "created": time.time()
                        }
                        manager.save_meta(member_id, meta)
                        success_count += 1
                    
                    # 模拟读取操作
                    meta = manager.load_meta(member_id)
                    if meta:
                        # 验证数据完整性
                        assert meta["id"] == member_id
                        assert meta["worker"] == worker_id
                except Exception as e:
                    errors.append(f"Worker {worker_id} - {member_id}: {e}")
        
        # 启动10个并发线程
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证结果
        if errors:
            print(f"❌ 发现 {len(errors)} 个并发工作区错误")
            for err in errors[:5]:
                print(f"  - {err}")
            if len(errors) > 5:
                print(f"  ... 还有 {len(errors)-5} 个错误")
        else:
            print(f"✅ 所有 {success_count} 个工作区操作成功")
        
        # 验证目录结构
        workspace_ids = manager.list_workspace_ids()
        print(f"📊 最终工作区数量: {len(workspace_ids)}")
        
        for ws_id in workspace_ids:
            ws_path = manager.get_workspace_path(ws_id)
            if not ws_path.exists():
                errors.append(f"工作区目录不存在: {ws_id}")
            else:
                # 验证标准子目录
                for subdir in ["src", "docs", "outputs"]:
                    subdir_path = ws_path / subdir
                    if not subdir_path.exists():
                        errors.append(f"工作区 {ws_id} 缺少子目录: {subdir}")
        
        self.results["errors"].extend(errors)
        self.results["successes"] += success_count
        self.results["total"] += total_operations
        
        return len(errors) == 0
    
    def test_file_lock_behavior(self):
        """测试文件锁行为"""
        print("\n🧪 测试文件锁和并发读写...")
        
        # 创建测试文件
        test_file = self.base_path / "test_lock.json"
        test_file.write_text('{"data": [], "version": "1.0"}')
        
        errors = []
        read_count = [0]
        write_count = [0]
        
        def reader(reader_id):
            for i in range(20):
                try:
                    # 模拟读取延迟
                    time.sleep(random.uniform(0.001, 0.005))
                    
                    with open(test_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    read_count[0] += 1
                    
                    # 验证数据完整性
                    if "data" not in data:
                        errors.append(f"Reader {reader_id} 读取到损坏数据")
                        
                except Exception as e:
                    errors.append(f"Reader {reader_id} 读取错误: {e}")
        
        def writer(writer_id):
            for i in range(10):
                try:
                    # 模拟写入延迟
                    time.sleep(random.uniform(0.002, 0.01))
                    
                    with open(test_file, 'r+', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 添加新数据
                        if "data" not in data:
                            data["data"] = []
                        data["data"].append({"writer": writer_id, "index": i})
                        
                        # 写回文件
                        f.seek(0)
                        f.truncate()
                        json.dump(data, f, indent=2)
                    
                    write_count[0] += 1
                    
                except Exception as e:
                    errors.append(f"Writer {writer_id} 写入错误: {e}")
        
        # 启动读写线程
        threads = []
        
        # 5个读线程
        for i in range(5):
            t = threading.Thread(target=reader, args=(i,))
            threads.append(t)
            t.start()
        
        # 3个写线程
        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证结果
        if errors:
            print(f"❌ 发现 {len(errors)} 个并发读写错误")
            for err in errors[:3]:
                print(f"  - {err}")
            if len(errors) > 3:
                print(f"  ... 还有 {len(errors)-3} 个错误")
        else:
            print(f"✅ 并发读写测试通过")
        
        print(f"📊 读取操作: {read_count[0]}, 写入操作: {write_count[0]}")
        
        # 验证最终数据
        with open(test_file, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
        
        expected_items = 30  # 3个写线程 * 10次写入
        actual_items = len(final_data.get("data", []))
        
        print(f"📊 数据项: 期望 {expected_items}, 实际 {actual_items}")
        
        if actual_items != expected_items:
            errors.append(f"数据丢失: 期望 {expected_items} 项, 实际 {actual_items} 项")
        
        self.results["errors"].extend(errors)
        return len(errors) == 0
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🚀 开始并发安全审计测试")
        print("=" * 60)
        
        start_time = time.time()
        
        test_results = {
            "registry_writes": self.test_registry_concurrent_writes(),
            "workspace_creation": self.test_workspace_concurrent_creation(),
            "file_lock": self.test_file_lock_behavior(),
        }
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("📋 测试结果汇总")
        print("=" * 60)
        
        for test_name, passed in test_results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"{test_name:30} {status}")
        
        print(f"\n📊 操作统计:")
        print(f"  成功操作: {self.results['successes']}")
        print(f"  总操作数: {self.results['total']}")
        print(f"  错误数量: {len(self.results['errors'])}")
        print(f"  测试时间: {elapsed_time:.2f}秒")
        
        if self.results['errors']:
            print(f"\n⚠️  发现 {len(self.results['errors'])} 个错误:")
            for i, error in enumerate(self.results['errors'][:10], 1):
                print(f"  {i}. {error}")
            if len(self.results['errors']) > 10:
                print(f"  ... 还有 {len(self.results['errors']) - 10} 个错误")
        
        all_passed = all(test_results.values())
        print(f"\n{'🎉 所有测试通过' if all_passed else '❌ 测试失败'}")
        
        return all_passed


if __name__ == "__main__":
    runner = ConcurrentTestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)