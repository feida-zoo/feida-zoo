#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题管理页亮色调统一 (pl_3855650e) — TDD 测试套件

验收标准:
1. 问题管理页所有暗色 CSS 值已替换为亮色对应值
2. 无遗留暗色背景 (#1e1e2e, #181825, #313244)
3. 按钮颜色与需求管理页一致
4. 表单输入框样式与需求管理页一致
"""

import unittest
import re


class TestIssuesLightTheme(unittest.TestCase):
    """验证问题管理页 CSS 已统一为亮色调"""

    def setUp(self):
        css_path = __file__.replace('test_issues_light_theme.py', 'static/dev_center.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

    def test_no_dark_container_background(self):
        """issues-container 不应使用暗色背景 #1e1e2e"""
        m = re.search(r'\.issues-container\s*\{[^}]*background:\s*#1e1e2e', self.css)
        self.assertIsNone(m, "issues-container 仍使用暗色背景 #1e1e2e")

    def test_no_dark_header_background(self):
        """issues-header 不应使用暗色背景 #181825"""
        m = re.search(r'\.issues-header\s*\{[^}]*background:\s*#181825', self.css)
        self.assertIsNone(m, "issues-header 仍使用暗色背景 #181825")

    def test_no_dark_card_background(self):
        """issue-card 不应使用暗色背景 #313244"""
        m = re.search(r'\.issue-card\s*\{[^}]*background:\s*#313244', self.css)
        self.assertIsNone(m, "issue-card 仍使用暗色背景 #313244")

    def test_no_dark_text_color(self):
        """issues-header h2 不应使用暗色文字 #cdd6f4"""
        m = re.search(r'\.issues-header\s+h2\s*\{[^}]*color:\s*#cdd6f4', self.css)
        self.assertIsNone(m, "issues-header h2 仍使用暗色文字 #cdd6f4")

    def test_no_dark_input_background(self):
        """issues-toolbar input 不应使用暗色背景 #313244"""
        m = re.search(r'\.issues-toolbar\s+input[^}]*background:\s*#313244', self.css)
        self.assertIsNone(m, "issues-toolbar input 仍使用暗色背景 #313244")

    def test_no_dark_modal_background(self):
        """issue-modal-content 不应使用暗色背景 #1e1e2e"""
        m = re.search(r'\.issue-modal-content\s*\{[^}]*background:\s*#1e1e2e', self.css)
        self.assertIsNone(m, "issue-modal-content 仍使用暗色背景 #1e1e2e")

    def test_issues_container_uses_light_background(self):
        """issues-container 应使用亮色背景（white 或 var）"""
        m = re.search(r'\.issues-container\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, "找不到 .issues-container 规则")
        body = m.group(1)
        # 应包含 white 或 var(-- 开头的背景色
        has_light = 'white' in body or 'var(--' in body
        self.assertTrue(has_light, f"issues-container 未使用亮色背景: {body[:80]}")

    def test_create_issue_button_uses_primary_color(self):
        """btn-create-issue 应使用主色调（与需求管理 btn-submit 一致）"""
        m = re.search(r'\.btn-create-issue\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, "找不到 .btn-create-issue 规则")
        body = m.group(1)
        # 应使用 var(--primary-color) 或 #3498db 等蓝色系
        has_primary = 'var(--primary-color)' in body or '#3498db' in body or '#2980b9' in body
        self.assertTrue(has_primary, f"btn-create-issue 未使用主色调: {body[:80]}")

    def test_issue_card_uses_light_border(self):
        """issue-card 应使用浅色边框"""
        m = re.search(r'\.issue-card\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, "找不到 .issue-card 规则")
        body = m.group(1)
        has_light_border = 'var(--border-color)' in body or '#ddd' in body or '#e0e0e0' in body
        self.assertTrue(has_light_border, f"issue-card 未使用浅色边框: {body[:80]}")

    def test_issue_title_uses_dark_color(self):
        """issue-title 应使用深色文字（与需求管理一致）"""
        m = re.search(r'\.issue-title\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, "找不到 .issue-title 规则")
        body = m.group(1)
        has_dark = 'var(--dark-color)' in body or '#2c3e50' in body or '#34495e' in body
        self.assertTrue(has_dark, f"issue-title 未使用深色文字: {body[:80]}")


class TestNoDarkColorLeakage(unittest.TestCase):
    """全局检查：确认无暗色值泄漏到问题管理选择器"""

    DARK_COLORS = ['#1e1e2e', '#181825', '#313244', '#45475a', '#cdd6f4', '#a6adc8', '#585b70']

    def setUp(self):
        css_path = __file__.replace('test_issues_light_theme.py', 'static/dev_center.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

    def test_no_catppuccin_colors_in_issues_selectors(self):
        """所有 issues-/issue- 选择器内不应有 Catppuccin 暗色值"""
        # 提取所有 issues-/issue- 相关的规则块
        blocks = re.findall(r'(?:\.issues-[^,\{]+|\.issue-[^,\{]+)\s*\{([^}]*)\}', self.css)
        violations = []
        for block in blocks:
            for dark in self.DARK_COLORS:
                if dark in block:
                    violations.append(f"发现暗色值 {dark} 在: {block[:60]}...")
        if violations:
            self.fail("\n".join(["暗色值泄漏:"] + violations[:5]))


if __name__ == "__main__":
    import sys
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestIssuesLightTheme))
    suite.addTests(loader.loadTestsFromTestCase(TestNoDarkColorLeakage))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
