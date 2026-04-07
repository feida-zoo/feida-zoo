"""
飝龘动物园 - 权限管理器 (Permissions)
基于角色的访问控制(RBAC)系统

重构说明 (P1-1.5):
- 支持配置化路径配置
- 与 RegistryManager 和 WorkspaceManager 集成
- 保持向后兼容的公共API
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Any, Union
from dataclasses import dataclass, field
import os
from pathlib import Path
from datetime import datetime

from .config_loader import ConfigLoader


class Permission(Enum):
    """系统权限定义"""
    # 共享目录权限
    READ_SHARED = "read_shared"
    WRITE_SHARED = "write_shared"
    DELETE_SHARED = "delete_shared"

    # 成员目录权限
    READ_MEMBER = "read_member"
    WRITE_MEMBER = "write_member"
    DELETE_MEMBER = "delete_member"

    # 代理管理权限
    SPAWN_AGENT = "spawn_agent"
    DELETE_AGENT = "delete_agent"
    MODIFY_AGENT = "modify_agent"

    # 配置管理权限
    READ_CONFIG = "read_config"
    MODIFY_CONFIG = "modify_config"

    # 系统管理权限
    ADMIN = "admin"
    AUDIT = "audit"
    SYSTEM_MANAGE = "system_manage"


class Role(Enum):
    """系统角色定义"""
    ARCHITECT = "architect"      # 架构师 (Alpha)
    ENGINEER = "engineer"        # 工程师 (Weaver)
    AUDITOR = "auditor"          # 审计师 (Duci)
    HISTORIAN = "historian"      # 史官 (Aeterna)
    ARTIST = "artist"            # 画师 (Gulu)
    ADMIN = "admin"              # 管理员 (Panda)
    GUEST = "guest"              # 访客


@dataclass
class RolePermissions:
    """角色权限配置"""
    role: Role
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""
    inherits_from: Optional[Role] = None


class PermissionManager:
    """
    权限管理器

    提供基于角色的访问控制(RBAC)功能：
    - 角色定义与管理
    - 权限分配与检查
    - 权限继承
    - 访问日志记录

    重构说明：
    - 支持通过 ConfigLoader 进行配置化路径管理
    - 可与 RegistryManager 和 WorkspaceManager 协同工作
    - 保持向后兼容性
    """

    # 默认角色权限配置
    DEFAULT_ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
        Role.ARCHITECT: {
            Permission.READ_SHARED, Permission.WRITE_SHARED,
            Permission.READ_MEMBER, Permission.WRITE_MEMBER,
            Permission.READ_CONFIG, Permission.MODIFY_CONFIG,
            Permission.SPAWN_AGENT, Permission.MODIFY_AGENT,
        },
        Role.ENGINEER: {
            Permission.READ_SHARED, Permission.WRITE_SHARED,
            Permission.READ_MEMBER, Permission.WRITE_MEMBER,
            Permission.READ_CONFIG,
            Permission.SPAWN_AGENT,
        },
        Role.AUDITOR: {
            Permission.READ_SHARED, Permission.READ_MEMBER, Permission.READ_CONFIG,
            Permission.AUDIT,
        },
        Role.HISTORIAN: {
            Permission.READ_SHARED, Permission.READ_MEMBER, Permission.READ_CONFIG,
            Permission.WRITE_SHARED,
        },
        Role.ARTIST: {
            Permission.READ_SHARED, Permission.WRITE_SHARED,
            Permission.READ_MEMBER, Permission.WRITE_MEMBER,
            Permission.SPAWN_AGENT,
        },
        Role.ADMIN: {
            Permission.READ_SHARED, Permission.WRITE_SHARED, Permission.DELETE_SHARED,
            Permission.READ_MEMBER, Permission.WRITE_MEMBER, Permission.DELETE_MEMBER,
            Permission.SPAWN_AGENT, Permission.DELETE_AGENT, Permission.MODIFY_AGENT,
            Permission.READ_CONFIG, Permission.MODIFY_CONFIG,
            Permission.ADMIN, Permission.AUDIT, Permission.SYSTEM_MANAGE,
        },
        Role.GUEST: {
            Permission.READ_SHARED,
        },
    }

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        base_path: Optional[Union[str, Path]] = None,
        config_loader: Optional[ConfigLoader] = None
    ):
        """
        初始化权限管理器

        Args:
            config_path: 配置文件路径。如果为 None，使用默认路径
            base_path: 项目根目录路径，用于解析相对路径。如果为 None，从环境变量获取
            config_loader: ConfigLoader 实例，用于配置解析。如果为 None，创建新实例
        """
        # 处理基础路径
        if base_path is None:
            base_path = os.getenv("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")
        self.base_path = Path(base_path).resolve()

        # 处理配置文件路径
        if config_path is None:
            self.config_path = self.base_path / "framework" / "configs" / "permissions.yaml"
        else:
            self.config_path = Path(config_path).resolve()

        # 初始化配置加载器
        self._config_loader = config_loader or ConfigLoader(str(self.base_path))

        # 初始化角色权限
        self._role_permissions: Dict[Role, Set[Permission]] = {}
        self._load_permissions()

        # 访问日志
        self._access_log: List[Dict[str, Any]] = []
        self._max_log_entries = 1000
    
    def _load_permissions(self) -> None:
        """加载权限配置
        使用 ConfigLoader 加载并解析配置文件，支持模板变量
        """
        # 从默认配置加载
        for role, permissions in self.DEFAULT_ROLE_PERMISSIONS.items():
            self._role_permissions[role] = permissions.copy()

        # 如果存在配置文件，从文件加载覆盖
        if self.config_path.exists():
            try:
                # 使用 ConfigLoader 加载并解析配置
                config = self._config_loader.load(str(self.config_path))

                if config and 'roles' in config:
                    for role_name, role_config in config['roles'].items():
                        try:
                            role = Role(role_name.lower())
                            if 'permissions' in role_config:
                                permissions = {
                                    Permission(p) for p in role_config['permissions']
                                }
                                self._role_permissions[role] = permissions
                        except ValueError:
                            continue
            except Exception as e:
                print(f"加载权限配置文件失败: {e}")

    def get_config_loader(self) -> ConfigLoader:
        """
        获取配置加载器实例

        Returns:
            ConfigLoader 实例
        """
        return self._config_loader

    def set_config_loader(self, config_loader: ConfigLoader) -> None:
        """
        设置配置加载器实例

        Args:
            config_loader: 新的 ConfigLoader 实例
        """
        self._config_loader = config_loader

    def check_member_permission(self, role: Role, permission: Permission,
                               member_id: str, registry_manager=None) -> bool:
        """
        检查对特定成员的操作权限

        与 RegistryManager 集成，验证成员存在性后检查权限

        Args:
            role: 请求者角色
            permission: 请求的权限
            member_id: 目标成员ID
            registry_manager: RegistryManager 实例，用于检查成员是否存在

        Returns:
            是否拥有权限。如果成员不存在且提供了 registry_manager，返回 False
        """
        # 如果提供了 RegistryManager，先检查成员是否存在
        if registry_manager is not None:
            if registry_manager.get_member(member_id) is None:
                return False

        # 检查权限
        return self.check_permission(role, permission)

    def check_workspace_permission(self, role: Role, permission: Permission,
                                  member_id: str, workspace_manager=None) -> bool:
        """
        检查对特定工作空间的操作权限

        与 WorkspaceManager 集成，验证工作空间存在性后检查权限

        Args:
            role: 请求者角色
            permission: 请求的权限
            member_id: 成员ID
            workspace_manager: WorkspaceManager 实例，用于检查工作空间是否存在

        Returns:
            是否拥有权限。如果工作空间不存在且提供了 workspace_manager，返回 False
        """
        # 如果提供了 WorkspaceManager，先检查工作空间是否存在
        if workspace_manager is not None:
            if not workspace_manager.workspace_exists(member_id):
                return False

        # 检查权限
        return self.check_permission(role, permission)
    
    def check_permission(self, role: Role, permission: Permission) -> bool:
        """
        检查角色是否拥有指定权限
        
        Args:
            role: 角色
            permission: 权限
            
        Returns:
            是否拥有权限
        """
        if role not in self._role_permissions:
            return False
        
        # ADMIN角色拥有所有权限
        if Permission.ADMIN in self._role_permissions[role]:
            return True
        
        return permission in self._role_permissions[role]
    
    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """
        获取角色的所有权限
        
        Args:
            role: 角色
            
        Returns:
            权限集合
        """
        return self._role_permissions.get(role, set()).copy()
    
    def grant_permission(self, role: Role, permission: Permission) -> bool:
        """
        为角色授予权限
        
        Args:
            role: 角色
            permission: 权限
            
        Returns:
            是否授予成功
        """
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        
        self._role_permissions[role].add(permission)
        self._log_access(role, permission, "grant")
        return True
    
    def revoke_permission(self, role: Role, permission: Permission) -> bool:
        """
        撤销角色的权限
        
        Args:
            role: 角色
            permission: 权限
            
        Returns:
            是否撤销成功
        """
        if role not in self._role_permissions:
            return False
        
        if permission in self._role_permissions[role]:
            self._role_permissions[role].remove(permission)
            self._log_access(role, permission, "revoke")
            return True
        
        return False
    
    def _log_access(self, role: Role, permission: Permission, action: str) -> None:
        """
        记录访问日志
        
        Args:
            role: 角色
            permission: 权限
            action: 操作类型
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role.value,
            "permission": permission.value,
            "action": action,
        }
        
        self._access_log.append(log_entry)
        
        # 限制日志大小
        if len(self._access_log) > self._max_log_entries:
            self._access_log = self._access_log[-self._max_log_entries:]
    
    def get_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取访问日志
        
        Args:
            limit: 返回的最大条目数
            
        Returns:
            日志条目列表
        """
        return self._access_log[-limit:]
    
    def has_permission(self, role: Role, permission: Permission) -> bool:
        """
        check_permission的别名方法
        
        Args:
            role: 角色
            permission: 权限
            
        Returns:
            是否拥有权限
        """
        return self.check_permission(role, permission)


def main():
    """示例用法"""
    # 初始化权限管理器
    pm = PermissionManager()
    
    # 检查架构师权限
    print("架构师权限检查:")
    print(f"  READ_SHARED: {pm.check_permission(Role.ARCHITECT, Permission.READ_SHARED)}")
    print(f"  WRITE_SHARED: {pm.check_permission(Role.ARCHITECT, Permission.WRITE_SHARED)}")
    print(f"  ADMIN: {pm.check_permission(Role.ARCHITECT, Permission.ADMIN)}")
    
    # 检查管理员权限
    print("\n管理员权限检查:")
    print(f"  ADMIN: {pm.check_permission(Role.ADMIN, Permission.ADMIN)}")
    print(f"  所有权限: {len(pm.get_role_permissions(Role.ADMIN))} 项")
    
    # 授予权限示例
    print("\n授予访客 WRITE_SHARED 权限:")
    pm.grant_permission(Role.GUEST, Permission.WRITE_SHARED)
    print(f"  WRITE_SHARED: {pm.check_permission(Role.GUEST, Permission.WRITE_SHARED)}")


if __name__ == "__main__":
    main()
