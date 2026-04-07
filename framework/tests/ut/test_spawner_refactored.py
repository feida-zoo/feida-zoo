"""
单元测试：重构后的 Spawner
测试重构后的 Spawner 使用 RegistryManager 和 WorkspaceManager 的正确性
"""

import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock

from framework.core.spawner import Spawner, MemberConfig
from framework.core.registry_manager import RegistryManager
from framework.core.workspace_manager import WorkspaceManager


class TestSpawnerRefactored:
    """重构后的 Spawner 测试"""

    def setup_method(self):
        """测试准备：创建临时目录"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        # 创建必要的目录结构
        (self.base_path / "agents").mkdir(parents=True)
        (self.base_path / "framework" / "shared").mkdir(parents=True)
        
        # 创建 data 目录和 registry.json 文件
        data_path = self.base_path / "framework" / "data"
        data_path.mkdir(parents=True, exist_ok=True)
        
        registry_file = data_path / "registry.json"
        registry_file.write_text('{"members": {}, "version": "1.0.0", "last_updated": null}')
        
        # 设置环境变量
        self.original_env = os.environ.get("FEIDA_ZOO_HOME")
        os.environ["FEIDA_ZOO_HOME"] = str(self.base_path)

    def teardown_method(self):
        """测试清理：恢复环境"""
        self.temp_dir.cleanup()
        if self.original_env is not None:
            os.environ["FEIDA_ZOO_HOME"] = self.original_env
        else:
            os.environ.pop("FEIDA_ZOO_HOME", None)

    def test_spawner_init_creates_managers(self):
        """测试 Spawner 初始化时创建 Manager 实例"""
        spawner = Spawner()
        
        assert hasattr(spawner, 'registry_manager')
        assert isinstance(spawner.registry_manager, RegistryManager)
        assert hasattr(spawner, 'workspace_manager')
        assert isinstance(spawner.workspace_manager, WorkspaceManager)

    def test_spawn_member_uses_managers(self):
        """测试 spawn_member 使用 Manager 类"""
        spawner = Spawner()

        # Mock 管理器方法
        with patch.object(spawner.workspace_manager, 'create_workspace') as mock_create:
            with patch.object(spawner.workspace_manager, 'save_meta') as mock_save_meta:
                with patch.object(spawner.registry_manager, 'register_member') as mock_register:
                    mock_create.return_value = self.base_path / "agents" / "testmember"
                    mock_save_meta.return_value = None

                    config = MemberConfig(
                        name="测试成员",
                        code_name="testmember",
                        role="engineer",
                        model="claude-3-5-sonnet",
                        workspace="",
                        capabilities=["coding", "testing"],
                        description="测试成员",
                        avatar=""
                    )

                    member = spawner.spawn_member(config)

                    # 验证调用了正确的方法
                    mock_create.assert_called_once()
                    mock_register.assert_called_once()
                    mock_save_meta.assert_called_once()

                    # 验证返回的成员对象
                    assert member.id == "testmember"
                    assert member.name == "测试成员"
                    assert member.role == "engineer"

    def test_list_members_uses_registry_manager(self):
        """测试 list_members 使用 RegistryManager"""
        spawner = Spawner()
        
        # Mock RegistryManager 的 list_members 方法
        test_members = [
            {"id": "member1", "name": "成员1", "code_name": "member1", "role": "engineer", "model": "test", "workspace": "/tmp/member1", "status": "active", "created_at": "2024-01-01T00:00:00", "capabilities": []},
            {"id": "member2", "name": "成员2", "code_name": "member2", "role": "engineer", "model": "test", "workspace": "/tmp/member2", "status": "active", "created_at": "2024-01-01T00:00:00", "capabilities": []}
        ]
        
        with patch.object(spawner.registry_manager, 'list_members') as mock_list:
            with patch.object(spawner.workspace_manager, 'load_meta') as mock_load_meta:
                mock_list.return_value = test_members
                mock_load_meta.return_value = {"name": "测试成员", "description": "测试描述"}
            
            members = spawner.list_members()
            
            mock_list.assert_called_once()
            assert len(members) == 2
            assert members[0].id == "member1"
            assert members[1].name == "成员2"

    def test_get_member_uses_registry_manager(self):
        """测试 get_member 使用 RegistryManager"""
        spawner = Spawner()
        
        test_member_data = {
            "id": "testmember",
            "name": "测试成员",
            "code_name": "testmember",
            "role": "engineer",
            "model": "claude-3-5-sonnet",
            "workspace": str(self.base_path / "agents" / "testmember"),
            "status": "active",
            "created_at": "2024-01-01T00:00:00",
            "capabilities": ["coding", "testing"]
        }
        
        with patch.object(spawner.registry_manager, 'get_member') as mock_get:
            mock_get.return_value = test_member_data
            
            member = spawner.get_member("testmember")
            
            mock_get.assert_called_once_with("testmember")
            assert member is not None
            assert member.id == "testmember"
            assert member.name == "测试成员"

    def test_update_member_status_uses_registry_manager(self):
        """测试 update_member_status 使用 RegistryManager"""
        spawner = Spawner()
        
        with patch.object(spawner.registry_manager, 'update_member_status') as mock_update:
            mock_update.return_value = True
            
            result = spawner.update_member_status("testmember", "suspended")
            
            mock_update.assert_called_once_with("testmember", "suspended")
            assert result is True

    def test_delete_member_uses_both_managers(self):
        """测试 delete_member 使用两个 Manager"""
        spawner = Spawner()

        with patch.object(spawner.workspace_manager, 'delete_workspace') as mock_delete_ws:
            with patch.object(spawner.registry_manager, 'delete_member') as mock_delete_reg:
                mock_delete_ws.return_value = True
                mock_delete_reg.return_value = True

                result = spawner.delete_member("testmember")

                mock_delete_ws.assert_called_once_with("testmember")
                mock_delete_reg.assert_called_once_with("testmember")
                assert result is True

    def test_spawn_member_error_handling(self):
        """测试 spawn_member 的错误处理"""
        spawner = Spawner()
        
        config = MemberConfig(
            name="测试成员",
            code_name="testmember",
            role="engineer",
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding", "testing"],
            description="测试成员",
            avatar=""
        )
        
        # 测试工作空间创建失败
        with patch.object(spawner.workspace_manager, 'create_workspace', side_effect=Exception("创建工作空间失败")):
            with pytest.raises(Exception, match="创建工作空间失败"):
                spawner.spawn_member(config)
        
        # 测试成员注册失败
        with patch.object(spawner.workspace_manager, 'create_workspace') as mock_create:
            with patch.object(spawner.workspace_manager, 'save_meta') as mock_save_meta:
                with patch.object(spawner.registry_manager, 'register_member', side_effect=Exception("注册成员失败")):
                    mock_create.return_value = self.base_path / "agents" / "testmember"
                    mock_save_meta.return_value = None

                    with pytest.raises(Exception, match="注册成员失败"):
                        spawner.spawn_member(config)

    def test_backward_compatibility(self):
        """测试向后兼容性 - 原有API保持不变"""
        spawner = Spawner()
        
        # 验证所有原有public方法都存在
        public_methods = [
            'spawn_member',
            'list_members',
            'get_member',
            'update_member_status',
            'delete_member'
        ]
        
        for method in public_methods:
            assert hasattr(spawner, method)
            assert callable(getattr(spawner, method))

    def test_config_loader_integration(self):
        """测试与 ConfigLoader 的集成"""
        spawner = Spawner()
        
        # 验证Spawner使用了配置化的路径
        assert hasattr(spawner, 'base_path')
        assert hasattr(spawner, 'agents_path')
        assert hasattr(spawner, 'registry_file')
        
        # 验证路径是正确的
        assert str(spawner.base_path) == str(self.base_path)
        assert spawner.agents_path == self.base_path / "agents"
        assert spawner.registry_file == self.base_path / "framework" / "data" / "registry.json"