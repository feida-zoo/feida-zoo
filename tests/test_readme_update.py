#!/usr/bin/env python3
"""
pl_6932a56b — README 更新测试用例
覆盖设计文档全部 8 项验收检查点 + Verify REJECT 修复
"""
import os
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")
SCREENSHOT_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
SCREENSHOT_PIPELINE_DIR = os.path.join(REPO_ROOT, "docs", "pipeline")

REQUIRED_SCREENSHOTS = [
    "screenshot_kanban.png",
    "screenshot_members.png",
    "screenshot_chat.png",
]
OPTIONAL_SCREENSHOTS = ["screenshot_requirements.png"]
EXPECTED_PHASES = ["requirement", "design", "review", "develop", "test", "audit", "deliver"]
EXPECTED_DIRS = ["agents", "dashboard", "framework", "scripts", "plugins", "skills"]


# ============================================================
# Helper
# ============================================================

def _read_readme():
    """读取 README.md"""
    assert os.path.exists(README_PATH), f"README.md 不存在于 {README_PATH}"
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _screenshot_path(name):
    """仅检查稳定目录 docs/screenshots/ 中的截图"""
    return os.path.join(SCREENSHOT_DIR, name)


def _extract_section(content, title):
    """提取 ## {title} 节的内容（到下个 ## 为止）"""
    idx = content.find(f"## {title}")
    if idx == -1:
        return None
    # 同级别或更高级别标题
    next_idx = re.search(r"\n##(?!\#) ", content[idx + 3:])
    if next_idx:
        return content[idx:idx + 3 + next_idx.start()]
    return content[idx:]


# ============================================================
# TC-001: README 文件存在
# ============================================================

class TestReadmeExists:
    """TC-001: README 文件存在"""

    def test_readme_exists(self):
        assert os.path.exists(README_PATH), "README.md 不存在"


# ============================================================
# TC-002: 成员列表 — 活跃/归档拆分
# ============================================================

class TestActiveMembers:
    """TC-002: 成员列表 — 活跃成员+归档拆分"""

    ACTIVE = ["达达", "Panda", "阿尔法", "Alpha", "毒刺", "Duci"]
    ARCHIVED = ["织巢", "Weaver", "埃特娜", "Aeterna", "咕噜", "Gulu"]
    ACTIVE_EMOJIS = ["🐼", "🐢", "🦂"]

    def test_active_members_present(self):
        content = _read_readme()
        for name in self.ACTIVE:
            assert name in content, f"活跃成员 {name} 未出现在 README 中"

    def test_ex_members_not_in_active_table(self):
        """已退出成员不可出现在活跃成员表中（可在归档区出现）。
        检查「已归档成员」小节标题存在、且已退出成员不在活跃成员表格中。"""
        content = _read_readme()
        member_section = _extract_section(content, "成员列表") or ""
        # 检查归档小节标题
        has_archive_heading = (
            "### 已归档" in member_section or
            "### 归档" in member_section or
            "## 归档" in member_section or
            "### 已退出" in member_section
        )
        if not has_archive_heading:
            for name in self.ARCHIVED:
                assert name not in content, \
                    f"已退出成员 {name} 出现在 README 中但无归档标注"
            return
        # 有归档标注 → 提取活跃子节与归档子节之间的文本（活跃表格部分）
        # 活跃子节内容：从「### 活跃成员」到「### 已归档成员」或到「## 」下一节
        active_marker = "### 活跃成员"
        archive_marker = "### 已归档"
        if active_marker in member_section:
            active_text = member_section.split(active_marker)[-1]
            if archive_marker in active_text:
                active_text = active_text.split(archive_marker)[0]
            else:
                active_text = active_text.split("\n###")[0] if "\n###" in active_text else active_text
            for name in self.ARCHIVED:
                assert name not in active_text, \
                    f"已退出成员 {name} 出现在活跃成员表格中"

    def test_active_emojis_present(self):
        content = _read_readme()
        for emoji in self.ACTIVE_EMOJIS:
            assert emoji in content, f"活跃成员 emoji {emoji} 未在 README 中出现"


# ============================================================
# TC-003: 核心守则完整可读
# ============================================================

class TestCoreRules:
    """TC-003: 核心守则完整可读"""

    MIN_RULES_LENGTH = 100   # 比原 50 翻倍，避免空章节误判

    def test_core_rules_not_empty(self):
        content = _read_readme()
        assert "核心守则" in content, "核心守则章节缺失"
        rules_section = content.split("核心守则")[-1].split("\n##")[0]
        # 校验不是空链接（旧版 README 的「详见」）
        assert "详见" not in rules_section, "核心守则后存在「详见」空链接"
        assert len(rules_section.strip()) >= self.MIN_RULES_LENGTH, \
            f"核心守则内容不足 {self.MIN_RULES_LENGTH} 字"

    def test_core_rules_contains_rules(self):
        content = _read_readme()
        rules_section = content.split("核心守则")[-1].split("\n##")[0]
        keywords = ["不得", "必须", "禁止", "应当", "🐢", "🦂", "🐼"]
        assert any(k in rules_section for k in keywords), \
            "核心守则未包含实质性规则词"


# ============================================================
# TC-004: 截图存在 + 引用格式 + 稳定性
# ============================================================

class TestScreenshots:
    """TC-004/TC-009: 截图存在·非空·引用格式稳定"""

    def test_minimum_screenshots(self):
        count = sum(1 for s in REQUIRED_SCREENSHOTS
                    if os.path.exists(_screenshot_path(s)))
        assert count >= 3, f"必要截图不足，仅找到 {count}/3 在 docs/screenshots/"

    def test_screenshots_not_empty(self):
        for name in REQUIRED_SCREENSHOTS:
            path = _screenshot_path(name)
            if not os.path.exists(path):
                continue
            size = os.path.getsize(path)
            assert size > 10240, f"{name} 疑似空截图（仅 {size} bytes）"
            assert size < 2 * 1024 * 1024, f"{name} 文件过大（{size} bytes）"

    def test_screenshots_in_stable_dir(self):
        """截图必须在 docs/screenshots/，不在 pipeline 临时目录。"""
        for name in REQUIRED_SCREENSHOTS:
            stable = _screenshot_path(name)
            old = os.path.join(SCREENSHOT_PIPELINE_DIR, name)
            assert os.path.exists(stable), f"{name} 不在 docs/screenshots/ 中"
            assert not os.path.exists(old), \
                f"{name} 不应同时存在于 docs/pipeline/（冗余旧位置）"

    def test_screenshot_markdown_ref_format(self):
        """README 中截图引用必须是有效 Markdown 图片语法"""
        content = _read_readme()
        refs = re.findall(r'!\[.*?\]\(.*?\.png\)', content)
        assert len(refs) >= 2, f"Markdown 截图引用不足 2 个，仅找到 {len(refs)}"
        # 所有引用路径不得指向 pipeline 目录
        bad_refs = [r for r in refs if "docs/pipeline/" in r]
        assert len(bad_refs) == 0, f"截图引用指向 pipeline 临时目录: {bad_refs}"


# ============================================================
# TC-005: 项目概述
# ============================================================

class TestProjectOverview:
    """TC-005: 项目概述存在"""

    def test_has_project_overview(self):
        content = _read_readme()
        assert "项目概述" in content or "简介" in content, "缺少项目概述章节"

    def test_overview_not_empty(self):
        content = _read_readme()
        overview = content.split("项目概述")[-1].split("\n##")[0] \
            if "项目概述" in content else ""
        overview = overview or (content.split("简介")[-1].split("\n##")[0]
                                if "简介" in content else "")
        assert len(overview.strip()) > 50, "项目概述内容过短"


# ============================================================
# TC-006: 目录结构
# ============================================================

class TestDirectoryStructure:
    """TC-006: 目录结构说明"""

    def test_directory_structure_section(self):
        content = _read_readme()
        assert "项目结构" in content or "目录结构" in content, "缺少项目结构章节"

    def test_key_directories_listed(self):
        content = _read_readme()
        struct_section = content.split("项目结构")[-1].split("\n##")[0] \
            if "项目结构" in content else ""
        struct_section = struct_section or (content.split("目录结构")[-1].split("\n##")[0]
                                             if "目录结构" in content else "")
        for d in EXPECTED_DIRS:
            assert d in struct_section, f"核心目录 {d} 未在项目结构中列出"


# ============================================================
# TC-007: 运行指南 + 无硬编码路径
# ============================================================

class TestRunGuide:
    """TC-007: 运行指南完整 + 硬编码路径检查"""

    def test_has_run_guide(self):
        content = _read_readme()
        assert "快速开始" in content or "启动" in content or "运行指南" in content, \
            "缺少运行指南章节"

    def test_has_start_command(self):
        """检查代码块中的启动命令，避免中文「系统设计」误匹配 'sh '"""
        content = _read_readme()
        # 查找代码块
        code_blocks = re.findall(r'```.*?\n(.*?)```', content, re.DOTALL)
        code_text = "\n".join(code_blocks)
        # 在代码块中查找命令模式
        has_cmd = bool(re.search(r'(python3?\s|bash\s|\.\/[\w/]+\.sh)', code_text))
        assert has_cmd, "运行指南缺少启动命令（代码块中无 python3/bash/./脚本）"

    def test_has_access_address(self):
        content = _read_readme()
        assert "18792" in content or "localhost" in content or "http://" in content, \
            "运行指南缺少访问地址"

    def test_env_var_mentioned(self):
        content = _read_readme()
        assert "FEIDA_ZOO_HOME" in content or "环境变量" in content, \
            "运行指南未提及环境变量说明"

    def test_no_hardcoded_user_paths(self):
        """README 不应包含硬编码用户路径（/home/ /Users/ 等）"""
        content = _read_readme()
        bad_patterns = re.findall(r'/(?:home|Users)/[a-zA-Z0-9_-]+', content)
        assert len(bad_patterns) == 0, \
            f"READEM 中包含硬编码用户路径: {bad_patterns}"


# ============================================================
# TC-008: Pipeline + 技术栈 + 贡献指南
# ============================================================

class TestPipelineIntro:
    """TC-008(1): Pipeline 工作流介绍"""

    def test_has_pipeline_section(self):
        content = _read_readme()
        assert "Pipeline" in content or "工作流" in content, "缺少 Pipeline 介绍"

    def test_phase_stages_listed(self):
        """全部 7 阶段列在 README 中（中英文均可）"""
        content = _read_readme()
        # 用精确标题定位 Pipeline 节
        pipeline_marker = "## Pipeline 工作流" if "## Pipeline 工作流" in content else "## Pipeline"
        if pipeline_marker in content:
            pipeline_section = content.split(pipeline_marker)[-1].split("\n##")[0]
        else:
            pipeline_section = ""
        # 检查英文阶段名（如 design/review/develop）或中文标签（如 设计/审查/开发）
        cn_labels = ["需求", "设计", "审查", "开发", "测试", "审计", "交付"]
        en_found = sum(1 for phase in EXPECTED_PHASES if phase in pipeline_section)
        cn_found = sum(1 for label in cn_labels if label in pipeline_section)
        assert en_found + cn_found >= 7, f"Pipeline 阶段不全，expected 7, found en={en_found} cn={cn_found}"


class TestTechStack:
    """TC-008(2): 技术栈说明"""

    def test_has_tech_stack(self):
        content = _read_readme()
        assert "技术栈" in content, "缺少技术栈章节"

    def test_key_techs_listed(self):
        content = _read_readme()
        for t in ["Python", "HTML"]:
            assert t in content, f"技术栈未列出 {t}"


class TestContributionGuide:
    """TC-008(3): 贡献指南 — Review P1#8"""

    def test_has_contribution_guide(self):
        content = _read_readme()
        assert "贡献" in content, "缺少贡献指南章节"

    def test_emoji_commit_rule(self):
        content = _read_readme()
        commit_section = content.split("提交")[-1].split("\n##")[0] \
            if "提交" in content else ""
        assert "🐢" in commit_section or "emoji" in commit_section, \
            "贡献指南未说明 emoji 提交约定"


# ============================================================
# TC-010: Markdown 格式有效性
# ============================================================

class TestMarkdownFormat:
    """TC-010: Markdown 表格语法有效"""

    def test_table_has_separator_line(self):
        """表格分隔行 `|---|---|` 存在"""
        content = _read_readme()
        tables = re.findall(r'^.*\|.*$', content, re.MULTILINE)
        has_separator = any("---" in line and "|" in line for line in tables)
        assert has_separator, "README 表格缺少分隔行（|---|---|）"


# ============================================================
# 边界检查
# ============================================================

class TestArchivedMembersIntegrity:
    """归档成员信息完整性"""

    ARCHIVED_NAMES = ["织巢", "Weaver", "埃特娜", "Aeterna", "咕噜", "Gulu"]
    ARCHIVED_EMOJIS = ["🐜", "🪨", "🟢"]

    def test_archived_members_information(self):
        content = _read_readme()
        archived_present = [n for n in self.ARCHIVED_NAMES if n in content]
        if not archived_present:
            pytest.skip("README 中无归档成员信息，跳过完整性校验")
        # 至少包含部分 emoji
        emoji_found = [e for e in self.ARCHIVED_EMOJIS if e in content]
        assert len(emoji_found) >= 1, "归档成员无 emoji 标识"
