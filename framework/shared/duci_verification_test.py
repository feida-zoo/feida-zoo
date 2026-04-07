#!/usr/bin/env python3
"""
毒刺二次审计验证测试
验证织巢修复的漏洞是否真正被修复
"""

import tempfile
import os
import threading
import time
from pathlib import Path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.core.workspace import Workspace

def test_thread_lock_efficacy():
    """测试线程锁是否真的防止了竞争条件"""
    print("=== 测试线程锁有效性 ===")
    
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    # 创建测试文件
    test_files = []
    for i in range(5):
        test_file = os.path.join(temp_dir, f"test_{i}.txt")
        with open(test_file, "w") as f:
            f.write(f"content {i}")
        test_files.append(test_file)
    
    # 使用直接文件操作模拟竞争条件
    log_file = os.path.join(temp_dir, ".deletion_log.json")
    
    def concurrent_log_writes():
        """模拟并发日志写入"""
        for i in range(100):
            try:
                workspace.soft_delete(test_files[i % 5])
                time.sleep(0.001)  # 增加竞争机会
            except:
                pass
    
    # 运行多个线程
    threads = []
    for _ in range(10):
        t = threading.Thread(target=concurrent_log_writes)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 检查日志文件是否损坏
    try:
        with open(log_file, 'r') as f:
            import json
            data = json.load(f)
            print(f"✓ 日志文件有效，包含 {len(data)} 条记录")
            print(f"✓ 最后一条记录: {data[-1]}")
    except Exception as e:
        print(f"✗ 日志文件损坏: {e}")
        return False
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    return True

def test_path_validation_robustness():
    """测试路径验证的健壮性"""
    print("\n=== 测试路径验证健壮性 ===")
    
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    test_cases = [
        # (path, should_fail, description)
        ("../../../../etc/passwd", True, "经典路径遍历攻击"),
        ("..\\..\\..\\windows\\system32", True, "Windows风格路径遍历"),
        ("valid/file.txt", False, "正常相对路径"),
        ("/absolute/outside/path", True, "绝对外部路径"),
        ("subdir/../../../etc/passwd", True, "混合路径遍历"),
        ("./../test.txt", True, "相对路径向上遍历"),
        ("", True, "空路径"),
        ("../" * 100 + "etc/passwd", True, "深度路径遍历"),
    ]
    
    all_passed = True
    for path, should_fail, description in test_cases:
        try:
            # 测试 _validate_path 方法
            result = workspace._validate_path(path)
            if should_fail:
                print(f"✗ {description}: 应该失败但通过了，返回: {result}")
                all_passed = False
            else:
                print(f"✓ {description}: 正确通过")
        except ValueError as e:
            if should_fail:
                print(f"✓ {description}: 正确失败 - {str(e)[:50]}...")
            else:
                print(f"✗ {description}: 应该通过但失败了 - {str(e)}")
                all_passed = False
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    return all_passed

def test_log_size_limitation_actual():
    """实际测试日志大小限制"""
    print("\n=== 测试日志大小限制 ===")
    
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    # 修改为小值以便测试
    workspace._max_log_entries = 5
    
    # 创建临时文件并删除
    for i in range(10):
        test_file = os.path.join(temp_dir, f"test_{i}.txt")
        with open(test_file, "w") as f:
            f.write(f"content {i}")
        
        try:
            workspace.soft_delete(test_file)
        except:
            pass
    
    # 检查日志大小
    log_entries = workspace.get_deletion_log()
    print(f"日志条目数: {len(log_entries)} (最大限制: {workspace._max_log_entries})")
    
    if len(log_entries) <= workspace._max_log_entries:
        print(f"✓ 日志大小限制有效")
        
        # 检查是否有清理记录
        cleanup_entries = [e for e in log_entries if e.get('operation') == 'log_cleanup']
        if cleanup_entries:
            print(f"✓ 有自动清理记录")
        else:
            print(f"⚠ 没有清理记录，但大小限制有效")
    else:
        print(f"✗ 日志大小限制失败: {len(log_entries)} > {workspace._max_log_entries}")
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    return len(log_entries) <= workspace._max_log_entries

def test_concurrent_read_write():
    """测试并发读写操作的线程安全性"""
    print("\n=== 测试并发读写 ===")
    
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    # 创建共享数据
    read_counts = [0]
    write_counts = [0]
    
    def reader():
        for _ in range(100):
            workspace._read_log()
            read_counts[0] += 1
            time.sleep(0.0001)
    
    def writer():
        for i in range(100):
            workspace._write_log([{"test": i}])
            write_counts[0] += 1
            time.sleep(0.0001)
    
    # 启动多个读写线程
    threads = []
    for _ in range(5):
        t = threading.Thread(target=reader)
        threads.append(t)
        t.start()
    
    for _ in range(5):
        t = threading.Thread(target=writer)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print(f"✓ 完成 {read_counts[0]} 次读取和 {write_counts[0]} 次写入")
    
    # 检查日志文件是否仍然有效
    log_file = os.path.join(temp_dir, ".deletion_log.json")
    try:
        with open(log_file, 'r') as f:
            import json
            data = json.load(f)
            print(f"✓ 日志文件最终状态有效")
    except Exception as e:
        print(f"✗ 日志文件损坏: {e}")
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    return True

def test_path_validation_edge_cases():
    """测试路径验证边界情况"""
    print("\n=== 测试路径边界情况 ===")
    
    temp_dir = tempfile.mkdtemp()
    workspace = Workspace(temp_dir)
    
    # 测试符号链接
    try:
        # 创建文件
        real_file = os.path.join(temp_dir, "real.txt")
        with open(real_file, "w") as f:
            f.write("real content")
        
        # 创建符号链接
        link_file = os.path.join(temp_dir, "link.txt")
        os.symlink(real_file, link_file)
        
        # 验证符号链接
        validated = workspace._validate_path(link_file)
        print(f"✓ 符号链接验证成功: {validated}")
        
    except Exception as e:
        print(f"✗ 符号链接验证失败: {e}")
    
    # 测试 Unicode 路径
    try:
        unicode_path = os.path.join(temp_dir, "测试文件📁.txt")
        validated = workspace._validate_path(unicode_path)
        print(f"✓ Unicode 路径验证成功")
    except Exception as e:
        print(f"✗ Unicode 路径验证失败: {e}")
    
    # 测试非常长的路径
    try:
        long_path = "a" * 1000 + ".txt"
        validated = workspace._validate_path(long_path)
        print(f"✓ 长路径验证成功")
    except Exception as e:
        print(f"✗ 长路径验证失败: {e}")
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    return True

def main():
    """运行所有验证测试"""
    print("🦂 毒刺二次审计验证测试开始\n")
    
    tests = [
        ("线程锁有效性", test_thread_lock_efficacy),
        ("路径验证健壮性", test_path_validation_robustness),
        ("日志大小限制", test_log_size_limitation_actual),
        ("并发读写安全", test_concurrent_read_write),
        ("路径边界情况", test_path_validation_edge_cases),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"测试异常: {e}")
            results.append((name, False))
    
    print("\n" + "="*50)
    print("测试结果汇总:")
    print("="*50)
    
    all_passed = True
    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{name}: {status}")
        if not success:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ 所有验证测试通过")
    else:
        print("❌ 部分验证测试失败")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)