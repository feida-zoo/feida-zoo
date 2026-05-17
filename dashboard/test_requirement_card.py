#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
需求卡片优化 (pl_6d0752fe) 测试套件

测试需求列表 Tab 的状态标签已从列级名改为中文内部阶段名
"""

import unittest
import re
from pathlib import Path

# 期望的中文状态映射（与 PHASE_TO_CHINESE 一致）
EXPECTED_LABELS = {
    'request': '待处理',
    'validate': '验证中',
    'design': '设计中',
    'ui_design': 'UI设计中',
    'review': '审查中',
    'develop_wt': '开发中(WT)',
    'review_test': '测试审查',
    'develop_code': '编码中',
    'develop': '开发中',
    'test': '测试中',
    'audit': '验收中',
    'final_check': '终检中',
    'deliver': '交付中',
    'done': '已完成',
    'cancelled': '🚫 已取消',
    'timed_out': '⏰ 已超时',
    'escalated': '🚨 已升级',
}

# 不应出现的列级名（旧版）
OLD_COLUMN_NAMES = ['📥 需求池', '🎨 设计阶段', '🔧 开发阶段', '🔍 验收阶段', '✅ 已完成', '⚠️ 异常']


class TestRequirementCardStatusLabels(unittest.TestCase):
    """测试需求列表状态标签"""

    def setUp(self):
        js_path = Path(__file__).parent / "static" / "dev_center.js"
        with open(js_path, 'r', encoding='utf-8') as f:
            self.js = f.read()

    def _extract_requirement_status_labels(self):
        """提取需求列表的 statusLabels block"""
        # 找到第二个 statusLabels（第一个是 issues 的）
        blocks = re.findall(
            r'const statusLabels\s*=\s*\{([^}]+)\};',
            self.js
        )
        if len(blocks) >= 2:
            # 第二个是 requirements 的 statusLabels
            return blocks[1]
        return blocks[-1] if blocks else ''

    def test_no_column_level_names(self):
        """验证没有列级状态名残留"""
        sl_body = self._extract_requirement_status_labels()
        for name in OLD_COLUMN_NAMES:
            self.assertNotIn(name, sl_body,
                             f"statusLabels 中仍含列级名: {name}")

    def test_all_phases_have_chinese_labels(self):
        """验证所有 17 个阶段都有中文标签"""
        sl_body = self._extract_requirement_status_labels()
        for phase, expected_cn in EXPECTED_LABELS.items():
            self.assertIn(phase, sl_body,
                          f"statusLabels 缺少阶段: {phase}")
            self.assertIn(expected_cn, sl_body,
                          f"statusLabels 中阶段 {phase} 缺少中文名: {expected_cn}")

    def test_label_count(self):
        """验证 statusLabels 数量正确"""
        sl_body = self._extract_requirement_status_labels()
        keys = re.findall(r"'(\w+)'\s*:", sl_body)
        self.assertEqual(len(keys), len(EXPECTED_LABELS),
                         f"statusLabels 应有 {len(EXPECTED_LABELS)} 个条目，实际 {len(keys)}")

    def test_no_duplicate_keys(self):
        """验证没有重复的 key"""
        sl_body = self._extract_requirement_status_labels()
        keys = re.findall(r"'(\w+)'\s*:", sl_body)
        self.assertEqual(len(keys), len(set(keys)),
                         "statusLabels 中有重复 key")

    def test_old_issue_status_labels_preserved(self):
        """验证第一个 statusLabels（issues）未受影响"""
        blocks = re.findall(
            r'const statusLabels\s*=\s*\{([^}]+)\};',
            self.js
        )
        if blocks:
            first = blocks[0]
            # issues 应该有 'open', 'in_progress', 'resolved', 'closed'
            self.assertIn('open', first)
            self.assertIn('closed', first)


class TestRequirementCardCSS(unittest.TestCase):
    """测试需求卡片 CSS badge 样式"""

    def setUp(self):
        css_path = Path(__file__).parent / "static" / "dev_center.css"
        with open(css_path, 'r', encoding='utf-8') as f:
            self.css = f.read()

    def test_key_phase_badge_styles_exist(self):
        """验证关键 phase 有 CSS badge 样式"""
        key_phases = ['develop_wt', 'review_test', 'develop_code',
                      'audit', 'cancelled', 'timed_out', 'escalated',
                      'validate', 'ui_design', 'final_check', 'deliver']
        for phase in key_phases:
            class_name = f'.req-status-badge.{phase}'
            self.assertIn(class_name, self.css,
                          f"CSS 缺少 {class_name} 样式")

    def test_original_badge_styles_preserved(self):
        """验证原有的 badge 样式保留"""
        original_classes = ['.request', '.design', '.review',
                            '.develop', '.test', '.done', '.exception']
        for cls in original_classes:
            self.assertIn(cls, self.css,
                          f"CSS 中原有的 {cls} 样式丢失")

    def test_exception_phases_have_red_badge(self):
        """验证异常状态 badge 有红色背景"""
        for phase in ['cancelled', 'escalated']:
            class_name = f'.req-status-badge.{phase}'
            idx = self.css.find(class_name)
            if idx >= 0:
                end = self.css.find('}', idx)
                snippet = self.css[idx:end + 1]
                self.assertIn('fce4ec', snippet,
                              f"{class_name} 应为浅红背景")
                # 检查红色调 hex（#c 开头的颜色或 #b71 等深红）
                has_red = '#c6' in snippet or '#c628' in snippet or '#b71' in snippet or '#d32' in snippet
                self.assertTrue(has_red,
                              f"{class_name} 应为红色文字: {snippet.strip()[:80]}")


if __name__ == "__main__":
    import sys
    if "-v" in sys.argv:
        sys.argv.remove("-v")
        verbosity = 2
    else:
        verbosity = 1

    runner = unittest.TextTestRunner(verbosity=verbosity)
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRequirementCardStatusLabels))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRequirementCardCSS))
    result = runner.run(suite)

    print()
    print(f"总计: {result.testsRun} 测试, "
          f"通过: {result.testsRun - len(result.failures) - len(result.errors)}, "
          f"失败: {len(result.failures)}")

    sys.exit(0 if result.wasSuccessful() else 1)
