"""
飝龘动物园框架核心模块

包含以下核心组件：
- spawner: 角色孵化器，负责成员创建和管理
- registry_manager: 成员注册表管理器，负责注册表CRUD操作
- workspace_manager: 工作区管理器，负责工作区创建和管理
- permissions: 权限管理器，提供RBAC功能
- config_loader: 配置模板引擎，支持变量解析
- workspace: 工作空间管理器，提供安全删除功能
- interfaces: 存储适配器接口定义
- adapters: 存储适配器实现
"""

__version__ = "1.0.0"
__author__ = "飝龘动物园"

from .spawner import Spawner, Member, MemberConfig, MemberRole, MemberStatus
from .registry_manager import RegistryManager
from .workspace_manager import WorkspaceManager
from .permissions import (
    PermissionManager,
    Permission,
    Role,
    RolePermissions
)
from .config_loader import (
    ConfigLoader,
    ConfigTemplateError,
    ConfigTemplateSyntaxError
)
from .workspace import Workspace
from .interfaces import IStorageAdapter
from .adapters import LocalFileSystemAdapter

__all__ = [
    # Spawner
    "Spawner",
    "Member",
    "MemberConfig",
    "MemberRole",
    "MemberStatus",
    # RegistryManager
    "RegistryManager",
    # WorkspaceManager
    "WorkspaceManager",
    # Permissions
    "PermissionManager",
    "Permission",
    "Role",
    "RolePermissions",
    # ConfigLoader
    "ConfigLoader",
    "ConfigTemplateError",
    "ConfigTemplateSyntaxError",
    # Workspace
    "Workspace",
    # Storage Adapter
    "IStorageAdapter",
    "LocalFileSystemAdapter",
]