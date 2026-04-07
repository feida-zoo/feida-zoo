"""
测试 WorkspaceManager 路径安全功能
防止绝对路径逃逸和路径遍历攻击
"""

import tempfile
from pathlib import Path
import sys
import os

# 添加框架目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from framework.core.workspace_manager import WorkspaceManager


def test_path_security_basic():
    """测试基础路径安全功能"""
    print("🧪 测试 WorkspaceManager 基础路径安全...")
    
    temp_dir = tempfile.TemporaryDirectory()
    manager = WorkspaceManager(temp_dir.name)
    
    test_cases = [
        # (member_id, should_succeed, description)
        ("normal_member", True, "正常成员ID"),
        ("member_with_underscore", True, "带下划线的成员ID"),
        ("member-with-dash", True, "带连字符的成员ID"),
        ("member.with.dots", True, "带点的成员ID"),
        ("123member456", True, "数字开头结尾的成员ID"),
        ("Member123_Test-456.789", True, "复杂但安全的成员ID"),
    ]
    
    errors = []
    
    for member_id, should_succeed, description in test_cases:
        try:
            path = manager.get_workspace_path(member_id)
            if should_succeed:
                print(f"  ✅ {description}: '{member_id}' -> {path}")
                
                # 验证路径没有逃逸
                try:
                    path.relative_to(Path(temp_dir.name).resolve())
                except ValueError:
                    errors.append(f"路径逃逸: {member_id} -> {path}")
            else:
                errors.append(f"预期失败但成功: {member_id}")
                print(f"  ❌ {description}: 预期失败但成功")
                
        except ValueError as e:
            if not should_succeed:
                print(f"  ✅ {description}: 正确拒绝 '{member_id}' - {str(e)[:50]}...")
            else:
                errors.append(f"预期成功但失败: {member_id} - {e}")
                print(f"  ❌ {description}: 错误拒绝 '{member_id}'")
        except Exception as e:
            errors.append(f"意外错误: {member_id} - {e}")
            print(f"  ❌ {description}: 意外错误 '{member_id}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


def test_path_traversal_attacks():
    """测试路径遍历攻击防护"""
    print("\n🧪 测试路径遍历攻击防护...")
    
    temp_dir = tempfile.TemporaryDirectory()
    base_path = Path(temp_dir.name).resolve()
    manager = WorkspaceManager(temp_dir.name)
    
    # 各种路径遍历攻击尝试
    attack_cases = [
        # (攻击字符串, 描述)
        ("../evil", "简单路径遍历"),
        ("../../../../etc/passwd", "多层路径遍历"),
        ("normal/../evil", "混合路径遍历"),
        ("./../evil", "当前目录路径遍历"),
        ("normal/../../evil", "嵌套路径遍历"),
        ("..\\evil", "Windows风格路径遍历"),
        ("normal\\..\\evil", "Windows混合路径遍历"),
    ]
    
    errors = []
    
    for attack_string, description in attack_cases:
        try:
            path = manager.get_workspace_path(attack_string)
            errors.append(f"未阻止攻击: {description} '{attack_string}' -> {path}")
            print(f"  ❌ {description}: 未阻止攻击 '{attack_string}'")
        except ValueError as e:
            print(f"  ✅ {description}: 正确阻止 '{attack_string}' - {str(e)[:50]}...")
        except Exception as e:
            errors.append(f"意外错误: {attack_string} - {e}")
            print(f"  ❌ {description}: 意外错误 '{attack_string}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


def test_absolute_path_attacks():
    """测试绝对路径攻击防护"""
    print("\n🧪 测试绝对路径攻击防护...")
    
    temp_dir = tempfile.TemporaryDirectory()
    manager = WorkspaceManager(temp_dir.name)
    
    # 绝对路径攻击尝试
    absolute_attacks = [
        ("/etc/passwd", "Unix绝对路径"),
        ("C:\\Windows\\System32", "Windows绝对路径"),
        ("/tmp/evil", "临时目录绝对路径"),
        ("/home/user/.ssh/id_rsa", "用户目录绝对路径"),
        ("//server/share", "网络路径"),
        ("\\\\server\\share", "Windows网络路径"),
    ]
    
    errors = []
    
    for attack_string, description in absolute_attacks:
        try:
            path = manager.get_workspace_path(attack_string)
            errors.append(f"未阻止绝对路径: {description} '{attack_string}' -> {path}")
            print(f"  ❌ {description}: 未阻止绝对路径 '{attack_string}'")
        except ValueError as e:
            print(f"  ✅ {description}: 正确阻止绝对路径 '{attack_string}' - {str(e)[:50]}...")
        except Exception as e:
            errors.append(f"意外错误: {attack_string} - {e}")
            print(f"  ❌ {description}: 意外错误 '{attack_string}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


def test_dangerous_patterns():
    """测试危险模式防护"""
    print("\n🧪 测试危险模式防护...")
    
    temp_dir = tempfile.TemporaryDirectory()
    manager = WorkspaceManager(temp_dir.name)
    
    # 各种危险模式
    dangerous_patterns = [
        ("", "空字符串"),
        (".", "当前目录"),
        ("..", "上级目录"),
        (".hidden", "隐藏文件"),
        ("CON", "Windows保留名称"),
        ("PRN", "Windows保留名称"),
        ("AUX", "Windows保留名称"),
        ("NUL", "Windows保留名称"),
        ("COM1", "Windows保留名称"),
        ("LPT1", "Windows保留名称"),
        ("normal/", "以斜杠结尾"),
        ("/normal", "以斜杠开头"),
        ("normal//evil", "双斜杠"),
        ("normal\\evil", "反斜杠"),
        ("normal\\.\\..\\evil", "混合危险字符"),
        ("a" * 256, "过长名称"),
        ("evil; rm -rf /", "命令注入尝试"),
        ("evil`ls`", "反引号命令"),
        ("evil$(ls)", "命令替换"),
        ("evil | cat", "管道字符"),
        ("evil&cat", "后台进程"),
        ("evil>file", "重定向"),
        ("evil<file", "输入重定向"),
    ]
    
    errors = []
    
    for pattern, description in dangerous_patterns:
        try:
            path = manager.get_workspace_path(pattern)
            errors.append(f"未阻止危险模式: {description} '{pattern}' -> {path}")
            print(f"  ❌ {description}: 未阻止危险模式 '{pattern}'")
        except ValueError as e:
            print(f"  ✅ {description}: 正确阻止危险模式 '{pattern}' - {str(e)[:50]}...")
        except Exception as e:
            errors.append(f"意外错误: {pattern} - {e}")
            print(f"  ❌ {description}: 意外错误 '{pattern}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


def test_workspace_creation_security():
    """测试工作区创建时的安全性"""
    print("\n🧪 测试工作区创建安全性...")
    
    temp_dir = tempfile.TemporaryDirectory()
    manager = WorkspaceManager(temp_dir.name)
    
    test_cases = [
        # (member_id, should_succeed, description)
        ("safe_member", True, "安全成员创建"),
        ("../evil", False, "路径遍历创建"),
        ("/etc/passwd", False, "绝对路径创建"),
        ("", False, "空ID创建"),
        (".hidden", False, "隐藏文件创建"),
    ]
    
    errors = []
    
    for member_id, should_succeed, description in test_cases:
        try:
            path = manager.create_workspace(member_id)
            if should_succeed:
                # 验证工作区实际创建
                if manager.workspace_exists(member_id):
                    print(f"  ✅ {description}: 成功创建 '{member_id}'")
                else:
                    errors.append(f"工作区未实际创建: {member_id}")
                    print(f"  ❌ {description}: 工作区未实际创建")
            else:
                errors.append(f"预期失败但成功创建: {member_id}")
                print(f"  ❌ {description}: 预期失败但成功创建")
                
        except ValueError as e:
            if not should_succeed:
                print(f"  ✅ {description}: 正确拒绝创建 '{member_id}' - {str(e)[:50]}...")
            else:
                errors.append(f"预期成功但创建失败: {member_id} - {e}")
                print(f"  ❌ {description}: 错误拒绝创建 '{member_id}'")
        except Exception as e:
            errors.append(f"意外错误: {member_id} - {e}")
            print(f"  ❌ {description}: 意外错误 '{member_id}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


def test_path_normalization():
    """测试路径规范化安全性"""
    print("\n🧪 测试路径规范化安全性...")
    
    temp_dir = tempfile.TemporaryDirectory()
    base_path = Path(temp_dir.name).resolve()
    manager = WorkspaceManager(temp_dir.name)
    
    # 测试规范化后的安全性
    tricky_cases = [
        ("normal/./path", "当前目录符号"),
        ("normal/../safe", "应被拒绝的路径遍历"),
        ("/tmp/../etc", "应被拒绝的绝对路径"),
        ("C:\\Windows\\..\\System32", "应被拒绝的Windows路径"),
    ]
    
    errors = []
    
    for member_id, description in tricky_cases:
        try:
            path = manager.get_workspace_path(member_id)
            # 检查是否逃逸
            try:
                rel_path = path.relative_to(base_path)
                # 如果包含..，应该被拒绝
                if ".." in str(rel_path):
                    errors.append(f"路径包含..但未被拒绝: {member_id} -> {rel_path}")
                    print(f"  ❌ {description}: 路径包含遍历字符")
                else:
                    print(f"  ✅ {description}: 安全路径 '{member_id}' -> {rel_path}")
            except ValueError:
                errors.append(f"路径逃逸: {member_id} -> {path}")
                print(f"  ❌ {description}: 路径逃逸")
                
        except ValueError as e:
            print(f"  ✅ {description}: 正确拒绝危险路径 '{member_id}' - {str(e)[:50]}...")
        except Exception as e:
            errors.append(f"意外错误: {member_id} - {e}")
            print(f"  ❌ {description}: 意外错误 '{member_id}'")
    
    temp_dir.cleanup()
    
    success = len(errors) == 0
    print(f"\n测试结果: {'✅ 通过' if success else '❌ 失败'}")
    if errors:
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    
    return success


if __name__ == "__main__":
    print("=" * 60)
    print("WorkspaceManager 路径安全测试套件")
    print("=" * 60)
    
    results = []
    
    results.append(("基础路径安全", test_path_security_basic()))
    results.append(("路径遍历攻击防护", test_path_traversal_attacks()))
    results.append(("绝对路径攻击防护", test_absolute_path_attacks()))
    results.append(("危险模式防护", test_dangerous_patterns()))
    results.append(("工作区创建安全性", test_workspace_creation_security()))
    results.append(("路径规范化", test_path_normalization()))
    
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