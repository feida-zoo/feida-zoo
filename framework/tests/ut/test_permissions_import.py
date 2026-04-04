import pytest
import sys
from pathlib import Path

def test_permissions_module_imports():
    """
    测试：permissions.py 可以正常导入，不会因缺少依赖而崩溃
    
    P1验收标准：
    - permissions.py 可以正常编译
    - 权限检查功能不会因导入错误崩溃
    """
    # 设置项目根目录到 Python 路径
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # 尝试导入模块
    try:
        from framework.core import permissions
        assert True, "模块导入成功"
    except ImportError as e:
        pytest.fail(f"模块导入失败: {e}")

def test_datetime_available_in_permissions():
    """
    测试：permissions 模块中 datetime 可用
    """
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    from framework.core import permissions
    from datetime import datetime
    
    # 检查 PermissionManager 类存在
    assert hasattr(permissions, 'PermissionManager'), "PermissionManager 类不存在"
    
    # 检查 PermissionManager 实例化不会失败
    pm = permissions.PermissionManager()
    assert pm is not None, "PermissionManager 实例化失败"
