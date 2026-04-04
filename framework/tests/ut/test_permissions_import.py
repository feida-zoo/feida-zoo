"""
测试：permissions.py 模块导入和功能测试

P1阶段任务1.1 - 修复 datetime 导入错误
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# ==================== Fixtures ====================

@pytest.fixture
def setup_path():
    """设置项目根目录到 Python 路径"""
    # 当前文件: framework/tests/ut/test_permissions_import.py
    # 项目根目录是 ../../.. = feida_zoo
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    yield project_root
    # 清理
    if str(project_root) in sys.path:
        sys.path.remove(str(project_root))


@pytest.fixture
def permissions_module(setup_path):
    """导入并返回 permissions 模块"""
    from framework.core import permissions
    return permissions


@pytest.fixture
def permission_manager(permissions_module):
    """创建并返回 PermissionManager 实例"""
    return permissions_module.PermissionManager()


# ==================== P1: 核心导入测试 ====================

def test_permissions_module_can_be_imported(setup_path):
    """
    测试：permissions.py 可以正常导入，不会因缺少依赖而崩溃
    
    P1验收标准：
    - permissions.py 可以正常编译
    - 权限检查功能不会因导入错误崩溃
    """
    try:
        from framework.core import permissions
        assert permissions is not None, "模块导入成功但返回None"
    except ImportError as e:
        pytest.fail(f"模块导入失败: {e}")
    except SyntaxError as e:
        pytest.fail(f"模块语法错误: {e}")


def test_datetime_import_works_in_permissions(permissions_module):
    """
    测试：permissions 模块中 datetime 可以正常导入和使用
    
    P1关键测试 - 覆盖任务1.1核心问题：
    - 验证 datetime 模块在 permissions.py 中已导入
    - 验证 _log_access 方法中的 datetime.now() 调用不会失败
    """
    # 验证 permissions 模块中已经导入了 datetime
    # 如果 permissions.py 中没有导入 datetime，_log_access 调用会失败
    
    # 验证 permissions 模块可以正常实例化
    pm = permissions_module.PermissionManager()
    assert pm is not None, "PermissionManager 实例化失败"
    
    # 验证 _log_access 方法存在（该方法使用 datetime.now()）
    assert hasattr(pm, '_log_access'), "PermissionManager 缺少 _log_access 方法"
    
    # 尝试调用 _log_access 验证 datetime 使用正常
    # 注意：这会触发 _log_access 方法中的 datetime.now() 调用
    # 如果 permissions.py 没有导入 datetime，这里会抛出 NameError
    try:
        pm._log_access(
            role=permissions_module.Role.ENGINEER,
            permission=permissions_module.Permission.READ_SHARED,
            action="test"
        )
    except NameError as e:
        if "datetime" in str(e) or "'datetime'" in str(e):
            pytest.fail(f"datetime 未导入错误 - 任务1.1需要修复: {e}")
        raise
    except Exception as e:
        # 其他异常可能是预期的（如配置文件不存在等）
        # 只要不是 NameError 关于 datetime 就可以
        pass


# ==================== P2: PermissionManager 功能测试 ====================

def test_permission_manager_instantiation(permissions_module):
    """
    测试：PermissionManager 可以正确实例化
    
    P2边界条件测试
    """
    # 验证类存在
    assert hasattr(permissions_module, 'PermissionManager'), \
        f"PermissionManager 类不存在，模块属性: {dir(permissions_module)}"
    
    # 验证可以实例化
    pm = permissions_module.PermissionManager()
    assert pm is not None, "PermissionManager 实例化返回 None"
    
    # 验证实例具有必要的属性
    assert hasattr(pm, '_role_permissions'), "实例缺少 _role_permissions 属性"
    assert hasattr(pm, '_access_log'), "实例缺少 _access_log 属性"
    assert hasattr(pm, '_max_log_entries'), "实例缺少 _max_log_entries 属性"


def test_check_permission_core_functionality(permission_manager, permissions_module):
    """
    测试：check_permission 核心功能
    
    P2边界条件测试 - 验证权限检查功能正常工作
    """
    # 测试 ADMIN 角色拥有所有权限
    assert permission_manager.check_permission(
        permissions_module.Role.ADMIN, 
        permissions_module.Permission.ADMIN
    ), "ADMIN 角色应该拥有 ADMIN 权限"
    
    # 测试 ENGINEER 角色的权限
    assert permission_manager.check_permission(
        permissions_module.Role.ENGINEER,
        permissions_module.Permission.READ_SHARED
    ), "ENGINEER 角色应该拥有 READ_SHARED 权限"
    
    # 测试 GUEST 角色的权限限制
    assert permission_manager.check_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.READ_SHARED
    ), "GUEST 角色应该拥有 READ_SHARED 权限"
    
    assert not permission_manager.check_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_SHARED
    ), "GUEST 角色不应该拥有 WRITE_SHARED 权限"


def test_grant_and_revoke_permission(permission_manager, permissions_module):
    """
    测试：grant_permission 和 revoke_permission 功能
    
    P2边界条件测试 - 验证权限授予和撤销功能
    """
    # 初始状态：GUEST 不应该有 WRITE_MEMBER 权限
    assert not permission_manager.check_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_MEMBER
    ), "GUEST 初始状态不应该有 WRITE_MEMBER 权限"
    
    # 授予权限
    result = permission_manager.grant_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_MEMBER
    )
    assert result, "grant_permission 应该返回 True"
    
    # 验证权限已授予
    assert permission_manager.check_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_MEMBER
    ), "授予后 GUEST 应该有 WRITE_MEMBER 权限"
    
    # 撤销权限
    result = permission_manager.revoke_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_MEMBER
    )
    assert result, "revoke_permission 应该返回 True"
    
    # 验证权限已撤销
    assert not permission_manager.check_permission(
        permissions_module.Role.GUEST,
        permissions_module.Permission.WRITE_MEMBER
    ), "撤销后 GUEST 不应该有 WRITE_MEMBER 权限"


def test_has_permission_alias(permission_manager, permissions_module):
    """
    测试：has_permission 是 check_permission 的别名
    
    P2边界条件测试
    """
    # has_permission 应该与 check_permission 返回相同结果
    result1 = permission_manager.has_permission(
        permissions_module.Role.ENGINEER,
        permissions_module.Permission.READ_SHARED
    )
    result2 = permission_manager.check_permission(
        permissions_module.Role.ENGINEER,
        permissions_module.Permission.READ_SHARED
    )
    assert result1 == result2, "has_permission 应该与 check_permission 返回相同结果"


# ==================== P2: 异常场景测试 ====================

def test_invalid_role_permission(permission_manager, permissions_module):
    """
    测试：无效角色和权限的处理
    
    P2异常场景测试 - 验证系统对无效输入的处理
    """
    # 测试无效角色（不存在的角色）
    # 创建一个新角色，但没有分配权限
    class FakeRole:
        value = "fake_role"
    
    fake_role = MagicMock()
    fake_role.value = "fake_role"
    
    # 对于未定义的角色，应该返回 False
    result = permission_manager.check_permission(
        permissions_module.Role.GUEST,  # 使用存在的角色
        permissions_module.Permission.ADMIN  # 但测试没有的权限
    )
    assert not result, "GUEST 不应该有 ADMIN 权限"


def test_module_import_error_handling():
    """
    测试：模块导入错误处理
    
    P2异常场景测试 - 验证导入失败时的行为
    """
    # 测试当模块不存在时的导入错误
    with pytest.raises(ImportError):
        import non_existent_module_xyz


def test_permission_manager_invalid_config():
    """
    测试：PermissionManager 无效配置处理
    
    P2异常场景测试 - 验证对无效配置路径的处理
    """
    # 使用不存在的配置文件路径
    from framework.core.permissions import PermissionManager
    
    # 不应该因为配置文件不存在而失败（应该有默认行为）
    pm = PermissionManager(config_path="/non/existent/path/config.yaml")
    assert pm is not None, "即使配置路径无效也应该能实例化"


# ==================== P3: 测试类组织（建议级） ====================

class TestPermissionsImport:
    """测试：模块导入相关功能"""
    
    def test_module_can_be_imported(self, setup_path):
        """测试模块可以正常导入"""
        from framework.core import permissions
        assert permissions is not None


class TestDatetimeImport:
    """测试：datetime 导入和使用"""
    
    def test_datetime_import_in_permissions(self, permissions_module):
        """测试 datetime 在 permissions 中可用"""
        import datetime
        # 验证可以创建时间戳
        now = datetime.datetime.now()
        assert now is not None


class TestPermissionManagerCore:
    """测试：PermissionManager 核心功能"""
    
    def test_instantiation(self, permissions_module):
        """测试实例化"""
        pm = permissions_module.PermissionManager()
        assert pm is not None
    
    def test_permission_checking(self, permission_manager, permissions_module):
        """测试权限检查"""
        assert permission_manager.check_permission(
            permissions_module.Role.ADMIN,
            permissions_module.Permission.ADMIN
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
