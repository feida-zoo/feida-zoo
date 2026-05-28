#!/usr/bin/env python3
"""
运行现有测试以确保兼容性
"""

import subprocess
import sys
import os
from pathlib import Path

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n运行测试: {test_file}")
    
    # 设置PYTHONPATH
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).parent) + ':' + env.get('PYTHONPATH', '')
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=Path(__file__).parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout:
            print(result.stdout[:500])  # 只显示前500字符
        
        if result.returncode == 0:
            print(f"✅ 通过: {test_file}")
            return True
        else:
            print(f"❌ 失败: {test_file}")
            if result.stderr:
                print("错误输出:", result.stderr[:500])
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ 超时: {test_file}")
        return False
    except Exception as e:
        print(f"❌ 错误: {test_file} - {e}")
        return False

def main():
    """主函数"""
    print("🧪 运行现有测试以确保兼容性")
    print("=" * 60)
    
    test_files = [
        "framework/tests/ut/test_workspace_manager.py",
        "framework/tests/ut/test_spawner_refactored.py",
        "framework/tests/st/test_workspace_lifecycle.py",
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
    
    # 总结
    print(f"\n{'='*60}")
    print("兼容性测试总结:")
    print(f"{'='*60}")
    
    for test_file, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_file}: {status}")
    
    if results:
        all_passed = all(passed for _, passed in results)
        print(f"\n总体结果: {'✅ 所有测试通过' if all_passed else '❌ 有测试失败'}")
    else:
        print(f"\n⚠️  未运行任何测试")
        all_passed = False
    
    # 返回适当的退出码
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()