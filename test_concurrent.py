#!/usr/bin/env python3
"""
并发安全测试
"""

import json
import tempfile
import threading
import time
from pathlib import Path
import random
import sys

# 添加当前目录到路径
sys.path.insert(0, '.')

from framework.core.registry_manager import RegistryManager


def test_basic_concurrent():
    """基础并发测试"""
    print("🧪 测试 RegistryManager 基础并发...")
    
    temp_dir = tempfile.TemporaryDirectory()
    registry_path = Path(temp_dir.name) / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    
    errors = []
    
    def worker(worker_id):
        for i in range(5):
            member_id = f"w{worker_id}m{i}"
            try:
                manager.register_member({
                    "id": member_id,
                    "name": f"Worker {worker_id} Member {i}",
                    "status": "active"
                })
                manager.save()
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")
    
    # 启动3个并发线程
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待
    for t in threads:
        t.join()
    
    # 结果
    final_members = manager.list_members()
    
    print(f"✅ 操作完成")
    print(f"   错误数: {len(errors)}")
    print(f"   最终成员: {len(final_members)} (期望: 15)")
    
    if errors:
        for err in errors:
            print(f"   ❌ {err}")
    
    # 验证数据一致性
    for i in range(3):
        for j in range(5):
            member_id = f"w{i}m{j}"
            member = manager.get_member(member_id)
            if not member:
                errors.append(f"数据丢失: {member_id}")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    return success


if __name__ == "__main__":
    success = test_basic_concurrent()
    sys.exit(0 if success else 1)