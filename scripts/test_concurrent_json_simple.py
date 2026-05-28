#!/usr/bin/env python3
"""
简单并发 JSON 文件损坏测试
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path


def test_concurrent_json_write():
    """测试并发 JSON 写入"""
    print("🧪 测试并发 JSON 写入...")
    
    temp_dir = tempfile.TemporaryDirectory()
    file_path = Path(temp_dir.name) / "test.json"
    
    # 初始数据
    initial_data = {"members": {}, "version": "1.0.0"}
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, indent=2)
    
    errors = []
    operations = 0
    
    def worker(worker_id):
        nonlocal errors, operations
        for i in range(50):
            try:
                # 读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 修改
                member_id = f"worker{worker_id}_member{i}"
                data["members"][member_id] = {"id": member_id, "worker": worker_id}
                
                # 写入
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
                operations += 1
            except json.JSONDecodeError as e:
                errors.append(f"Worker {worker_id} iteration {i}: {e}")
            except Exception as e:
                if "No such file" not in str(e) and "Resource temporarily unavailable" not in str(e):
                    errors.append(f"Worker {worker_id} iteration {i}: {e}")
    
    # 启动多个线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
    
    # 启动
    for t in threads:
        t.start()
    
    # 等待
    for t in threads:
        t.join(timeout=2.0)
    
    # 验证最终文件
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
        
        print(f"✅ 操作数: {operations}")
        print(f"✅ 错误数: {len(errors)}")
        print(f"✅ 最终成员数: {len(final_data.get('members', {}))}")
        
        if errors:
            print(f"⚠️  错误示例: {errors[:3]}")
        
        return len(errors) == 0
    except Exception as e:
        print(f"❌ 最终文件损坏: {e}")
        return False


def test_file_locking():
    """测试文件锁"""
    print("🧪 测试文件锁...")
    
    temp_dir = tempfile.TemporaryDirectory()
    file_path = Path(temp_dir.name) / "locked.json"
    
    lock_acquired = [False, False]
    
    def worker1():
        try:
            # 尝试获取文件锁
            import fcntl
            with open(file_path, 'a') as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired[0] = True
                time.sleep(0.1)
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass
    
    def worker2():
        try:
            import fcntl
            with open(file_path, 'a') as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired[1] = True
                time.sleep(0.05)
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass
    
    t1 = threading.Thread(target=worker1)
    t2 = threading.Thread(target=worker2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    print(f"✅ Worker1 获取锁: {lock_acquired[0]}")
    print(f"✅ Worker2 获取锁: {lock_acquired[1]}")
    
    # 至少一个应该成功
    return any(lock_acquired)


def test_atomic_write():
    """测试原子写入"""
    print("🧪 测试原子写入...")
    
    temp_dir = tempfile.TemporaryDirectory()
    file_path = Path(temp_dir.name) / "atomic.json"
    
    errors = []
    
    def atomic_write(data):
        """原子写入：先写入临时文件，然后重命名"""
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, file_path)  # 原子操作
            return True
        except Exception as e:
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            raise e
    
    def worker(worker_id):
        for i in range(20):
            try:
                # 读取
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = {"members": {}, "version": "1.0.0"}
                
                # 修改
                member_id = f"atomic_{worker_id}_{i}"
                data["members"][member_id] = {"id": member_id, "atomic": True}
                
                # 原子写入
                atomic_write(data)
            except Exception as e:
                errors.append(f"Worker {worker_id} iteration {i}: {e}")
    
    # 启动多个线程
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
    
    # 启动
    for t in threads:
        t.start()
    
    # 等待
    for t in threads:
        t.join(timeout=2.0)
    
    # 验证
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
        print(f"✅ 原子写入测试完成，错误数: {len(errors)}")
        print(f"✅ 最终成员数: {len(final_data.get('members', {}))}")
        return len(errors) == 0
    else:
        print("❌ 文件不存在")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("🦂 简单并发 JSON 测试")
    print("=" * 80)
    
    tests = [
        ("并发 JSON 写入测试", test_concurrent_json_write),
        ("文件锁测试", test_file_locking),
        ("原子写入测试", test_atomic_write),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        try:
            result = test_func()
            results.append(result)
            print(f"  {'✅ 通过' if result else '❌ 失败'}")
        except Exception as e:
            print(f"  ❌ 测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，需要修复。")