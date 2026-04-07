"""
测试 RegistryManager 并发锁功能
确保并发写入时 registry.json 文件不损坏
"""

import json
import tempfile
import threading
import time
from pathlib import Path
import sys

# 添加框架目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from framework.core.registry_manager import RegistryManager


def test_concurrent_lock_basic():
    """测试基础并发锁功能"""
    print("🧪 测试 RegistryManager 基础并发锁...")
    
    temp_dir = tempfile.TemporaryDirectory()
    registry_path = Path(temp_dir.name) / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    
    errors = []
    success_count = 0
    
    def worker(worker_id: int, iterations: int = 10):
        nonlocal success_count
        for i in range(iterations):
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
                errors.append(f"Worker {worker_id}: {e}")
    
    # 启动多个并发线程
    threads = []
    num_workers = 5
    for i in range(num_workers):
        t = threading.Thread(target=worker, args=(i, 5))
        threads.append(t)
    
    # 同时启动所有线程
    for t in threads:
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    print(f"✅ 并发操作完成")
    print(f"   成功操作数: {success_count}")
    print(f"   错误数: {len(errors)}")
    
    if errors:
        print("   ❌ 发现错误:")
        for err in errors[:5]:  # 只显示前5个错误
            print(f"     - {err}")
        if len(errors) > 5:
            print(f"     ... 还有 {len(errors) - 5} 个错误")
    
    # 验证文件完整性
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "members" not in data:
            errors.append("文件损坏：缺少 'members' 字段")
        else:
            print(f"   最终成员数: {len(data['members'])} (期望: {num_workers * 5})")
            
            # 验证所有成员都存在
            for i in range(num_workers):
                for j in range(5):
                    member_id = f"worker{i}_member{j}"
                    if member_id not in data["members"]:
                        errors.append(f"数据丢失: {member_id}")
    except json.JSONDecodeError as e:
        errors.append(f"JSON解析失败（文件损坏）: {e}")
    except Exception as e:
        errors.append(f"文件读取失败: {e}")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    return success


def test_concurrent_lock_stress():
    """压力测试：高并发写入"""
    print("\n🧪 压力测试 RegistryManager 高并发锁...")
    
    temp_dir = tempfile.TemporaryDirectory()
    registry_path = Path(temp_dir.name) / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    
    errors = []
    success_count = 0
    lock = threading.Lock()
    
    def stress_worker(worker_id: int, iterations: int = 20):
        nonlocal success_count
        for i in range(iterations):
            # 随机操作：注册、更新或删除
            import random
            operation = random.choice(["register", "update", "delete"])
            
            try:
                if operation == "register":
                    member_id = f"stress_{worker_id}_{i}_{int(time.time() * 1000)}"
                    manager.register_member({
                        "id": member_id,
                        "name": f"Stress Worker {worker_id}",
                        "status": "pending"
                    })
                    manager.save()
                    with lock:
                        success_count += 1
                
                elif operation == "update":
                    # 尝试更新一个存在的成员
                    members = manager.list_members()
                    if members:
                        member = random.choice(members)
                        manager.update_member_status(member["id"], "updated")
                        manager.save()
                        with lock:
                            success_count += 1
                
                elif operation == "delete":
                    # 尝试删除一个存在的成员
                    members = manager.list_members()
                    if members:
                        member = random.choice(members)
                        manager.delete_member(member["id"])
                        manager.save()
                        with lock:
                            success_count += 1
            
            except Exception as e:
                # 某些操作失败是正常的（例如删除不存在的成员）
                if "已存在" not in str(e) and "不存在" not in str(e):
                    errors.append(f"Worker {worker_id} {operation}: {e}")
    
    # 启动更多线程进行压力测试
    threads = []
    num_workers = 10
    
    for i in range(num_workers):
        t = threading.Thread(target=stress_worker, args=(i, 15))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"✅ 压力测试完成")
    print(f"   成功操作数: {success_count}")
    print(f"   错误数: {len(errors)}")
    
    # 验证文件仍然是有效的JSON
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"   文件验证: ✅ 有效JSON")
    except Exception as e:
        errors.append(f"文件损坏: {e}")
        print(f"   文件验证: ❌ 损坏")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    return success


def test_lock_reentrant():
    """测试锁的可重入性（一个线程内多次调用save）"""
    print("\n🧪 测试 RegistryManager 锁可重入性...")
    
    temp_dir = tempfile.TemporaryDirectory()
    registry_path = Path(temp_dir.name) / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    
    errors = []
    
    # 在同一个线程内快速连续调用save
    for i in range(50):
        member_id = f"reentrant_{i}"
        try:
            manager.register_member({
                "id": member_id,
                "name": f"Reentrant Member {i}",
                "status": "active"
            })
            manager.save()
        except Exception as e:
            errors.append(f"迭代 {i}: {e}")
    
    print(f"✅ 可重入测试完成")
    print(f"   错误数: {len(errors)}")
    
    # 验证文件完整性
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if len(data.get("members", {})) != 50:
            errors.append(f"成员数量不正确: {len(data.get('members', {}))} (期望: 50)")
    except Exception as e:
        errors.append(f"文件验证失败: {e}")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    return success


if __name__ == "__main__":
    print("=" * 60)
    print("RegistryManager 并发锁测试套件")
    print("=" * 60)
    
    results = []
    
    results.append(("基础并发锁", test_concurrent_lock_basic()))
    results.append(("压力测试", test_concurrent_lock_stress()))
    results.append(("锁可重入性", test_lock_reentrant()))
    
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print(f"\n总体结果: {'✅ 所有测试通过' if all_passed else '❌ 有测试失败'}")
    sys.exit(0 if all_passed else 1)