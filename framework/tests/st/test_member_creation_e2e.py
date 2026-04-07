"""
端到端测试：成员创建流程
测试完整的成员创建、管理、删除生命周期
"""

import os
import tempfile
import json
from pathlib import Path
import pytest

from framework.core.spawner import Spawner, MemberConfig, MemberRole, MemberStatus
from framework.core.workspace import Workspace


class TestMemberCreationE2E:
    """成员创建端到端测试"""

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

    def test_complete_member_lifecycle(self):
        """测试完整的成员生命周期"""
        spawner = Spawner()
        
        # 1. 创建成员
        config = MemberConfig(
            name="测试工程师",
            code_name="testengineer",
            role=MemberRole.ENGINEER.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding", "testing", "debugging"],
            description="测试用的工程师成员",
            avatar=""
        )
        
        member = spawner.spawn_member(config)
        
        # 验证成员创建成功
        assert member.id == "testengineer"
        assert member.name == "测试工程师"
        assert member.role == MemberRole.ENGINEER.value
        assert member.status == MemberStatus.ACTIVE.value
        
        # 验证工作空间创建成功
        workspace_path = Path(member.workspace)
        assert workspace_path.exists()
        assert (workspace_path / "src").exists()
        assert (workspace_path / "docs").exists()
        assert (workspace_path / "outputs").exists()
        
        # 验证成员元数据文件
        meta_file = workspace_path / "member.json"
        assert meta_file.exists()
        
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
        
        assert meta_data["name"] == "测试工程师"
        assert meta_data["code_name"] == "testengineer"
        assert meta_data["role"] == MemberRole.ENGINEER.value
        assert "created_at" in meta_data
        
        # 2. 验证成员在注册表中
        registry_file = self.base_path / "framework" / "data" / "registry.json"
        assert registry_file.exists()
        
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        assert "testengineer" in registry["members"]
        member_data = registry["members"]["testengineer"]
        assert member_data["name"] == "测试工程师"
        assert member_data["status"] == MemberStatus.ACTIVE.value
        
        # 3. 获取成员信息
        retrieved_member = spawner.get_member("testengineer")
        assert retrieved_member is not None
        assert retrieved_member.id == "testengineer"
        assert retrieved_member.name == "测试工程师"
        
        # 4. 列出成员
        members = spawner.list_members()
        assert len(members) == 1
        assert members[0].id == "testengineer"
        
        # 按状态筛选
        active_members = spawner.list_members(status=MemberStatus.ACTIVE.value)
        assert len(active_members) == 1
        
        suspended_members = spawner.list_members(status=MemberStatus.SUSPENDED.value)
        assert len(suspended_members) == 0
        
        # 5. 更新成员状态
        result = spawner.update_member_status("testengineer", MemberStatus.SUSPENDED.value)
        assert result is True
        
        # 验证状态更新
        updated_member = spawner.get_member("testengineer")
        assert updated_member.status == MemberStatus.SUSPENDED.value
        
        # 6. 删除成员
        result = spawner.delete_member("testengineer")
        assert result is True
        
        # 验证工作空间移动到回收站
        workspace = Workspace(member.workspace)
        assert workspace.root.exists()  # 工作空间仍然存在（在回收站中）
        
        # 验证成员从注册表中移除
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry_after_delete = json.load(f)
        
        assert "testengineer" not in registry_after_delete["members"]
        
        # 7. 验证删除后无法获取成员
        deleted_member = spawner.get_member("testengineer")
        assert deleted_member is None

    def test_multiple_members_creation(self):
        """测试创建多个成员"""
        spawner = Spawner()
        
        members_data = [
            {
                "name": "架构师",
                "code_name": "architect1",
                "role": MemberRole.ARCHITECT.value,
                "model": "claude-3-5-sonnet",
                "capabilities": ["design", "planning"]
            },
            {
                "name": "工程师",
                "code_name": "engineer1",
                "role": MemberRole.ENGINEER.value,
                "model": "claude-3-5-sonnet",
                "capabilities": ["coding", "testing"]
            },
            {
                "name": "审计员",
                "code_name": "auditor1",
                "role": MemberRole.AUDITOR.value,
                "model": "claude-3-5-sonnet",
                "capabilities": ["review", "audit"]
            }
        ]
        
        created_members = []
        for data in members_data:
            config = MemberConfig(
                name=data["name"],
                code_name=data["code_name"],
                role=data["role"],
                model=data["model"],
                workspace="",
                capabilities=data["capabilities"],
                description=f"{data['name']}成员",
                avatar=""
            )
            
            member = spawner.spawn_member(config)
            created_members.append(member)
        
        # 验证所有成员都创建成功
        assert len(created_members) == 3
        
        # 验证注册表中有所有成员
        registry_file = self.base_path / "framework" / "data" / "registry.json"
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        assert len(registry["members"]) == 3
        assert "architect1" in registry["members"]
        assert "engineer1" in registry["members"]
        assert "auditor1" in registry["members"]
        
        # 验证列出所有成员
        all_members = spawner.list_members()
        assert len(all_members) == 3
        
        # 验证按角色筛选
        engineers = spawner.list_members()
        engineers = [m for m in all_members if m.role == MemberRole.ENGINEER.value]
        assert len(engineers) == 1
        assert engineers[0].id == "engineer1"

    def test_member_creation_validation(self):
        """测试成员创建的验证逻辑"""
        spawner = Spawner()
        
        # 测试重复成员名
        config1 = MemberConfig(
            name="测试成员",
            code_name="testmember",
            role=MemberRole.ENGINEER.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding"],
            description="测试成员",
            avatar=""
        )
        
        member1 = spawner.spawn_member(config1)
        assert member1 is not None
        
        # 尝试创建相同ID的成员应该失败
        config2 = MemberConfig(
            name="另一个测试成员",
            code_name="testmember",  # 相同的code_name
            role=MemberRole.ARCHITECT.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["design"],
            description="另一个测试成员",
            avatar=""
        )
        
        with pytest.raises(ValueError, match="成员 'testmember' 已存在"):
            spawner.spawn_member(config2)

    def test_permanent_deletion(self):
        """测试永久删除成员"""
        spawner = Spawner()
        
        # 创建成员
        config = MemberConfig(
            name="测试删除",
            code_name="testdelete",
            role=MemberRole.ENGINEER.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding"],
            description="测试删除功能",
            avatar=""
        )
        
        member = spawner.spawn_member(config)
        workspace_path = Path(member.workspace)
        
        # 验证成员创建成功
        assert workspace_path.exists()
        
        # 删除成员
        result = spawner.delete_member("testdelete")
        assert result is True
        
        # 验证工作空间被永久删除
        assert not workspace_path.exists()
        
        # 验证成员从注册表中移除
        registry_file = self.base_path / "framework" / "data" / "registry.json"
        with open(registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        assert "testdelete" not in registry["members"]

    def test_integration_with_workspace_module(self):
        """测试与 Workspace 模块的集成"""
        spawner = Spawner()
        
        # 创建成员
        config = MemberConfig(
            name="工作空间测试",
            code_name="wstest",
            role=MemberRole.ENGINEER.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding"],
            description="测试工作空间集成",
            avatar=""
        )
        
        member = spawner.spawn_member(config)
        workspace_path = Path(member.workspace)
        
        # 使用 Workspace 模块操作工作空间
        workspace = Workspace(workspace_path)

        # 创建测试文件
        test_file = workspace_path / "src" / "test.txt"
        test_file.write_text("This is a test file for deletion operations.")

        # 测试软删除
        workspace.soft_delete(test_file)
        
        # 测试恢复
        workspace.restore(test_file)

        # 再次软删除，然后永久删除
        workspace.soft_delete(test_file)
        # 永久删除需要删除回收站中的路径
        trash_path = workspace._get_trash_path(test_file)
        workspace.permanent_delete(trash_path)
        
        # 验证 Workspace 模块与 Spawner 集成正常
        assert workspace.root == workspace_path

    def test_registry_persistence(self):
        """测试注册表持久化"""
        spawner1 = Spawner()
        
        # 创建成员
        config = MemberConfig(
            name="持久化测试",
            code_name="persisttest",
            role=MemberRole.ENGINEER.value,
            model="claude-3-5-sonnet",
            workspace="",
            capabilities=["coding"],
            description="测试注册表持久化",
            avatar=""
        )
        
        member = spawner1.spawn_member(config)
        
        # 创建新的 Spawner 实例（模拟重启）
        spawner2 = Spawner()
        
        # 验证新实例能读取到之前创建的成员
        retrieved_member = spawner2.get_member("persisttest")
        assert retrieved_member is not None
        assert retrieved_member.id == "persisttest"
        assert retrieved_member.name == "持久化测试"