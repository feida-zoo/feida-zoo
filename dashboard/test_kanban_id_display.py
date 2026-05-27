#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
看板页 ID 显示 (pl_94726bf7) — TDD 测试套件

验收标准:
1. 看板卡片显示 pipeline_id（短ID），而非 UUID
2. 无 pipeline_id 的旧需求回退到 task.id（UUID）
3. 两者皆无时回退到空字符串
"""

import unittest


# 模拟 createTaskCard() 中 ID 显示逻辑（前端 JS 对应的 Python 模拟）
def get_display_id(task):
    """模拟: ${task.pipeline_id || task.id || ''}"""
    return task.get('pipeline_id') or task.get('id') or ''


class TestKanbanIdDisplay(unittest.TestCase):
    """测试看板卡片 ID 显示逻辑"""

    def test_show_pipeline_id_when_available(self):
        """有 pipeline_id 时显示短ID"""
        task = {
            'id': 'e13ac8d8-5f13-47f5-8779-8d7929dcb57a',
            'pipeline_id': 'pl_3edd4a81',
            'title': '测试需求'
        }
        self.assertEqual(get_display_id(task), 'pl_3edd4a81')

    def test_fallback_to_uuid_when_no_pipeline_id(self):
        """无 pipeline_id 时回退 UUID"""
        task = {
            'id': 'e13ac8d8-5f13-47f5-8779-8d7929dcb57a',
            'title': '旧需求'
        }
        self.assertEqual(get_display_id(task), 'e13ac8d8-5f13-47f5-8779-8d7929dcb57a')

    def test_empty_when_both_missing(self):
        """两者皆无时返回空字符串"""
        task = {'title': '无ID需求'}
        self.assertEqual(get_display_id(task), '')

    def test_pipeline_id_empty_string_fallback(self):
        """pipeline_id 为空字符串时回退 UUID"""
        task = {
            'id': 'abc-123',
            'pipeline_id': '',
            'title': '空pipeline'
        }
        self.assertEqual(get_display_id(task), 'abc-123')

    def test_pipeline_only_task(self):
        """pipeline-only 任务：id = pipeline_id（如 pl_abc123）"""
        task = {
            'id': 'pl_abc123',
            'pipeline_id': 'pl_abc123',
            'title': 'Pipeline only'
        }
        self.assertEqual(get_display_id(task), 'pl_abc123')

    def test_display_matches_chatroom_format(self):
        """显示格式与聊天室 pl_id 格式一致"""
        task = {
            'id': 'uuid-123',
            'pipeline_id': 'pl_94726bf7',
            'title': '匹配测试'
        }
        display = get_display_id(task)
        # 格式: pl_ + 8位 hex
        self.assertTrue(display.startswith('pl_'))
        self.assertEqual(len(display), 3 + 8)  # "pl_" + 8 hex chars


class TestJSCodeStructure(unittest.TestCase):
    """验证前端代码包含正确逻辑"""

    def setUp(self):
        self.js_path = __file__.replace('test_kanban_id_display.py', 'static/dev_center.js')
        with open(self.js_path, 'r', encoding='utf-8') as f:
            self.js = f.read()

    def test_createTaskCard_has_pipeline_id_display(self):
        """createTaskCard 应使用 pipeline_id 显示"""
        # 找到 task-id div 行，确认使用 pipeline_id
        import re
        matches = re.findall(r'<div class="task-id">\$\{([^}]+)\}</div>', self.js)
        self.assertTrue(len(matches) > 0, "找不到 task-id 显示逻辑")
        self.assertIn('pipeline_id', matches[0],
                      f"task-id 未使用 pipeline_id，当前: {matches[0]}")


if __name__ == "__main__":
    import sys
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestKanbanIdDisplay))
    suite.addTests(loader.loadTestsFromTestCase(TestJSCodeStructure))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
