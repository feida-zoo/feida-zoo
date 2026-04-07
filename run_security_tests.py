#!/usr/bin/env python3
"""
运行安全修复测试
"""

import subprocess
import sys
from pathlib import Path

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*60}")
    print(f"运行测试: {test_file}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=Path(test_file).parent.parent,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"❌ 测试超时: {test_file}")
        return False
    except Exception as e:
        print(f"❌ 测试执行错误: {e}")
        return False

def main():
    """主函数"""
    print("🧪 开始运行P0安全漏洞修复测试")
    print("=" * 60)
    
    test_files = [
        "test_concurrent.py",
        "test_absolute_path.py",
        "test_path_traversal.py",
        "framework/tests/ut/test_registry_concurrent_lock.py",
        "framework/tests/ut/test_workspace_path_security.py",
    ]
    
    results = []
    all_passed = True
    
    for test_file in test_files:
        full_path = Path(__file__).parent / test_file
        if full_path.exists():
            passed = run_test(str(full_path))
            results.append((test_file, passed))
            if not passed:
                all_passed = False
        else:
            print(f"⚠️  测试文件不存在: {test_file}")
            results.append((test_file, False))
            all_passed = False
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结:")
    print(f"{'='*60}")
    
    for test_file, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_file}: {status}")
    
    print(f"\n总体结果: {'✅ 所有测试通过' if all_passed else '❌ 有测试失败'}")
    
    # 返回适当的退出码
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()