"""
飝龘动物园 - 权限管理器 (Permissions)
基于角色的访问控制(RBAC)系统
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
import json
from pathlib import Path
from datetime import datetime


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
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化权限管理器
        
        Args:
            config_path: 配置文件路径，默认为 framework/configs/permissions.yaml
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path("/home/afei/workspace/panda/framework/configs/permissions.yaml")
        
        # 初始化角色权限
        self._role_permissions: Dict[Role, Set[Permission]] = {}
        self._load_permissions()
        
        # 访问日志
        self._access_log: List[Dict[str, Any]] = []
        self._max_log_entries = 1000
    
    def _load_permissions(self) -> None:
        """加载权限配置"""
        # 从默认配置加载
        for role, permissions in self.DEFAULT_ROLE_PERMISSIONS.items():
            self._role_permissions[role] = permissions.copy()
        
        # 如果存在配置文件，从文件加载覆盖
        if self.config_path.exists():
            try:
                import yaml
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
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
