#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成员管理界面优化 (pl_2f64c188) — TDD 测试套件

验收标准:
1. 模型显示从硬编码改为动态读取 API 返回的 member.model
2. 配色从暗色文字改为亮色可读文字
"""

import unittest
import re


class TestMemberModelDisplay(unittest.TestCase):
    """测试成员模型显示逻辑"""

    def test_no_hardcoded_models_in_js(self):
        """JS 中不应有硬编码模型数组"""
        js_path = __file__.replace('test_member_ui.py', 'static/dev_center.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        # 不应有硬编码的 "DeepSeek V4 Flash" 等模型名
        hardcoded = ['DeepSeek V4 Flash', 'GLM-5.1', 'MiniMax-M2.7']
        for model in hardcoded:
            self.assertNotIn(model, js, f"发现硬编码模型: {model}")

    def test_js_reads_member_model_from_api(self):
        """JS 应从 API 响应中读取 member.model"""
        js_path = __file__.replace('test_member_ui.py', 'static/dev_center.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        # 找到 renderMemberStatus 函数体
        m = re.search(r'renderMemberStatus\([^)]*\)\s*\{', js)
        self.assertIsNotNone(m, "找不到 renderMemberStatus 函数")
        # 函数体内应有 member.model 或类似读取逻辑
        func_start = m.start()
        # 找到函数结束（下一个同层级函数或方法）
        brace_count = 1
        i = js.find('{', func_start) + 1
        while brace_count > 0 and i < len(js):
            if js[i] == '{': brace_count += 1
            elif js[i] == '}': brace_count -= 1
            i += 1
        func_body = js[func_start:i]
        self.assertIn('model', func_body, "renderMemberStatus 未使用 model 字段")


class TestMemberUIColor(unittest.TestCase):
    """测试成员管理页配色"""

    def setUp(self):
        css_path = __file__.replace('test_member_ui.py', 'static/dev_center.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

    def test_member_details_not_dark_text(self):
        """.member-details-mini 不应使用暗色半透明文字"""
        m = re.search(r'\.member-details-mini\s*\{([^}]*)\}', self.css)
        if m:
            body = m.group(1)
            self.assertNotIn('rgba(255, 255, 255, 0.7)', body,
                              ".member-details-mini 仍使用暗色文字")
            self.assertNotIn('rgba(255,255,255,0.7)', body,
                              ".member-details-mini 仍使用暗色文字")

    def test_member_model_not_dark_text(self):
        """.member-model 不应使用暗色半透明文字"""
        m = re.search(r'\.member-model\s*\{([^}]*)\}', self.css)
        if m:
            body = m.group(1)
            self.assertNotIn('rgba(255, 255, 255, 0.5)', body,
                              ".member-model 仍使用暗色文字")
            self.assertNotIn('rgba(255,255,255,0.5)', body,
                              ".member-model 仍使用暗色文字")

    def test_member_model_uses_readable_color(self):
        """.member-model 应使用可读颜色"""
        m = re.search(r'\.member-model\s*\{([^}]*)\}', self.css)
        if m:
            body = m.group(1)
            has_readable = ('var(--gray-color)' in body or
                           'var(--dark-color)' in body or
                           '#7f8c8d' in body or
                           '#2c3e50' in body)
            self.assertTrue(has_readable,
                           f".member-model 未使用可读颜色: {body[:80]}")

    def test_member_status_item_not_dark_bg(self):
        """.member-status-item 不应使用暗色半透明背景"""
        blocks = re.findall(r'\.member-status-item\s*\{([^}]*)\}', self.css)
        for block in blocks:
            self.assertNotIn('rgba(255, 255, 255, 0.05)', block,
                             ".member-status-item 仍使用暗色背景")
            self.assertNotIn('rgba(255,255,255,0.05)', block,
                             ".member-status-item 仍使用暗色背景")


if __name__ == "__main__":
    import sys
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestMemberModelDisplay))
    suite.addTests(loader.loadTestsFromTestCase(TestMemberUIColor))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
