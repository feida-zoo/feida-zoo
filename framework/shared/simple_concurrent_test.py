#!/usr/bin/env python3
"""
简单并发测试脚本
测试 RegistryManager 的基本并发安全性
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


def test_concurrent_registry_writes():
    """测试注册表并发写入"""
    print("测试 RegistryManager 并发写入...")
    
    temp_dir = tempfile.TemporaryDirectory()
    registry_path = Path(temp_dir.name) / "registry.json"
    manager = RegistryManager(registry_path)
    manager.load()
    
    errors = []
    success_count = 0
    
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
    
    # 启动5个并发线程
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 验证结果
    if errors:
        print(f"发现 {len(errors)} 个并发写入错误")
        for err in errors[:5]:
            print(f"  - {err}")
    else:
        print(f"所有 {success_count} 个并发写入操作成功")
    
    # 验证最终状态
    final_members = manager.list_members()
    print(f"最终成员数量: {len(final_members)}")
    
    if len(final_members) != 50:  # 5 workers * 10 members
        print(f"⚠️  数据丢失: 期望 50 个成员, 实际 {len(final_members)} 个")
    
    temp_dir.cleanup()
    return len(errors) == 0


if __name__ == "__main__":
    success = test_concurrent_registry_writes()
    print(f"\n测试结果: {'通过' if success else '失败'}")
    sys.exit(0 if success else 1)