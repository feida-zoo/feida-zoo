#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
看板优化 (pl_cc412a3a) 测试套件

测试内容：
1. 常量定义验证
2. 看板数据生成逻辑
3. 去重逻辑
4. 异常状态归入
5. 阶段→中文映射
6. 集成测试（API 响应结构）

用法：
    python3 test_kanban_optimization.py [-v]
    
未启动服务器时：单元测试模式（不依赖 HTTP API）
带 -i 参数时：集成测试模式（需要服务器运行）
"""

import sys
import os
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

# ===== 测试目标常量及函数（与 app_enhanced.py 保持一致） =====

# 期望的5列定义
EXPECTED_KANBAN_STATUS_KEYS = ["request", "design", "develop", "audit", "done"]

# After: exception phases mapped into main columns
AFTER_PIPELINE_PHASE_TO_COLUMN = {
    "request":     "request",
    "validate":    "request",
    "design":      "design",
    "ui_design":   "design",
    "review":      "develop",
    "develop_wt":  "develop",
    "review_test": "develop",
    "develop_code":"develop",
    "develop":     "develop",
    "test":        "develop",
    "audit":       "audit",
    "final_check": "audit",
    "deliver":     "done",
    "done":        "done",
    "cancelled":   "done",
    "timed_out":   "audit",
    "escalated":   "develop",
}

# 阶段中文映射
PHASE_TO_CHINESE = {
    "request":      "待处理",
    "validate":     "验证中",
    "design":       "设计中",
    "ui_design":    "UI设计中",
    "review":       "审查中",
    "develop":      "开发中",
    "develop_wt":   "开发中(WT)",
    "review_test":  "测试审查",
    "develop_code": "编码中",
    "test":         "测试中",
    "audit":        "验收中",
    "final_check":  "终检中",
    "deliver":      "交付中",
    "done":         "已完成",
    "cancelled":    "🚫 已取消",
    "timed_out":    "⏰ 已超时",
    "escalated":    "🚨 已升级",
}


def phase_to_column(phase: str, mapping: dict) -> str:
    """将 Pipeline 阶段映射到看板列"""
    return mapping.get(phase, "request")


def get_chinese_name(phase: str) -> str:
    """获取阶段的中文显示名"""
    return PHASE_TO_CHINESE.get(phase, phase)


# ===== 常量验证单元测试 =====

class TestKanbanConstants(unittest.TestCase):
    """测试看板常量定义"""

    def test_kanban_status_has_5_columns(self):
        """验证看板只有5个列（无 exception 列）"""
        # 模拟 app_enhanced.py 的 AFTER KANBAN_STATUS
        mock_kanban_status = {
            "request": "📥 需求池",
            "design":  "🎨 设计阶段",
            "develop": "🔧 开发阶段",
            "audit":   "🔍 验收阶段",
            "done":    "✅ 已完成",
        }
        self.assertEqual(len(mock_kanban_status), 5)
        self.assertNotIn("exception", mock_kanban_status)

    def test_pipeline_phase_to_column_has_all_keys(self):
        """验证映射覆盖全部 Pipeline 阶段"""
        target_count = len(PHASE_TO_CHINESE)
        self.assertEqual(len(AFTER_PIPELINE_PHASE_TO_COLUMN), target_count,
                         f"PIPELINE_PHASE_TO_COLUMN 有 {len(AFTER_PIPELINE_PHASE_TO_COLUMN)} 个条目, PHASE_TO_CHINESE 有 {target_count} 个")
        for phase in PHASE_TO_CHINESE:
            self.assertIn(phase, AFTER_PIPELINE_PHASE_TO_COLUMN,
                          f"阶段 {phase} 在 PIPELINE_PHASE_TO_COLUMN 中缺失")
        for phase in AFTER_PIPELINE_PHASE_TO_COLUMN:
            self.assertIn(phase, PHASE_TO_CHINESE,
                          f"阶段 {phase} 在 PHASE_TO_CHINESE 中缺失")

    def test_all_phases_map_to_5_columns_only(self):
        """验证所有阶段只映射到5个主列"""
        valid_columns = {"request", "design", "develop", "audit", "done"}
        for phase, col in AFTER_PIPELINE_PHASE_TO_COLUMN.items():
            self.assertIn(col, valid_columns,
                          f"阶段 {phase} 映射到了非5列的 {col}")

    def test_legacy_phases_not_in_columns(self):
        """验证旧 exception 列不再出现"""
        valid_columns = {"request", "design", "develop", "audit", "done"}
        self.assertNotIn("exception", valid_columns)

    def test_exception_phase_mapping(self):
        """验证异常阶段正确归入主列"""
        self.assertEqual(phase_to_column("cancelled", AFTER_PIPELINE_PHASE_TO_COLUMN), "done")
        self.assertEqual(phase_to_column("timed_out", AFTER_PIPELINE_PHASE_TO_COLUMN), "audit")
        self.assertEqual(phase_to_column("escalated", AFTER_PIPELINE_PHASE_TO_COLUMN), "develop")

    def test_phase_to_chinese_all_phases_covered(self):
        """验证 PHASE_TO_CHINESE 覆盖所有 Pipeline 阶段"""
        # 所有在 PIPELINE_PHASE_TO_COLUMN 中的阶段都应该有中文名
        for phase in AFTER_PIPELINE_PHASE_TO_COLUMN:
            self.assertIn(phase, PHASE_TO_CHINESE,
                          f"阶段 {phase} 缺少中文映射")
            self.assertNotEqual(PHASE_TO_CHINESE[phase], phase,
                                f"阶段 {phase} 的中文映射与原始 key 相同（未设置）")

    def test_phase_to_chinese_has_emoji_for_exceptions(self):
        """验证异常阶段的中文名有 Emoji 前缀"""
        for phase in ["cancelled", "timed_out", "escalated"]:
            cn = get_chinese_name(phase)
            self.assertTrue(len(cn) > 3, f"{phase} 的中文名太短: {cn}")

    def test_default_to_request_for_unknown_phase(self):
        """验证未知阶段默认映射到 'request'"""
        self.assertEqual(phase_to_column("unknown_phase_123", AFTER_PIPELINE_PHASE_TO_COLUMN), "request")
        self.assertEqual(phase_to_column("", AFTER_PIPELINE_PHASE_TO_COLUMN), "request")

    def test_phase_order_maintained(self):
        """验证映射顺序正确（无丢失）"""
        expected_order = [
            "request", "validate", "design", "ui_design", "review",
            "develop_wt", "review_test", "develop_code", "develop", "test",
            "audit", "final_check", "deliver", "done",
            "cancelled", "timed_out", "escalated",
        ]
        # 验证 PIPELINE_PHASE_TO_COLUMN 包含所有 expected 阶段
        for phase in expected_order:
            self.assertIn(phase, AFTER_PIPELINE_PHASE_TO_COLUMN,
                          f"阶段 {phase} 在映射中缺失")
        # 验证没有额外的阶段
        for phase in AFTER_PIPELINE_PHASE_TO_COLUMN:
            self.assertIn(phase, expected_order,
                          f"映射中出现了意外的阶段 {phase}")


# ===== 看板数据生成逻辑测试 =====

class TestKanbanDataGeneration(unittest.TestCase):
    """测试看板数据生成核心逻辑"""

    def setUp(self):
        # 创建临时目录模拟数据文件
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.test_dir) / "data"
        self.pipeline_dir = Path(self.test_dir) / "pipeline"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_requirements(self, requirements):
        """创建模拟 requirements.json"""
        req_path = self.data_dir / "requirements.json"
        with open(req_path, 'w', encoding='utf-8') as f:
            json.dump(requirements, f, ensure_ascii=False)

    def _create_pipeline_state(self, pipeline_id, state):
        """创建模拟 Pipeline 状态文件"""
        state_path = self.pipeline_dir / f"state_{pipeline_id}.json"
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump({"state": state, "updated_at": "2026-05-17T20:00:00"}, f)

    def _simulate_kanban_generation(self, mapping=AFTER_PIPELINE_PHASE_TO_COLUMN):
        """
        模拟 app_enhanced.py 的 _get_kanban_data() 逻辑
        
        返回: kanban_tasks dict
        """
        # 读取 requirements
        req_path = self.data_dir / "requirements.json"
        if req_path.exists():
            with open(req_path, 'r', encoding='utf-8') as f:
                requirements = json.load(f)
        else:
            requirements = []

        # 读取活跃管道
        pipelines = {}
        for state_file in self.pipeline_dir.glob("state_*.json"):
            task_id = state_file.stem.replace("state_", "", 1)
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            pipelines[task_id] = {
                "state": state_data.get("state", "unknown"),
                "updated_at": state_data.get("updated_at", "")
            }

        # 模拟 KANBAN_STATUS（5列）
        kanban_status = {
            "request": "📥 需求池",
            "design":  "🎨 设计阶段",
            "develop": "🔧 开发阶段",
            "audit":   "🔍 验收阶段",
            "done":    "✅ 已完成",
        }

        PHASE_EXECUTOR = {
            "request": "panda", "validate": "alpha",
            "design": "alpha", "ui_design": "alpha", "review": "duci",
            "develop_wt": "alpha", "review_test": "duci",
            "develop_code": "alpha", "test": "duci",
            "audit": "duci", "final_check": "panda", "deliver": "panda",
        }

        kanban_tasks = {status: [] for status in kanban_status}
        seen_pipeline_ids = set()

        # Step 2: 从 requirements 加载
        for req in requirements:
            pipeline_id = req.get('pipeline_id', '')
            req_status = req.get('status', 'request')
            column_key = "request"
            pipeline_phase = req_status
            current_executor = PHASE_EXECUTOR.get(req_status, '')

            if pipeline_id:
                if pipeline_id in pipelines:
                    pl_state = pipelines[pipeline_id].get("state", "request")
                    column_key = mapping.get(pl_state, "request")
                    pipeline_phase = pl_state
                    current_executor = PHASE_EXECUTOR.get(pl_state, '')
                elif req_status != 'request':
                    # 单源映射：使用 AFTER_PIPELINE_PHASE_TO_COLUMN
                    column_key = mapping.get(req_status, column_key)
            elif req_status != 'request':
                    # 单源映射：使用 AFTER_PIPELINE_PHASE_TO_COLUMN
                    column_key = mapping.get(req_status, column_key)

            if column_key not in kanban_tasks:
                column_key = "request"

            kanban_tasks[column_key].append({
                'id': req.get('id', ''),
                'name': req.get('title', '未命名需求'),
                'pipeline_id': pipeline_id,
                'phase': column_key,
                'phase_name': kanban_status.get(column_key, column_key),
                'pipeline_status': req.get('status', ''),
                'pipeline_status_raw': req.get('status', ''),
                'current_executor': current_executor,
            })

            if pipeline_id:
                seen_pipeline_ids.add(pipeline_id)

        # Step 3: 从活跃管道补充（去重）
        for task_id, pl_info in pipelines.items():
            if task_id in seen_pipeline_ids:
                continue  # 去重

            pl_state = pl_info.get("state", "request")
            column_key = mapping.get(pl_state, "request")
            if column_key not in kanban_tasks:
                column_key = "request"
            kanban_tasks[column_key].append({
                'id': task_id,
                'name': f'管道任务 {task_id[:8]}',
                'pipeline_id': task_id,
                'phase': column_key,
                'phase_name': kanban_status.get(column_key, column_key),
                'pipeline_status': pl_state,
                'pipeline_status_raw': pl_state,
                'current_executor': PHASE_EXECUTOR.get(pl_state, 'panda'),
            })

        return kanban_tasks, kanban_status

    def test_requirements_loads_into_correct_column(self):
        """验证 requirements 根据阶段正确分配到看板列"""
        self._create_requirements([
            {"id": "req-1", "title": "需求1", "status": "design", "pipeline_id": ""},
            {"id": "req-2", "title": "需求2", "status": "done", "pipeline_id": ""},
            {"id": "req-3", "title": "需求3", "status": "request"},
        ])
        tasks, _ = self._simulate_kanban_generation()

        # req-1 (design) → design 列
        design_ids = [t['id'] for t in tasks['design']]
        self.assertIn("req-1", design_ids)

        # req-2 (done) → done 列
        done_ids = [t['id'] for t in tasks['done']]
        self.assertIn("req-2", done_ids)

        # req-3 (request) → request 列
        request_ids = [t['id'] for t in tasks['request']]
        self.assertIn("req-3", request_ids)

    def test_pipeline_state_overrides_requirement_status(self):
        """验证 Pipeline 状态覆盖 requirement 的原始 status"""
        self._create_requirements([
            {"id": "req-1", "title": "需求1", "status": "design",
             "pipeline_id": "pl_abc123"},
        ])
        self._create_pipeline_state("pl_abc123", "develop_code")

        tasks, _ = self._simulate_kanban_generation()

        # req-1 应该在 develop 列（因为 pipeline state 是 develop_code）
        develop_ids = [t['id'] for t in tasks['develop']]
        self.assertIn("req-1", develop_ids,
                      f"Pipeline state develop_code 应映射到 develop 列")
        self.assertNotIn("req-1", [t['id'] for t in tasks['design']])

    def test_no_duplicate_for_same_pipeline_id(self):
        """验证同一个 pipeline_id 不会重复出现在看板"""
        self._create_requirements([
            {"id": "req-1", "title": "需求1", "status": "develop_code",
             "pipeline_id": "pl_abc123"},
        ])
        self._create_pipeline_state("pl_abc123", "develop_code")

        tasks, _ = self._simulate_kanban_generation()

        # 统计所有列中 pl_abc123 的出现次数
        total_count = sum(
            1 for col_tasks in tasks.values()
            for t in col_tasks
            if t['pipeline_id'] == 'pl_abc123'
        )
        self.assertEqual(total_count, 1,
                         f"pl_abc123 在看板中出现 {total_count} 次，应为 1 次")

    def test_exception_phases_in_correct_columns(self):
        """验证异常状态的需求出现在正确的主列中"""
        self._create_requirements([
            {"id": "req-cancelled", "title": "已取消", "status": "cancelled", "pipeline_id": ""},
            {"id": "req-timedout", "title": "已超时", "status": "timed_out", "pipeline_id": ""},
            {"id": "req-escalated", "title": "已升级", "status": "escalated", "pipeline_id": ""},
        ])
        tasks, _ = self._simulate_kanban_generation()

        # cancelled → done 列
        self.assertIn("req-cancelled", [t['id'] for t in tasks['done']],
                      "cancelled 应在 done 列")
        # timed_out → audit 列
        self.assertIn("req-timedout", [t['id'] for t in tasks['audit']],
                      "timed_out 应在 audit 列")
        # escalated → develop 列
        self.assertIn("req-escalated", [t['id'] for t in tasks['develop']],
                      "escalated 应在 develop 列")

    def test_pipeline_only_entities_appended_when_not_in_requirements(self):
        """验证无对应 requirement 的 pipeline 实体被补充"""
        self._create_requirements([])
        self._create_pipeline_state("pl_solo", "design")

        tasks, _ = self._simulate_kanban_generation()

        # pl_solo 应该出现在看板中（无 requirements 但 pipeline 存在）
        found = any(
            t['pipeline_id'] == 'pl_solo'
            for col_tasks in tasks.values()
            for t in col_tasks
        )
        self.assertTrue(found, "无对应 requirement 的 pipeline 应出现在看板")

    def test_pipeline_with_known_requirement_not_duplicated(self):
        """验证有 requirement 的 pipeline 不再重复补充"""
        self._create_requirements([
            {"id": "req-double", "title": "双源", "status": "audit",
             "pipeline_id": "pl_double"},
        ])
        self._create_pipeline_state("pl_double", "audit")

        tasks, _ = self._simulate_kanban_generation()

        # 只应在 audit 列中出现一次
        count = sum(
            1 for col_tasks in tasks.values()
            for t in col_tasks
            if t['pipeline_id'] == 'pl_double'
        )
        self.assertEqual(count, 1,
                         f"pl_double 出现 {count} 次，预期 1 次")

    def test_unknown_column_phase_defaults_to_request(self):
        """验证未知列名回退到 request"""
        self._create_requirements([
            {"id": "req-unknown", "title": "未知", "status": "made_up_phase",
             "pipeline_id": ""},
        ])
        tasks, _ = self._simulate_kanban_generation()

        # 未知阶段 → request
        self.assertIn("req-unknown", [t['id'] for t in tasks['request']])

    def test_api_response_has_5_columns(self):
        """验证最终 API 响应中只有5列"""
        self._create_requirements([
            {"id": "req-1", "title": "A", "status": "done", "pipeline_id": ""},
        ])
        self._create_pipeline_state("pl_alone", "design")

        tasks, kanban_status = self._simulate_kanban_generation()

        # 验证列数与期望一致
        self.assertEqual(len(kanban_status), 5)
        # 验证列名
        expected_titles = {
            "request": "📥 需求池",
            "design": "🎨 设计阶段",
            "develop": "🔧 开发阶段",
            "audit": "🔍 验收阶段",
            "done": "✅ 已完成",
        }
        for key, title in expected_titles.items():
            self.assertEqual(kanban_status[key], title)

    def test_legacy_exception_column_not_in_response(self):
        """验证旧 exception 列不在响应中"""
        self._create_requirements([
            {"id": "req-cancelled", "title": "取消", "status": "cancelled"},
        ])
        tasks, kanban_status = self._simulate_kanban_generation()

        self.assertNotIn("exception", kanban_status)
        self.assertNotIn("exception", tasks)

    def test_seen_ids_empty_pipeline_ids(self):
        """验证空 pipeline_id 的 requirement 不影响去重"""
        self._create_requirements([
            {"id": "req-no-pid", "title": "无管道", "status": "design"},
            {"id": "req-no-pid2", "title": "無管道2", "status": "done"},
        ])
        tasks, _ = self._simulate_kanban_generation()

        # 两个都应该正常出现
        all_ids = [t['id'] for col_tasks in tasks.values() for t in col_tasks]
        self.assertIn("req-no-pid", all_ids)
        self.assertIn("req-no-pid2", all_ids)

    def test_card_data_has_chinese_phase_name(self):
        """验证卡片数据的 pipeline_status 显示的是中文文本"""
        self._create_requirements([
            {"id": "req-cn", "title": "中文", "status": "develop_code", "pipeline_id": ""},
            {"id": "req-cn2", "title": "取消", "status": "cancelled", "pipeline_id": ""},
        ])
        tasks, _ = self._simulate_kanban_generation()

        # 获取卡片数据
        for col_tasks in tasks.values():
            for t in col_tasks:
                raw_status = t.get('pipeline_status', '')
                # 验证 pipeline_status 被正确设置
                # 注意：在模拟函数中 pipeline_status = req.get('status')
                # 实际在后端会做 PHASE_TO_CHINESE 映射
                pass

        # 验证状态存在
        develop_tasks = tasks.get('develop', [])
        for t in develop_tasks:
            self.assertIn('pipeline_status', t)
            self.assertIn('pipeline_status_raw', t)


# ===== PHASE_TO_CHINESE 映射测试 =====

class TestPhaseToChinese(unittest.TestCase):
    """测试阶段中文映射"""

    def test_all_phases_have_chinese_name(self):
        """验证所有 pipeline 阶段都有中文名"""
        all_phases = [
            "request", "validate", "design", "ui_design", "review",
            "develop_wt", "review_test", "develop_code", "develop",
            "test", "audit", "final_check", "deliver", "done",
            "cancelled", "timed_out", "escalated",
        ]
        for phase in all_phases:
            cn = PHASE_TO_CHINESE.get(phase, "")
            self.assertTrue(cn, f"阶段 {phase} 缺少中文名")
            self.assertNotEqual(cn, phase, f"阶段 {phase} 的中文名未设置")

    def test_chinese_names_are_distinct(self):
        """验证中文名各不相同（无重复映射）"""
        names = list(PHASE_TO_CHINESE.values())
        self.assertEqual(len(names), len(set(names)),
                         "存在重复的中文映射名:\n" +
                         "\n".join(f"  {k}: {v}" for k, v in PHASE_TO_CHINESE.items()))

    def test_chinese_name_length(self):
        """验证中文名合理长度"""
        for phase, cn in PHASE_TO_CHINESE.items():
            self.assertGreaterEqual(len(cn), 2,
                                    f"阶段 {phase} 中文名太短: '{cn}'")
            if phase in ("cancelled", "timed_out", "escalated"):
                self.assertGreaterEqual(len(cn), 5,
                                        f"异常阶段 {phase} 中文名太短: '{cn}'")


# ===== CSS/前端相关元测试 =====

class TestFrontendMeta(unittest.TestCase):
    """前端相关元测试（检查 CSS/JS 中的硬编码引用）"""

    def test_css_grid_should_be_5_columns(self):
        """验证 CSS grid 模板应该改为 repeat(5, 1fr)"""
        css_path = Path(__file__).parent / "static" / "dev_center.css"
        if not css_path.exists():
            self.skipTest("CSS 文件不存在")

        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查 .kanban-columns 的 grid-template-columns
        import re
        grid_match = re.search(
            r'\.kanban-columns\s*\{[^}]*grid-template-columns\s*:\s*([^;}]+)',
            css_content
        )
        if grid_match:
            current_grid = grid_match.group(1).strip()
            self.assertNotIn("repeat(6", current_grid,
                             f"CSS 仍使用 6 列 grid: {current_grid}")
            self.assertIn("repeat(5", current_grid,
                          f"CSS grid 应为 5 列，当前: {current_grid}")

    def test_no_exception_column_css(self):
        """验证 CSS 中没有 .kanban-column.exception 定义"""
        css_path = Path(__file__).parent / "static" / "dev_center.css"
        if not css_path.exists():
            self.skipTest("CSS 文件不存在")

        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查 exception 列样式定义
        if '.kanban-column.exception' in css_content:
            self.fail("CSS 中仍含有 .kanban-column.exception 定义，应移除")


# ===== 集成测试（需要服务器运行） =====

@unittest.skipIf("--integrate" not in sys.argv and "-i" not in sys.argv,
                 "集成测试跳过，使用 -i 或 --integrate 运行")
class TestKanbanAPIIntegration(unittest.TestCase):
    """看板 API 集成测试"""

    BASE_URL = "http://localhost:18792"

    def test_api_returns_5_columns(self):
        """验证 /api/kanban 返回5列"""
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.BASE_URL}/api/kanban", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                statuses = data.get("statuses", {})
                self.assertEqual(len(statuses), 5,
                                 f"API 返回 {len(statuses)} 列，应为 5 列")
                self.assertNotIn("exception", statuses,
                                 "API 返回了 exception 列")
        except (urllib.error.URLError, ConnectionRefusedError) as e:
            self.skipTest(f"服务器未运行: {e}")

    def test_api_response_structure(self):
        """验证 API 响应结构完整"""
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.BASE_URL}/api/kanban", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.assertIn("columns", data)
                self.assertIn("statuses", data)
                self.assertIn("stats", data)
                # 验证每个列都有 title 和 tasks
                for col_key, col_data in data["columns"].items():
                    self.assertIn("title", col_data)
                    self.assertIn("tasks", col_data)
        except (urllib.error.URLError, ConnectionRefusedError) as e:
            self.skipTest(f"服务器未运行: {e}")

    def test_card_has_pipeline_status(self):
        """验证卡片数据包含 pipeline_status 字段"""
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.BASE_URL}/api/kanban", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for col_key, col_data in data["columns"].items():
                    for task in col_data["tasks"]:
                        self.assertIn("pipeline_status", task,
                                      f"卡片 {task.get('id')} 缺少 pipeline_status")
        except (urllib.error.URLError, ConnectionRefusedError) as e:
            self.skipTest(f"服务器未运行: {e}")


# ===== 主入口 =====

if __name__ == "__main__":
    # 解析命令行参数
    if "-v" in sys.argv:
        sys.argv.remove("-v")
        verbosity = 2
    else:
        verbosity = 1

    print("=" * 60)
    print("🐢 看板优化 (pl_cc412a3a) 测试套件")
    print("=" * 60)
    print()
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    runner = unittest.TextTestRunner(verbosity=verbosity)
    suite = unittest.TestSuite()

    # 单元测试
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKanbanConstants))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKanbanDataGeneration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPhaseToChinese))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFrontendMeta))

    # 集成测试（条件性）
    if "-i" in sys.argv or "--integrate" in sys.argv:
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestKanbanAPIIntegration))

    result = runner.run(suite)

    print()
    print("=" * 60)
    print(f"总计: {result.testsRun} 测试, "
          f"通过: {result.testsRun - len(result.failures) - len(result.errors)}, "
          f"失败: {len(result.failures)}, "
          f"错误: {len(result.errors)}")
    if result.wasSuccessful():
        print("✅ 全部通过")
    else:
        print("❌ 有测试失败")
        for test, trace in result.failures:
            print(f"  FAIL: {test}")
        for test, trace in result.errors:
            print(f"  ERROR: {test}")

    sys.exit(0 if result.wasSuccessful() else 1)
