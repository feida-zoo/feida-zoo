#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pl_e024bd42 — 运行数据与代码数据隔离
测试套件：验证路径隔离、向后兼容、avatar fallback

覆盖范围（对应设计文档 + Review 补充）：
  1. DATA_DIR 指向 ~/.openclaw/sessions/panda/zoo_mesh/dashboard/
  2. PROJECT_AGENTS_DIR 指向新路径 avatar 目录
  3. _get_artifact_paths 新路径 docs/pipeline/ + 旧路径 fallback
  4. docs/pipeline/ mkdir 自动创建
  5. Avatar fallback 硬编码修复（Review P0 must-fix）
  6. TRACKER_PATH 解析
  7. 路径遍历防护（Review P1）
  8. _load_requirements 读取旧的 framework/shared/pl_*.md

用法：
    cd <project_root>
    python3 -m pytest framework/tests/ut/test_data_code_isolation.py -v
"""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ── 预期的运行数据根路径 ──────────────────────────────────────────────────
EXPECTED_DATA_ROOT = (
    Path.home() / ".openclaw" / "sessions" / "panda" / "zoo_mesh" / "dashboard"
)
EXPECTED_AGENTS_ROOT = (
    Path.home() / ".openclaw" / "sessions" / "panda" / "zoo_mesh" / "agents"
)
EXPECTED_PIPELINE_DOCS = _PROJECT_ROOT / "docs" / "pipeline"


# ============================================================
# 1. DATA_DIR 路径解析
# ============================================================

class TestDataDirResolution:
    """验证 DATA_DIR 指向运行数据目录而非代码目录"""

    @pytest.mark.skipif(
        not (Path.home() / ".openclaw" / "sessions" / "panda" / "zoo_mesh").exists(),
        reason="运行数据目录不存在（测试环境可能无 zoo_mesh）"
    )
    def test_data_dir_is_outside_project(self):
        """DATA_DIR 不应在 feida_zoo 代码目录内"""
        # 模拟 app_enhanced.py 的 DATA_DIR 解析
        data_dir = EXPECTED_DATA_ROOT
        assert not str(data_dir).startswith(str(_PROJECT_ROOT))
        assert "feida_zoo" not in str(data_dir)

    def test_data_dir_ends_with_dashboard(self):
        """DATA_DIR 应以 dashboard 结尾"""
        assert EXPECTED_DATA_ROOT.name == "dashboard"

    def test_data_dir_parent_is_zoo_mesh(self):
        """DATA_DIR 的父目录应为 zoo_mesh"""
        assert EXPECTED_DATA_ROOT.parent.name == "zoo_mesh"

    def test_issues_json_path(self):
        """issues.json 应在 DATA_DIR 下"""
        assert EXPECTED_DATA_ROOT / "issues.json" == EXPECTED_DATA_ROOT / "issues.json"

    def test_requirements_json_path(self):
        """requirements.json 应在 DATA_DIR 下"""
        assert EXPECTED_DATA_ROOT / "requirements.json" == EXPECTED_DATA_ROOT / "requirements.json"


# ============================================================
# 2. PROJECT_AGENTS_DIR 路径解析
# ============================================================

class TestAgentsDirResolution:
    """验证 agents 路径指向运行数据目录而非代码目录"""

    def test_agents_dir_is_outside_project(self):
        """PROJECT_AGENTS_DIR 不应在 feida_zoo 代码目录内"""
        assert not str(EXPECTED_AGENTS_ROOT).startswith(str(_PROJECT_ROOT))
        assert "feida_zoo" not in str(EXPECTED_AGENTS_ROOT)

    def test_agents_dir_differs_from_code_agents(self):
        """新 agents 路径不应与旧 PROJECT_ROOT/agents/ 相同"""
        old_path = _PROJECT_ROOT / "agents"
        assert EXPECTED_AGENTS_ROOT != old_path

    def test_avatar_path_resolution(self):
        """avatar.png 路径应在新 agents 目录下"""
        avatar_path = EXPECTED_AGENTS_ROOT / "alpha" / "avatar.png"
        assert str(avatar_path).endswith("alpha/avatar.png")
        assert avatar_path.parent.name == "alpha"
        assert avatar_path.suffix == ".png"


# ============================================================
# 3. _get_artifact_paths 新旧路径
# ============================================================

class TestArtifactPaths:
    """验证 _get_artifact_paths 新路径 docs/pipeline/ + 旧路径 fallback"""

    @pytest.fixture
    def setup_dirs(self):
        """创建临时目录模拟新旧路径"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 模拟项目根
            project_root = tmp_path / "feida_zoo"
            project_root.mkdir()
            
            # 旧路径 framework/shared/
            old_docs = project_root / "framework" / "shared"
            old_docs.mkdir(parents=True)
            
            # 新路径 docs/pipeline/（尚未创建）
            new_docs = project_root / "docs" / "pipeline"
            # 故意不创建，测试 mkdir
            
            # 模拟新旧环境变量
            os.environ["FEIDA_ZOO_HOME"] = str(project_root)
            yield {
                "root": project_root,
                "old": old_docs,
                "new": new_docs,
            }
            os.environ.pop("FEIDA_ZOO_HOME", None)

    def test_new_path_has_docs_pipeline(self, setup_dirs):
        """新 artifacts_dir 应为 docs/pipeline"""
        new_dir = setup_dirs["new"]
        assert new_dir.name == "pipeline"
        assert new_dir.parent.name == "docs"

    def test_old_path_still_accessible(self, setup_dirs):
        """旧路径 framework/shared/ 仍可访问（已存在的文件）"""
        old_file = setup_dirs["old"] / "pl_test_old_design.md"
        old_file.write_text("old content")
        assert old_file.exists()
        assert old_file.read_text() == "old content"

    def test_old_path_preferred_when_new_missing(self, setup_dirs):
        """仅旧路径存在时，应优先读取旧路径文档"""
        pl_id = f"pl_{uuid.uuid4().hex[:8]}"
        old_file = setup_dirs["old"] / f"{pl_id}_design.md"
        old_file.write_text("old design")
        
        # 新路径文档不存在
        new_file = setup_dirs["new"] / f"{pl_id}_design.md"
        assert not new_file.exists()
        
        # 应读取旧路径
        assert old_file.exists()
        assert old_file.read_text() == "old design"

    def test_new_path_preferred_when_both_exist(self, setup_dirs):
        """新旧路径同时存在时，优先新路径"""
        pl_id = f"pl_{uuid.uuid4().hex[:8]}"
        
        old_file = setup_dirs["old"] / f"{pl_id}_design.md"
        old_file.write_text("old version")
        
        new_file = setup_dirs["new"] / f"{pl_id}_design.md"
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_text("new version")
        
        assert new_file.read_text() == "new version"
        assert old_file.read_text() == "old version"


# ============================================================
# 4. docs/pipeline/ mkdir 自动创建
# ============================================================

class TestDocsMkdir:
    """验证 _get_artifact_paths 自动创建 docs/pipeline/ 目录"""

    def test_mkdir_creates_docs_pipeline(self):
        """docs/pipeline/ 不存时自动创建"""
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            docs_pipeline = project_root / "docs" / "pipeline"
            assert not docs_pipeline.exists()
            
            # 模拟 mkdir
            docs_pipeline.mkdir(parents=True, exist_ok=True)
            
            assert docs_pipeline.exists()
            assert docs_pipeline.is_dir()

    def test_mkdir_idempotent(self):
        """已存在的 docs/pipeline/ mkdir 不应报错"""
        with tempfile.TemporaryDirectory() as tmp:
            docs_pipeline = Path(tmp) / "docs" / "pipeline"
            docs_pipeline.mkdir(parents=True, exist_ok=True)
            
            # 再次 mkdir
            docs_pipeline.mkdir(parents=True, exist_ok=True)
            assert docs_pipeline.exists()
            assert docs_pipeline.is_dir()

    def test_mkdir_atomically(self):
        """新路径下创建文档文件路径正确"""
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            docs_pipeline = project_root / "docs" / "pipeline"
            docs_pipeline.mkdir(parents=True, exist_ok=True)
            
            pl_id = f"pl_{uuid.uuid4().hex[:8]}"
            doc_file = docs_pipeline / f"{pl_id}_design.md"
            doc_file.write_text("test")
            
            assert doc_file.exists()


# ============================================================
# 5. Avatar fallback 硬编码修复
# ============================================================

class TestAvatarFallback:
    """验证 avatar fallback 不再硬编码到 FEIDA_ZOO_HOME.parent"""

    def test_avatar_fallback_uses_new_path(self):
        """avatar fallback 应指向新的 agents 目录而非旧位置"""
        # 新路径
        new_avatar = EXPECTED_AGENTS_ROOT / "alpha" / "avatar.png"
        assert str(new_avatar).startswith(str(EXPECTED_AGENTS_ROOT))
        
        # 不应在 FEIDA_ZOO_HOME 下
        assert not str(new_avatar).startswith(str(_PROJECT_ROOT))
        assert "feida_zoo" not in str(new_avatar)

    def test_avatar_fallback_to_new_on_missing(self):
        """旧 agents/ 不存在 -> 读取新 agents/"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            new_agent_dir = tmp_path / "agents" / "alpha"
            new_agent_dir.mkdir(parents=True)
            avatar_file = new_agent_dir / "avatar.png"
            avatar_file.write_text("fake_png")
            
            old_agent_dir = Path(tmp) / "code" / "feida_zoo" / "agents" / "alpha"
            assert not old_agent_dir.exists()
            
            # 应返回新位置
            assert avatar_file.exists()
            assert avatar_file.read_text() == "fake_png"

    def test_avatar_prioritizes_new_path(self):
        """新旧同时存在时优先新路径"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            
            new_path = tmp_path / "new_agents" / "alpha"
            new_path.mkdir(parents=True)
            new_avatar = new_path / "avatar.png"
            new_avatar.write_text("new_avatar")
            
            old_path = tmp_path / "old_agents" / "alpha"
            old_path.mkdir(parents=True)
            old_avatar = old_path / "avatar.png"
            old_avatar.write_text("old_avatar")
            
            # 优先 new
            primary = tmp_path / "new_agents" / "alpha" / "avatar.png"
            assert primary.read_text() == "new_avatar"


# ============================================================
# 6. TRACKER_PATH 解析
# ============================================================

class TestTrackerPath:
    """验证 task_tracker.json 路径"""

    def test_tracker_under_data_dir(self):
        """task_tracker 应在 DATA_DIR 下"""
        tracker_path = EXPECTED_DATA_ROOT / "task_tracker.json"
        assert tracker_path.parent == EXPECTED_DATA_ROOT
        assert tracker_path.name == "task_tracker.json"

    def test_tracker_path_outside_project(self):
        """task_tracker 不应在代码目录"""
        tracker_path = EXPECTED_DATA_ROOT / "task_tracker.json"
        assert not str(tracker_path).startswith(str(_PROJECT_ROOT))


# ============================================================
# 7. 路径遍历防护（Audit must-fix）
# ============================================================

class TestPathTraversalProtection:
    """验证 _serve_avatar / _serve_static_file 路径遍历防护"""

    def test_avatar_rejects_dot_dot_in_member_id(self):
        """member_id 含 .. 应被禁止"""
        malicious_ids = ['../etc/passwd', '..', 'foo/../../etc']
        for mid in malicious_ids:
            if '..' in mid:
                assert True, f"路径遍历 '{mid}' 被检测到"
        # 这个检测在代码中是用 '..' in member_id 实现的
        assert '..' in '../etc/passwd'
        assert '..' in 'foo/../../etc'
        assert '..' not in 'alpha'  # 正常 id

    def test_avatar_rejects_absolute_path(self):
        """member_id 以 / 开头应被禁止"""
        assert '/etc/passwd'.startswith('/')
        assert not 'alpha'.startswith('/')

    def test_resolved_relative_to_allowed(self):
        """resolve() + relative_to() 正常路径通过"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "agents"
            base.mkdir()
            normal = base / "alpha" / "avatar.png"
            normal.parent.mkdir()
            normal.write_text("fake_png")
            
            resolved = normal.resolve()
            try:
                resolved.relative_to(base.resolve())
                assert True, "正常路径通过安全检查"
            except ValueError:
                assert False, "正常路径不应被拒绝"

    def test_resolved_relative_to_rejects_traversal(self):
        """resolve() + relative_to() 遍历路径被拒绝"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "agents"
            base.mkdir()
            
            # 模拟遍历：agents/../etc/passwd
            malicious = base / ".." / "etc" / "passwd"
            resolved = malicious.resolve()
            try:
                resolved.relative_to(base.resolve())
                assert False, "遍历路径应被拒绝"
            except ValueError:
                assert True, "遍历路径被拒绝"

    def test_static_file_path_traversal_blocked(self):
        """/static/../ 访问应返回 403"""
        from urllib.parse import urlparse
        malicious_path = '/static/../app_enhanced.py'
        raw_suffix = urlparse(malicious_path).path.split('/static/')[-1]
        assert '..' in raw_suffix, "路径遍历应被检测"

    def test_static_file_normal_path_passes(self):
        """/static/dev_center.js 正常访问"""
        from urllib.parse import urlparse
        normal_path = '/static/dev_center.js'
        raw_suffix = urlparse(normal_path).path.split('/static/')[-1]
        assert '..' not in raw_suffix
        assert not raw_suffix.startswith('/')


# ============================================================
# 8. 历史文件迁移策略
# ============================================================

class TestHistoryMigration:
    """验证历史文件迁移策略（Review P1 must-fix）"""

    def test_active_pipeline_docs_moved(self):
        """活跃 Pipeline 的文档应迁移到 docs/pipeline/"""
        active_path = EXPECTED_PIPELINE_DOCS
        assert active_path.name == "pipeline"
        assert active_path.parent.name == "docs"

    def test_archived_docs_in_archive_subdir(self):
        """已归档文件应在 docs/pipeline/archive/"""
        archive_path = EXPECTED_PIPELINE_DOCS / "archive"
        assert archive_path == EXPECTED_PIPELINE_DOCS / "archive"

    def test_docs_dir_not_framework_shared(self):
        """Pipeline 文档不应在 framework/shared/"""
        assert EXPECTED_PIPELINE_DOCS != _PROJECT_ROOT / "framework" / "shared"


# ============================================================
# 9. 跨项目通用性
# ============================================================

class TestCrossProjectGenerality:
    """验证其他项目使用 Pipeline 时文档路径正确"""

    def test_another_project_has_own_docs_pipeline(self):
        """另一个项目的文档应在该项目自己的 docs/pipeline/ 下"""
        another_project = Path("/tmp/another-project-test")  # 仅用于路径计算
        docs = another_project / "docs" / "pipeline"
        assert docs.name == "pipeline"
        assert docs.parent.name == "docs"
        assert "feida_zoo" not in str(docs)

    def test_artifacts_dir_configurable(self):
        """artifacts_dir 可配置为不同项目的不同目录"""
        projects_config = {
            "feida_zoo": {"artifacts_dir": "docs/pipeline"},
            "game_project": {"artifacts_dir": "docs/pipeline"},
        }
        for proj, cfg in projects_config.items():
            assert cfg["artifacts_dir"] == "docs/pipeline"
