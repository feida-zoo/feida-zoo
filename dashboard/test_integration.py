#!/usr/bin/env python3
# Zoo Dev-Center 集成测试脚本

import subprocess
import time
import sys
import json
from pathlib import Path

def run_command(cmd, cwd=None):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

def test_git_adapter():
    """测试 Git 适配器"""
    print("🧪 测试 Git 适配器...")
    
    cmd = "python3 -c \"import sys; sys.path.append('.'); from dashboard.git_adapter import GitAdapter; adapter = GitAdapter(); print('Git适配器初始化成功'); commits = adapter.get_recent_commits(limit=2); print(f'获取到{len(commits)}条提交记录')\""
    
    stdout, stderr, code = run_command(cmd, cwd="/home/afei/workspace/code/feida_zoo")
    
    if code == 0 and "Git适配器初始化成功" in stdout:
        print("✅ Git 适配器测试通过")
        return True
    else:
        print(f"❌ Git 适配器测试失败: {stderr}")
        return False

def test_server_api():
    """测试服务器 API"""
    print("🧪 测试服务器 API...")
    
    # 检查服务器是否运行
    stdout, stderr, code = run_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:18792/api/system-info")
    
    if stdout == "200":
        print("✅ 服务器运行正常")
        
        # 测试各个API端点
        endpoints = [
            ("系统信息", "/api/system-info"),
            ("看板数据", "/api/kanban"),
            ("任务统计", "/api/task-stats"),
            ("Git时间线", "/api/git-timeline"),
        ]
        
        all_passed = True
        for name, endpoint in endpoints:
            stdout, stderr, code = run_command(f"curl -s http://localhost:18792{endpoint}")
            if code == 0 and stdout:
                try:
                    data = json.loads(stdout)
                    print(f"  ✅ {name} API 正常")
                except:
                    print(f"  ⚠️ {name} API 返回非JSON数据")
                    all_passed = False
            else:
                print(f"  ❌ {name} API 失败: {stderr}")
                all_passed = False
        
        return all_passed
    else:
        print("❌ 服务器未运行或响应异常")
        return False

def test_static_files():
    """测试静态文件"""
    print("🧪 测试静态文件...")
    
    files = [
        "static/dev_center.css",
        "static/dev_center.js",
        "templates/dev_center.html"
    ]
    
    all_exist = True
    for file_path in files:
        full_path = Path("/home/afei/workspace/code/feida_zoo/dashboard") / file_path
        if full_path.exists():
            print(f"  ✅ {file_path} 存在")
        else:
            print(f"  ❌ {file_path} 不存在")
            all_exist = False
    
    return all_exist

def main():
    print("🚀 Zoo Dev-Center v1.0 集成测试")
    print("=" * 50)
    
    tests = [
        ("Git 适配器", test_git_adapter),
        ("静态文件", test_static_files),
        ("服务器 API", test_server_api),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！Zoo Dev-Center v1.0 第一阶段开发完成")
        print("\n🌐 访问地址: http://localhost:18792")
        print("📚 详细文档: dashboard/README.md")
        return 0
    else:
        print("⚠️  部分测试未通过，请检查问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())