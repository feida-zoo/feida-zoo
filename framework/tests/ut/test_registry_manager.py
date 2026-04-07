"""
单元测试：RegistryManager - 成员注册表管理器
测试覆盖：
- 注册表加载和保存
- 成员注册
- 成员查询
- 成员更新
- 成员删除
- 状态更新
- 成员列表过滤
"""

import json
import tempfile
from pathlib import Path
import pytest

from framework.core.registry_manager import RegistryManager


class TestRegistryManager:
    """RegistryManager 单元测试"""

    def setup_method(self):
        """测试准备：创建临时文件"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry_path = Path(self.temp_dir.name) / "registry.json"

    def teardown_method(self):
        """测试清理：删除临时文件"""
        self.temp_dir.cleanup()

    def test_load_new_registry_creates_default_structure(self):
        """测试加载不存在的注册表时创建默认结构"""
        manager = RegistryManager(self.registry_path)
        registry = manager.load()

        assert "members" in registry
        assert registry["members"] == {}
        assert "version" in registry
        assert "last_updated" in registry
        assert registry["last_updated"] is None
        assert manager.member_count == 0

    def test_save_persists_data_with_timestamp(self):
        """测试保存时正确写入文件并更新时间戳"""
        manager = RegistryManager(self.registry_path)
        manager.load()
        manager.register_member({
            "id": "test_member",
            "name": "Test Member",
            "status": "active"
        })
        manager.save()

        # 验证文件存在
        assert self.registry_path.exists()

        # 重新加载验证数据
        with open(self.registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert "last_updated" in data
        assert data["last_updated"] is not None
        assert "test_member" in data["members"]
        assert data["members"]["test_member"]["name"] == "Test Member"

    def test_register_member_success(self):
        """测试成功注册成员"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        member_data = {
            "id": "test1",
            "name": "Test One",
            "role": "engineer",
            "status": "active"
        }

        member_id = manager.register_member(member_data)

        assert member_id == "test1"
        assert manager.member_count == 1

        saved = manager.get_member("test1")
        assert saved is not None
        assert saved["name"] == "Test One"
        assert saved["role"] == "engineer"

    def test_register_member_duplicate_id_raises_error(self):
        """测试重复注册相同ID会抛出错误"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        manager.register_member({"id": "test1", "name": "First"})

        with pytest.raises(ValueError, match="成员 'test1' 已存在"):
            manager.register_member({"id": "test1", "name": "Second"})

    def test_register_member_missing_id_raises_error(self):
        """测试缺少id会抛出错误"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        with pytest.raises(ValueError, match="成员数据必须包含 'id' 字段"):
            manager.register_member({"name": "No ID here"})

    def test_get_member_returns_none_for_nonexistent(self):
        """测试获取不存在的成员返回 None"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        result = manager.get_member("nonexistent")
        assert result is None

    def test_list_members_returns_all_members(self):
        """测试列出所有成员"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        manager.register_member({"id": "member1", "name": "Member 1", "status": "active"})
        manager.register_member({"id": "member2", "name": "Member 2", "status": "active"})
        manager.register_member({"id": "member3", "name": "Member 3", "status": "suspended"})

        all_members = manager.list_members()
        assert len(all_members) == 3

    def test_list_members_filters_by_status(self):
        """测试按状态过滤成员列表"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        manager.register_member({"id": "member1", "name": "Member 1", "status": "active"})
        manager.register_member({"id": "member2", "name": "Member 2", "status": "active"})
        manager.register_member({"id": "member3", "name": "Member 3", "status": "suspended"})

        active_members = manager.list_members(status="active")
        assert len(active_members) == 2

        suspended_members = manager.list_members(status="suspended")
        assert len(suspended_members) == 1
        assert suspended_members[0]["id"] == "member3"

    def test_list_members_empty_when_no_matches(self):
        """测试没有匹配时返回空列表"""
        manager = RegistryManager(self.registry_path)
        manager.load()
        manager.register_member({"id": "member1", "status": "active"})

        result = manager.list_members(status="deleted")
        assert len(result) == 0

    def test_update_member_success(self):
        """测试成功更新成员信息"""
        manager = RegistryManager(self.registry_path)
        manager.load()
        manager.register_member({
            "id": "test1",
            "name": "Original Name",
            "role": "engineer",
            "status": "active"
        })

        success = manager.update_member("test1", {
            "name": "Updated Name",
            "role": "architect"
        })

        assert success is True
        updated = manager.get_member("test1")
        assert updated["name"] == "Updated Name"
        assert updated["role"] == "architect"
        # 原有字段保留
        assert updated["status"] == "active"

    def test_update_member_fails_for_nonexistent(self):
        """测试更新不存在的成员返回 False"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        success = manager.update_member("nonexistent", {"name": "test"})
        assert success is False

    def test_delete_member_success(self):
        """测试成功删除成员"""
        manager = RegistryManager(self.registry_path)
        manager.load()
        manager.register_member({"id": "test1", "name": "Test"})

        assert manager.member_count == 1
        success = manager.delete_member("test1")

        assert success is True
        assert manager.member_count == 0
        assert manager.get_member("test1") is None

    def test_delete_member_fails_for_nonexistent(self):
        """测试删除不存在的成员返回 False"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        success = manager.delete_member("nonexistent")
        assert success is False

    def test_update_member_status_success(self):
        """测试成功更新成员状态"""
        manager = RegistryManager(self.registry_path)
        manager.load()
        manager.register_member({
            "id": "test1",
            "name": "Test",
            "status": "active"
        })

        success = manager.update_member_status("test1", "suspended")

        assert success is True
        member = manager.get_member("test1")
        assert member["status"] == "suspended"

    def test_update_member_status_fails_for_nonexistent(self):
        """测试更新不存在成员状态返回 False"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        success = manager.update_member_status("nonexistent", "active")
        assert success is False

    def test_get_version_returns_correct_version(self):
        """测试获取版本号"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        assert manager.get_version() == "1.0.0"

    def test_member_count_returns_correct_count(self):
        """测试member_count属性返回正确数量"""
        manager = RegistryManager(self.registry_path)
        manager.load()

        assert manager.member_count == 0

        manager.register_member({"id": "test1"})
        assert manager.member_count == 1

        manager.register_member({"id": "test2"})
        assert manager.member_count == 2

        manager.delete_member("test1")
        assert manager.member_count == 1

    def test_load_existing_file_preserves_data(self):
        """测试加载已有的文件保留数据"""
        # 创建一个预填充的注册表文件
        test_data = {
            "members": {
                "pre_existing": {
                    "id": "pre_existing",
                    "name": "Pre Existing",
                    "status": "active"
                }
            },
            "version": "1.0.0",
            "last_updated": "2024-01-01T00:00:00"
        }
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        manager = RegistryManager(self.registry_path)
        registry = manager.load()

        assert "pre_existing" in registry["members"]
        assert manager.member_count == 1
        assert manager.get_member("pre_existing")["name"] == "Pre Existing"
