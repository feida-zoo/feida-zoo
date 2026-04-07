#!/usr/bin/env python3
"""
验证 RegistryManager 修复
"""

import tempfile
import threading
import time
from pathlib import Path
import json
import sys

sys.path.insert(0, '.')
from framework.core.registry_manager import RegistryManager

print("🧪 验证 RegistryManager 原子写入和文件锁修复")
print("=" * 60)

# 测试1: 基本功能测试
print("1. 基本功能测试...")
temp_dir = tempfile.TemporaryDirectory()
registry_path = Path(temp_dir.name) / "registry.json"

manager = RegistryManager(registry_path)
manager.load()

# 注册成员
try:
    manager.register_member({
        "id": "test1",
        "name": "Test Member",
        "status": "active"
    })
    manager.save()
    print("  ✅ 注册和保存成功")
except Exception as e:
    print(f"  ❌ 注册失败: {e}")

# 读取验证
try:
    member = manager.get_member("test1")
    if member and member["id"] == "test1":
        print("  ✅ 读取验证成功")
    else:
        print("  ❌ 读取验证失败")
except Exception as e:
    print(f"  ❌ 读取验证失败: {e}")

temp_dir.cleanup()

# 测试2: 线程安全测试
print("\n2. 线程安全测试...")
temp_dir = tempfile.TemporaryDirectory()
registry_path = Path(temp_dir.name) / "registry.json"

errors = []
success_count = 0

def thread_worker(worker_id):
    global success_count
    local_manager = RegistryManager(registry_path)
    local_manager.load()
    
    for i in range(10):
        try:
            member_id = f"worker{worker_id}_member{i}"
            local_manager.register_member({
                "id": member_id,
                "name": f"Worker {worker_id}",
                "status": "active"
            })
            local_manager.save()
            success_count += 1
        except Exception as e:
            errors.append(f"Worker {worker_id}: {e}")

threads = []
for i in range(5):
    t = threading.Thread(target=thread_worker, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(f"  成功操作: {success_count}")
print(f"  错误数: {len(errors)}")

# 验证文件完整性
manager = RegistryManager(registry_path)
manager.load()
members = manager.list_members()
print(f"  最终成员数: {len(members)} (期望: 50)")

if len(members) == 50:
    print("  ✅ 数据完整性验证成功")
else:
    print(f"  ❌ 数据完整性验证失败，有数据丢失")

temp_dir.cleanup()

# 测试3: 文件锁测试
print("\n3. 文件锁测试...")
temp_dir = tempfile.TemporaryDirectory()
registry_path = Path(temp_dir.name) / "registry.json"

# 创建两个独立的管理器实例（模拟两个进程）
manager1 = RegistryManager(registry_path)
manager2 = RegistryManager(registry_path)

manager1.load()
manager2.load()

# 同时操作
def manager1_worker():
    for i in range(5):
        try:
            manager1.register_member({
                "id": f"m1_{i}",
                "name": f"Manager1 Member {i}",
                "status": "active"
            })
            manager1.save()
            time.sleep(0.01)  # 稍微延迟
        except Exception as e:
            print(f"  Manager1 错误: {e}")

def manager2_worker():
    for i in range(5):
        try:
            manager2.register_member({
                "id": f"m2_{i}",
                "name": f"Manager2 Member {i}",
                "status": "active"
            })
            manager2.save()
            time.sleep(0.01)  # 稍微延迟
        except Exception as e:
            print(f"  Manager2 错误: {e}")

t1 = threading.Thread(target=manager1_worker)
t2 = threading.Thread(target=manager2_worker)

t1.start()
t2.start()

t1.join()
t2.join()

# 验证结果
manager = RegistryManager(registry_path)
manager.load()
members = manager.list_members()
print(f"  最终成员数: {len(members)} (期望: 10)")

if len(members) == 10:
    print("  ✅ 文件锁测试成功（无数据损坏）")
else:
    print(f"  ❌ 文件锁测试失败，成员数: {len(members)}")

temp_dir.cleanup()

print("=" * 60)
print("✅ 修复验证完成")