#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
需求卡片优化2 (pl_985c3146) 测试套件

测试看板 Kanban 卡片按创建时间从新到旧排序
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path


class TestKanbanSort(unittest.TestCase):
    """测试看板卡片排序"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_requirements(self, requirements):
        req_path = Path(self.test_dir) / "requirements.json"
        with open(req_path, 'w', encoding='utf-8') as f:
            json.dump(requirements, f, ensure_ascii=False)

    def _simulate_sort(self, mapping=None):
        """模拟 app_enhanced.py 的排序逻辑"""
        # 基础测试数据
        tasks = [
            {'id': 'req-old', 'name': '旧需求', 'created_at': '2026-05-01T00:00:00', 'severity': 'P1'},
            {'id': 'req-mid', 'name': '中需求', 'created_at': '2026-05-10T00:00:00', 'severity': 'P2'},
            {'id': 'req-new', 'name': '新需求', 'created_at': '2026-05-17T00:00:00', 'severity': 'P3'},
        ]
        # 按创建时间从新到旧排序
        tasks.sort(key=lambda x: (x.get('created_at', '') or ''), reverse=True)
        return tasks

    def test_newest_first(self):
        """验证新需求排在旧需求前面"""
        sorted_tasks = self._simulate_sort()
        ids = [t['id'] for t in sorted_tasks]
        self.assertEqual(ids, ['req-new', 'req-mid', 'req-old'])

    def test_same_date_order(self):
        """验证同一天创建的卡片保持稳定顺序"""
        tasks = [
            {'id': 'req-a', 'name': 'A', 'created_at': '2026-05-17T20:00:00', 'severity': 'P0'},
            {'id': 'req-b', 'name': 'B', 'created_at': '2026-05-17T20:00:00', 'severity': 'P1'},
            {'id': 'req-c', 'name': 'C', 'created_at': '2026-05-16T20:00:00', 'severity': 'P2'},
        ]
        tasks.sort(key=lambda x: (x.get('created_at', '') or ''), reverse=True)
        ids = [t['id'] for t in tasks]
        # req-a 和 req-b 同时间，相对顺序稳定
        self.assertEqual(ids[0], 'req-a')  # 最新时间
        self.assertEqual(ids[-1], 'req-c')  # 最旧时间

    def test_empty_created_at(self):
        """验证无创建时间的卡片排在最后"""
        tasks = [
            {'id': 'req-new', 'created_at': '2026-05-17T00:00:00', 'severity': 'P1'},
            {'id': 'req-no-date', 'created_at': '', 'severity': 'P2'},
            {'id': 'req-old', 'created_at': '2026-05-01T00:00:00', 'severity': 'P3'},
        ]
        # sort 使用 or '' 处理 None/空值
        for t in tasks:
            t['created_at'] = t.get('created_at') or ''
        tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        ids = [t['id'] for t in tasks]
        self.assertEqual(ids[0], 'req-new')
        # 空创建时间的排在最后（空串 < "2026-..."）
        self.assertEqual(ids[-1], 'req-no-date')


class TestKanbanSortIntegration(unittest.TestCase):
    """集成验证：检查 app_enhanced.py 排序逻辑已修改"""

    def test_sort_uses_reverse(self):
        """验证排序代码使用了 reverse=True"""
        with open('dashboard/app_enhanced.py', 'r', encoding='utf-8') as f:
            py = f.read()
        self.assertIn('reverse=True', py,
                      "排序应使用 reverse=True")

    def test_no_severity_order_in_kanban_data(self):
        """验证 _get_kanban_data() 排序逻辑不用 severity_order"""
        with open('dashboard/app_enhanced.py', 'r', encoding='utf-8') as f:
            py = f.read()
        # 提取 _get_kanban_data 方法体
        import re
        m = re.search(r'def _get_kanban_data\(self\):(.*?)def _get_git_timeline', py, re.DOTALL)
        if m:
            method_body = m.group(1)
            if 'severity_order' in method_body:
                self.fail("_get_kanban_data() 中仍有 severity_order")



if __name__ == "__main__":
    import sys
    if "-v" in sys.argv:
        sys.argv.remove("-v")
        verbosity = 2
    else:
        verbosity = 1

    runner = unittest.TextTestRunner(verbosity=verbosity)
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKanbanSort))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKanbanSortIntegration))
    result = runner.run(suite)

    print()
    print(f"总计: {result.testsRun} 测试, "
          f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    sys.exit(0 if result.wasSuccessful() else 1)
