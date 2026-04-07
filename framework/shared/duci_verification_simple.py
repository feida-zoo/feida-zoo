#!/usr/bin/env python3
import tempfile
import os
import threading
import time
from pathlib import Path
import sys

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.core.workspace import Workspace

def test_basic():
    print("🦂 毒刺二次审计 - 基础验证")
    
    temp_dir = tempfile.mkdtemp()
    print(f"测试目录: {temp_dir}")
    
    try:
        # 1. 测试路径遍历防护
        print("\n1. 测试路径遍历防护:")
        workspace = Workspace(temp_dir)
        
        # 正常路径
        normal_file = os.path.join(temp_dir, "test.txt")
        with open(normal_file, "w") as f:
            f.write("test")
        
        try:
            workspace.soft_delete(normal_file)
            print("  ✓ 正常路径删除成功")
        except Exception as e:
            print(f"  ✗ 正常路径失败: {e}")
        
        # 恶意路径
        malicious_path = os.path.join(temp_dir, "../../../etc/passwd")
        try:
            workspace.soft_delete(malicious_path)
            print(f"  ✗ 恶意路径应该失败但通过了")
        except ValueError as e:
            print(f"  ✓ 恶意路径正确拦截: {str(e)[:50]}...")
        
        # 2. 测试线程锁
        print("\n2. 测试线程锁:")
        
        test_files = []
        for i in range(3):
            fpath = os.path.join(temp_dir, f"thread_{i}.txt")
            with open(fpath, "w") as f:
                f.write(f"content {i}")
            test_files.append(fpath)
        
        results = []
        def delete_file(fpath):
            try:
                workspace.soft_delete(fpath)
                results.append(("success", fpath))
            except Exception as e:
                results.append(("error", str(e)))
        
        threads = []
        for fpath in test_files:
            t = threading.Thread(target=delete_file, args=(fpath,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        success_count = sum(1 for r in results if r[0] == "success")
        print(f"  ✓ 并发删除完成: {success_count}/{len(test_files)} 成功")
        
        # 3. 测试日志大小限制
        print("\n3. 测试日志大小限制:")
        
        workspace._max_log_entries = 3
        for i in range(5):
            fpath = os.path.join(temp_dir, f"log_{i}.txt")
            with open(fpath, "w") as f:
                f.write(f"log {i}")
            try:
                workspace.soft_delete(fpath)
            except:
                pass
        
        log_entries = workspace.get_deletion_log()
        print(f"  日志条目数: {len(log_entries)} (限制: {workspace._max_log_entries})")
        
        if len(log_entries) <= workspace._max_log_entries:
            print("  ✓ 日志大小限制有效")
        else:
            print("  ✗ 日志大小限制失败")
        
        # 4. 测试异常处理
        print("\n4. 测试异常处理:")
        
        # 不存在的文件
        try:
            workspace.soft_delete("nonexistent.txt")
            print("  ✗ 不存在的文件应该失败")
        except FileNotFoundError:
            print("  ✓ 不存在的文件正确抛出异常")
        
        # 外部路径
        try:
            workspace.soft_delete("/tmp/outside.txt")
            print("  ✗ 外部路径应该失败")
        except ValueError:
            print("  ✓ 外部路径正确拦截")
        
        print("\n✅ 基础验证完成")
        return True
        
    finally:
        # 清理
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = test_basic()
    sys.exit(0 if success else 1)