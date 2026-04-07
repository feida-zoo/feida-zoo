#!/usr/bin/env python3
"""
毒刺 🦂 路径穿刺攻击测试
测试 WorkspaceManager 的路径安全验证
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from framework.core.workspace_manager import WorkspaceManager


class PathTraversalAuditor:
    """路径穿刺审计器"""
    
    def __init__(self, base_path="/tmp/test_workspace"):
        self.base_path = Path(base_path)
        self.manager = WorkspaceManager(self.base_path)
        self.passed_attacks = 0
        self.failed_attacks = 0
        self.vulnerabilities = []
    
    def test_basic_traversal(self):
        """测试基本路径遍历"""
        print("🧪 测试基本路径遍历...")
        
        attacks = [
            # 基本路径遍历
            "../",
            "../../",
            "../../../",
            "../../../../",
            # 相对路径
            "a/../../",
            "a/b/../../../",
            "a/../b/../../../",
            # 混合路径分隔符
            "..\\",
            "..\\..\\",
            "../\\..",
            "..\\/..",
            # 隐藏的路径遍历
            "a/./../..",
            "./../",
            ".\\..\\",
            # 多层嵌套
            "a/../b/../c/../../..",
            "x/y/../../../../../",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"基本路径遍历: '{attack}' -> {path}")
                print(f"  ❌ 攻击 '{attack}' 成功逃逸到: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ 攻击 '{attack}' 被阻止: {e}")
        
        print(f"  📊 基本路径遍历: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_unicode_attacks(self):
        """测试 Unicode 编码攻击"""
        print("🧪 测试 Unicode 编码攻击...")
        
        attacks = [
            # Unicode 点
            "..\u002e\u002e",
            ".\u002e/\u002e",
            # Unicode 斜杠
            "..\u002f..\u002f",
            "..\u005c..\u005c",
            # Unicode 空白符
            "member\u200bid",
            "member\u200cid",
            "member\u200did",
            "member\ufeffid",
            # 零宽字符
            "test\u200b",
            "test\u200c",
            "test\u200d",
            # 双向文本控制
            "\u202e",  # RLO
            "\u200e",  # LRM
            "\u200f",  # RLM
            # 组合字符
            "a\u0300",
            "c\u0327",
            "n\u0303",
            "A\u030a",
            "C\u0327",
            "o\u0308",
            # 全角字符
            "．．",
            "／",
            "＼",
            # 控制字符
            "member\x00id",
            "member\x01id",
            "member\x0aid",
            "member\x1bid",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"Unicode攻击: '{repr(attack)}' -> {path}")
                print(f"  ❌ Unicode攻击 '{repr(attack)}' 成功逃逸到: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ Unicode攻击 '{repr(attack)}' 被阻止: {e}")
        
        print(f"  📊 Unicode攻击: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_url_encoding_attacks(self):
        """测试 URL 编码攻击"""
        print("🧪 测试 URL 编码攻击...")
        
        attacks = [
            # URL 编码
            "..%2f",
            "%2e%2e",
            "%2e%2e%2f",
            # 双重编码
            "%252e%252e",
            "%252e%252e%252f",
            # 混合编码
            "..%2f%2e%2e%2f",
            ".%2e/.%2e",
            # 控制字符编码
            "%00",
            "%0a",
            "%0d",
            "%20",
            # URL 编码的路径遍历
            "..%2fetc%2fpasswd",
            "%2e%2e%2f..%2f..%2f",
            "..%5c..%5c",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"URL编码攻击: '{attack}' -> {path}")
                print(f"  ❌ URL攻击 '{attack}' 成功逃逸到: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ URL攻击 '{attack}' 被阻止: {e}")
        
        print(f"  📊 URL编码攻击: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_html_encoding_attacks(self):
        """测试 HTML 编码攻击"""
        print("🧪 测试 HTML 编码攻击...")
        
        attacks = [
            # HTML 实体
            "..&sol;..&sol;",
            "..&#x2f;..&#x2f;",
            "..&#47;..&#47;",
            # 十六进制转义
            "..\x2f..\x2f",
            "..\u002f..\u002f",
            # 八进制转义
            "..\2f ..\2f ",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"HTML编码攻击: '{attack}' -> {path}")
                print(f"  ❌ HTML攻击 '{attack}' 成功逃逸到: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ HTML攻击 '{attack}' 被阻止: {e}")
        
        print(f"  📊 HTML编码攻击: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_mixed_encoding_attacks(self):
        """测试混合编码攻击"""
        print("🧪 测试混合编码攻击...")
        
        attacks = [
            # Unicode + URL
            "\u002e%2e",
            "%2e\u002e",
            "..\u002f..\u005c",
            ".\u002e/..\u005c",
            # 多层编码
            "\u0025\u0032\u0065",  # %2e 的 Unicode
            "%5c%75%30%30%32%65",  # \u002e 的 URL 编码
            # 混合控制字符
            "member\x00\u002e\u002e",
            "%00..%2f",
            "\x0a..\x0d%2f",
            "\u000a..\u000d",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"混合编码攻击: '{repr(attack)}' -> {path}")
                print(f"  ❌ 混合攻击 '{repr(attack)}' 成功逃逸到: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ 混合攻击 '{repr(attack)}' 被阻止: {e}")
        
        print(f"  📊 混合编码攻击: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_os_path_join_bypass(self):
        """测试 os.path.join 绕过"""
        print("🧪 测试 os.path.join 绕过...")
        
        base_path = self.base_path
        test_cases = [
            # 使用 os.path.join 构造路径
            ("a", "../b"),
            ("a/b", "../../c"),
            ("a", "b/../../../c"),
            ("", "../../etc/passwd"),
            (".", "../.."),
            # 绝对路径组合
            ("/tmp", "test"),
            ("a", "/etc/passwd"),
            # 空字节攻击
            ("a", "b\x00c"),
            # 点点攻击的各种变体
            ("a", "..\\b"),
            ("a\\b", "..\\..\\c"),
        ]
        
        for base, rel in test_cases:
            try:
                # 使用 os.path.join 组合路径
                joined = os.path.join(base, rel)
                
                # 测试是否能被 WorkspaceManager 检测到
                if base and not base.startswith('/'):
                    # 如果 base 是相对路径，将其作为成员ID测试
                    test_path = joined
                else:
                    # 否则测试相对路径部分
                    test_path = rel
                
                path = self.manager.get_workspace_path(test_path)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"os.path.join绕过: base='{base}', rel='{rel}' -> {path}")
                print(f"  ❌ os.path.join绕过: '{base}' + '{rel}' = '{joined}' -> {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ os.path.join绕过被阻止: '{base}' + '{rel}' -> {e}")
        
        print(f"  📊 os.path.join绕过: {self.passed_attacks}/{len(test_cases)} 被阻止")
        return self.failed_attacks == 0
    
    def test_absolute_path_escape(self):
        """测试绝对路径逃逸"""
        print("🧪 测试绝对路径逃逸...")
        
        attacks = [
            # Unix 绝对路径
            "/etc/passwd",
            "/tmp/test",
            "/home/user/.ssh/id_rsa",
            # Windows 绝对路径
            "C:\\Windows\\System32",
            "D:\\test.txt",
            # Windows UNC 路径
            "\\\\server\\share",
            "//server/share",
            # 带环境变量
            "~/../etc/passwd",
            "$HOME/../etc/passwd",
            "%USERPROFILE%\\..\\Windows",
            # 带协议
            "file:///etc/passwd",
            # 特殊设备文件
            "/dev/null",
            "/dev/zero",
            # 符号链接目标
            "/proc/self/exe",
            "/proc/self/cwd",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                self.failed_attacks += 1
                self.vulnerabilities.append(f"绝对路径逃逸: '{attack}' -> {path}")
                print(f"  ❌ 绝对路径逃逸 '{attack}' 成功: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ 绝对路径逃逸 '{attack}' 被阻止: {e}")
        
        print(f"  📊 绝对路径逃逸: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def test_path_normalization_bypass(self):
        """测试路径规范化绕过"""
        print("🧪 测试路径规范化绕过...")
        
        attacks = [
            # 多重斜杠
            "a//b",
            "a///b",
            "a////b",
            # 点和点点组合
            "a/././b",
            "a/./././b",
            "a/b/././c",
            # 尾部斜杠
            "test/",
            "a/b/",
            "test//",
            # 前导点
            "./test",
            "../test",
            # 混合
            "a/./b/../c/./d",
            "a//b/../c",
            "./a/../b",
            # 空路径组件
            "a//",
            "a///",
            "//a",
            # Windows 风格混合
            "a\\b\\c",
            "a/b\\c",
            "a\\b/c",
        ]
        
        for attack in attacks:
            try:
                path = self.manager.get_workspace_path(attack)
                # 检查是否真的在工作区内
                resolved = path.resolve()
                if not str(resolved).startswith(str(self.base_path.resolve())):
                    self.failed_attacks += 1
                    self.vulnerabilities.append(f"路径规范化绕过: '{attack}' -> {path} (逃逸到: {resolved})")
                    print(f"  ❌ 路径规范化绕过 '{attack}' 成功逃逸到: {resolved}")
                else:
                    self.passed_attacks += 1
                    print(f"  ✅ 路径规范化 '{attack}' 被安全处理: {path}")
            except ValueError as e:
                self.passed_attacks += 1
                print(f"  ✅ 路径规范化 '{attack}' 被阻止: {e}")
        
        print(f"  📊 路径规范化绕过: {self.passed_attacks}/{len(attacks)} 被阻止")
        return self.failed_attacks == 0
    
    def run_all_tests(self):
        """运行所有路径穿刺测试"""
        print("=" * 80)
        print("🦂 毒刺路径穿刺审计开始")
        print("=" * 80)
        
        # 重置计数器
        self.passed_attacks = 0
        self.failed_attacks = 0
        self.vulnerabilities = []
        
        tests = [
            ("基本路径遍历测试", self.test_basic_traversal),
            ("Unicode 编码攻击测试", self.test_unicode_attacks),
            ("URL 编码攻击测试", self.test_url_encoding_attacks),
            ("HTML 编码攻击测试", self.test_html_encoding_attacks),
            ("混合编码攻击测试", self.test_mixed_encoding_attacks),
            ("os.path.join 绕过测试", self.test_os_path_join_bypass),
            ("绝对路径逃逸测试", self.test_absolute_path_escape),
            ("路径规范化绕过测试", self.test_path_normalization_bypass),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            try:
                result = test_func()
                results.append(result)
            except Exception as e:
                print(f"  💥 测试异常: {e}")
                results.append(False)
        
        # 总结
        print("\n" + "=" * 80)
        print("📊 路径穿刺审计结果总结")
        print("=" * 80)
        print(f"✅ 被阻止的攻击: {self.passed_attacks}")
        print(f"❌ 成功的攻击: {self.failed_attacks}")
        
        if self.vulnerabilities:
            print(f"\n⚠️  发现的漏洞 ({len(self.vulnerabilities)} 个):")
            for vuln in self.vulnerabilities[:10]:  # 只显示前10个
                print(f"  - {vuln}")
            if len(self.vulnerabilities) > 10:
                print(f"  ... 还有 {len(self.vulnerabilities) - 10} 个漏洞未显示")
        
        if self.failed_attacks == 0:
            print("\n🎉 所有路径穿刺攻击被阻止！路径安全验证有效。")
            return True
        else:
            print(f"\n⚠️  发现 {self.failed_attacks} 个路径穿刺漏洞，需要修复。")
            return False


if __name__ == "__main__":
    import tempfile
    import shutil
    
    # 创建临时目录进行测试
    temp_dir = tempfile.mkdtemp(prefix="path_audit_")
    print(f"📁 使用临时目录: {temp_dir}")
    
    try:
        auditor = PathTraversalAuditor(temp_dir)
        success = auditor.run_all_tests()
        exit(0 if success else 1)
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 已清理临时目录: {temp_dir}")