"""
单元测试：WorkspaceManager - 成员工作区管理器
测试覆盖：
- 创建工作区
- 检查工作区存在性
- 保存和加载元数据
- 更新元数据
- 删除工作区
- 列出工作区
"""

import tempfile
from pathlib import Path
import pytest

from framework.core.workspace_manager import WorkspaceManager


class TestWorkspaceManager:
    """WorkspaceManager 单元测试"""

    def setup_method(self):
        """测试准备：创建临时目录"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.agents_path = Path(self.temp_dir.name) / "agents"

    def teardown_method(self):
        """测试清理：删除临时目录"""
        self.temp_dir.cleanup()

    def test_init_creates_base_directory(self):
        """测试初始化时创建根目录"""
        assert not self.agents_path.exists()

        manager = WorkspaceManager(self.agents_path)

        assert self.agents_path.exists()
        assert self.agents_path.is_dir()

    def test_create_workspace_success(self):
        """测试成功创建工作区"""
        manager = WorkspaceManager(self.agents_path)
        workspace_path = manager.create_workspace("test_member")

        assert workspace_path.exists()
        assert workspace_path.is_dir()

        # 检查标准子目录
        for subdir in ["src", "docs", "outputs"]:
            subdir_path = workspace_path / subdir
            assert subdir_path.exists()
            assert subdir_path.is_dir()

        assert manager.workspace_exists("test_member") is True

    def test_create_workspace_already_exists_raises_error(self):
        """测试创建已存在的工作区抛出错误"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")

        with pytest.raises(ValueError, match="成员工作区 'test_member' 已存在"):
            manager.create_workspace("test_member")

    def test_get_workspace_path_returns_correct_path(self):
        """测试获取正确的工作区路径"""
        manager = WorkspaceManager(self.agents_path)
        workspace_path = manager.get_workspace_path("test_member")

        expected = self.agents_path.resolve() / "test_member"
        assert workspace_path == expected

    def test_get_meta_file_path_returns_correct_path(self):
        """测试获取正确的元数据文件路径"""
        manager = WorkspaceManager(self.agents_path)
        meta_path = manager.get_meta_file_path("test_member")

        expected = self.agents_path.resolve() / "test_member" / "member.json"
        assert meta_path == expected

    def test_workspace_exists_returns_false_when_not_exists(self):
        """测试工作区不存在时返回 False"""
        manager = WorkspaceManager(self.agents_path)

        assert manager.workspace_exists("nonexistent") is False

    def test_save_meta_success(self):
        """测试成功保存元数据"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")

        meta_data = {
            "name": "Test Member",
            "code_name": "test_member",
            "role": "engineer",
            "model": "gpt-4",
            "capabilities": ["coding", "debugging"]
        }

        manager.save_meta("test_member", meta_data)

        meta_file = manager.get_meta_file_path("test_member")
        assert meta_file.exists()

        # 验证读取
        loaded = manager.load_meta("test_member")
        assert loaded is not None
        assert loaded["name"] == "Test Member"
        assert loaded["code_name"] == "test_member"
        assert loaded["role"] == "engineer"
        assert "updated_at" in loaded  # 自动添加更新时间戳

    def test_save_meta_fails_when_workspace_not_exists(self):
        """测试工作区不存在时保存元数据抛出错误"""
        manager = WorkspaceManager(self.agents_path)

        with pytest.raises(ValueError, match="成员工作区 'nonexistent' 不存在"):
            manager.save_meta("nonexistent", {"name": "Test"})

    def test_load_meta_returns_none_when_not_exists(self):
        """测试元数据不存在时返回 None"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")  # 创建工作区但不保存元数据

        result = manager.load_meta("test_member")
        assert result is None

    def test_load_meta_returns_none_for_nonexistent_workspace(self):
        """测试工作区不存在时返回 None"""
        manager = WorkspaceManager(self.agents_path)

        result = manager.load_meta("nonexistent")
        assert result is None

    def test_update_meta_success(self):
        """测试成功更新元数据"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")

        # 初始保存
        initial_meta = {
            "name": "Original Name",
            "role": "engineer",
            "status": "active"
        }
        manager.save_meta("test_member", initial_meta)

        # 更新部分字段
        success = manager.update_meta("test_member", {
            "name": "Updated Name",
            "role": "architect",
            "new_field": "added"
        })

        assert success is True

        loaded = manager.load_meta("test_member")
        assert loaded["name"] == "Updated Name"
        assert loaded["role"] == "architect"
        assert loaded["status"] == "active"  # 原有字段保留
        assert loaded["new_field"] == "added"  # 新增字段
        assert "updated_at" in loaded

    def test_update_meta_fails_when_not_exists(self):
        """测试更新不存在的元数据返回 False"""
        manager = WorkspaceManager(self.agents_path)

        success = manager.update_meta("nonexistent", {"name": "test"})
        assert success is False

    def test_update_meta_field_success(self):
        """测试成功更新单个字段"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")
        manager.save_meta("test_member", {"name": "Test", "status": "active"})

        success = manager.update_meta_field("test_member", "status", "suspended")

        assert success is True
        loaded = manager.load_meta("test_member")
        assert loaded["status"] == "suspended"

    def test_delete_workspace_success(self):
        """测试成功删除工作区"""
        manager = WorkspaceManager(self.agents_path)
        manager.create_workspace("test_member")
        manager.save_meta("test_member", {"name": "Test"})

        assert manager.workspace_exists("test_member") is True
        assert len(list(self.agents_path.iterdir())) == 1

        success = manager.delete_workspace("test_member")

        assert success is True
        assert manager.workspace_exists("test_member") is False
        assert len(list(self.agents_path.iterdir())) == 0

    def test_delete_workspace_fails_when_not_exists(self):
        """测试删除不存在的工作区返回 False"""
        manager = WorkspaceManager(self.agents_path)

        success = manager.delete_workspace("nonexistent")
        assert success is False

    def test_list_workspace_ids_returns_all_valid_workspaces(self):
        """测试列出所有有效工作区ID"""
        manager = WorkspaceManager(self.agents_path)

        # 创建两个有元数据的工作区
        manager.create_workspace("member1")
        manager.save_meta("member1", {"name": "Member 1"})

        manager.create_workspace("member2")
        manager.save_meta("member2", {"name": "Member 2"})

        # 创建一个没有元数据的空目录
        (self.agents_path / "empty_dir").mkdir()

        result = manager.list_workspace_ids()

        assert len(result) == 2
        assert "member1" in result
        assert "member2" in result
        assert "empty_dir" not in result

    def test_list_workspace_ids_empty_when_no_workspaces(self):
        """测试没有工作区时返回空列表"""
        manager = WorkspaceManager(self.agents_path)

        result = manager.list_workspace_ids()
        assert result == []

    def test_get_and_set_storage_adapter(self):
        """测试获取和设置存储适配器"""
        manager = WorkspaceManager(self.agents_path)
        adapter = manager.get_storage_adapter()

        assert adapter is not None

        # 不测试自定义适配器，这里只验证接口工作
        new_adapter = manager.get_storage_adapter()
        manager.set_storage_adapter(new_adapter)

        assert manager.get_storage_adapter() is new_adapter
