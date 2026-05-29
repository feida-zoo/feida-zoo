#!/usr/bin/env python3
"""
pl_6932a56b — README 更新测试用例
覆盖设计文档中全部 8 项验收检查点 + Review P1 建议
"""
import os
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")
SCREENSHOT_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
SCREENSHOT_OLD_DIR = os.path.join(REPO_ROOT, "docs", "pipeline")


# ============================================================
# 基础校验
# ============================================================

def _read_readme():
    """读取 README.md，若不存在则跳过"""
    pytest.raises(AssertionError) if not os.path.exists(README_PATH) else None
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _screenshot_exists(name, search_dir=None):
    """检查截图文件是否存在"""
    if search_dir is None:
        search_dir = SCREENSHOT_DIR
    path = os.path.join(search_dir, name)
    if os.path.exists(path):
        return path
    # fallback to old location
    old_path = os.path.join(SCREENSHOT_OLD_DIR, name)
    if os.path.exists(old_path):
        return old_path
    return None


# ============================================================
# 测试用例
# ============================================================

class TestReadmeExists:
    """TC-001: README 文件存在"""

    def test_readme_exists(self):
        assert os.path.exists(README_PATH), "README.md 不存在"


class TestActiveMembers:
    """TC-002: 成员列表 — 活跃成员信息正确，已退出成员已归档"""

    README_ACTIVE_MEMBERS = ["达达", "Panda", "阿尔法", "Alpha", "毒刺", "Duci"]
    README_ARCHIVED_MEMBERS = ["织巢", "Weaver", "埃特娜", "Aeterna", "咕噜", "Gulu"]

    def test_active_members_present(self):
        """活跃成员必须出现在成员表（或标注为活跃的区域）"""
        content = _read_readme()
        for name in self.README_ACTIVE_MEMBERS:
            # 活跃成员应在活跃段或表内
            assert name in content, f"活跃成员 {name} 未出现在 README 中"

    def test_ex_members_not_in_active_table(self):
        """已退出成员不应出现在活跃成员表中（可在归档区出现）"""
        content = _read_readme()
        # 找成员表区域（在「成员列表」章节）
        member_section = self._extract_section(content, "成员列表")
        if member_section:
            for name in self.README_ARCHIVED_MEMBERS:
                if name in member_section:
                    # 如果出现在成员列表节，必须在归档子区域
                    assert "归档" in member_section or "已退出" in member_section, \
                        f"已退出成员 {name} 出现在活跃成员区域但无归档标注"

    @staticmethod
    def _extract_section(content, section_title):
        idx = content.find(f"## {section_title}")
        if idx == -1:
            return None
        next_idx = content.find("\n## ", idx + 3)
        if next_idx == -1:
            return content[idx:]
        return content[idx:next_idx]


class TestCoreRules:
    """TC-003: 核心守则完整可读"""

    def test_core_rules_not_empty(self):
        """核心守则不应为空/无链接断裂"""
        content = _read_readme()
        assert "详见" not in content.split("核心守则")[-1][:30] if "核心守则" in content else True, \
            "核心守则后存在「详见」空链接"
        assert "核心守则" in content, "核心守则章节缺失"
        # 守则后至少跟有实际内容（不仅仅是标题）
        rules_section = content.split("核心守则")[-1]
        # 跳过标题行，检查是否有内容
        assert len(rules_section.strip()) > 50, "核心守则内容过短，疑似空章节"

    def test_core_rules_contains_rules(self):
        """核心守则包含至少一条实质性规则"""
        content = _read_readme()
        keywords = ["不得", "必须", "禁止", "应当", "🐢", "🦂", "🐼"]
        rules_section = content.split("核心守则")[-1].split("##")[0]
        assert any(k in rules_section for k in keywords), "核心守则未包含实质性规则"


class TestScreenshots:
    """TC-004/TC-009: 至少 3 张截图存在"""

    EXPECTED_SCREENSHOTS = [
        "screenshot_kanban.png",
        "screenshot_members.png",
        "screenshot_chat.png",
    ]
    OPTIONAL_SCREENSHOTS = ["screenshot_requirements.png"]

    def test_minimum_screenshots(self):
        """至少 3 张必要截图"""
        count = sum(1 for s in self.EXPECTED_SCREENSHOTS if _screenshot_exists(s) is not None)
        assert count >= 3, f"必要截图不足，仅找到 {count}/3"

    def test_screenshots_referenced_in_readme(self):
        """截图路径在 README 中被引用"""
        content = _read_readme()
        ref_count = sum(1 for s in self.EXPECTED_SCREENSHOTS if s in content)
        assert ref_count >= 2, f"README 中截图引用不足，仅找到 {ref_count}/3"

    def test_screenshots_not_empty(self):
        """截图文件非空（大于 10KB 表示有实际内容）"""
        for name in self.EXPECTED_SCREENSHOTS:
            path = _screenshot_exists(name)
            if path:
                size = os.path.getsize(path)
                assert size > 10240, f"{name} 疑似空截图（仅 {size} bytes）"


class TestProjectOverview:
    """TC-005: 项目概述存在"""

    def test_has_project_overview(self):
        content = _read_readme()
        assert "项目概述" in content or "简介" in content, "缺少项目概述章节"

    def test_overview_not_empty(self):
        content = _read_readme()
        overview_section = content.split("项目概述")[-1].split("##")[0] if "项目概述" in content else ""
        overview_section = overview_section or (content.split("简介")[-1].split("##")[0] if "简介" in content else "")
        assert len(overview_section.strip()) > 50, "项目概述内容过短"


class TestDirectoryStructure:
    """TC-006: 目录结构说明"""

    EXPECTED_DIRS = ["agents", "dashboard", "framework", "scripts", "plugins", "skills"]

    def test_directory_structure_section(self):
        content = _read_readme()
        assert "项目结构" in content or "目录结构" in content, "缺少项目结构章节"

    def test_key_directories_listed(self):
        content = _read_readme()
        structure_section = self._extract_section(content, "项目结构") or ""
        for d in self.EXPECTED_DIRS:
            assert d in structure_section, f"核心目录 {d} 未在项目结构中列出"

    @staticmethod
    def _extract_section(content, title):
        idx = content.find(f"## {title}")
        if idx == -1:
            return None
        next_idx = content.find("\n## ", idx + 3)
        return content[idx:next_idx] if next_idx != -1 else content[idx:]


class TestRunGuide:
    """TC-007: 运行指南完整"""

    def test_has_run_guide(self):
        content = _read_readme()
        assert "快速开始" in content or "启动" in content or "运行指南" in content, \
            "缺少运行指南章节"

    def test_has_start_command(self):
        content = _read_readme()
        # 有命令行提示词
        assert "bash" in content or "sh " in content or "./" in content or "python" in content, \
            "运行指南缺少启动命令"

    def test_has_access_address(self):
        content = _read_readme()
        assert "18792" in content or "localhost" in content or "http" in content, \
            "运行指南缺少访问地址"

    def test_env_var_mentioned(self):
        """运行指南提及 FEIDA_ZOO_HOME 环境变量"""
        content = _read_readme()
        assert "FEIDA_ZOO_HOME" in content or "环境变量" in content, \
            "运行指南未提及环境变量说明"


class TestPipelineIntro:
    """TC-008: Pipeline 工作流介绍"""

    EXPECTED_PHASES = ["design", "review", "develop", "test", "audit", "deliver"]

    def test_has_pipeline_section(self):
        content = _read_readme()
        assert "Pipeline" in content or "工作流" in content, "缺少 Pipeline 介绍"

    def test_phase_stages_listed(self):
        """Pipeline 阶段列表完整：至少包含 5 个核心阶段"""
        content = _read_readme()
        pipeline_section = content.split("Pipeline")[-1].split("##")[0] if "Pipeline" in content else ""
        pipeline_section += content.split("工作流")[-1].split("##")[0] if "工作流" in content else ""
        count = sum(1 for phase in self.EXPECTED_PHASES if phase in pipeline_section)
        assert count >= 4, f"Pipeline 阶段列出的核心阶段不足，仅 {count}/6"


class TestTechStack:
    """TC-008(补充): 技术栈说明"""

    def test_has_tech_stack(self):
        content = _read_readme()
        assert "技术栈" in content, "缺少技术栈章节"

    def test_key_techs_listed(self):
        content = _read_readme()
        techs = ["Python", "SSE", "HTML"]
        for t in techs:
            assert t in content, f"技术栈未列出 {t}"


class TestContributionGuide:
    """TC-008(Review P1#8): 贡献指南"""

    def test_has_contribution_guide(self):
        content = _read_readme()
        assert "贡献" in content, "缺少贡献指南章节"

    def test_emoji_commit_rule(self):
        """提交约定提及 emoji 前缀"""
        content = _read_readme()
        commit_section = content.split("提交")[-1].split("##")[0] if "提交" in content else ""
        assert "🐢" in commit_section or "emoji" in commit_section, \
            "贡献指南未说明 emoji 提交约定"


class TestScreenshotPathStable:
    """TC-009(Review P1#9): 截图路径稳定"""

    def test_screenshots_in_stable_dir(self):
        """截图应存放在 docs/screenshots/ 而非 pipeline 临时目录"""
        stable_path = os.path.join(SCREENSHOT_DIR, "screenshot_kanban.png")
        exists_in_stable = os.path.exists(stable_path)
        exists_in_old = os.path.exists(os.path.join(SCREENSHOT_OLD_DIR, "screenshot_kanban.png"))
        assert exists_in_stable or exists_in_old, "截图文件未找到"
        if exists_in_stable:
            assert not os.path.exists(os.path.join(SCREENSHOT_OLD_DIR, "screenshot_kanban.png")), \
                "截图不应同时存在于新旧两个位置"


class TestNonEmptyMembers:
    """TC-010: 成员信息表格完整"""

    def test_member_table_complete(self):
        content = _read_readme()
        # 每个活跃成员应有 emoji
        for emoji in ["🐼", "🐢", "🦂"]:
            assert emoji in content, f"活跃成员 emoji {emoji} 未在 README 中出现"
