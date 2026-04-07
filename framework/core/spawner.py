"""
飝龘动物园 - 角色孵化器 (Spawner)
负责成员的创建、初始化和管理

重构说明 (P1-1.5):
- 将注册表管理职责委托给 RegistryManager
- 将工作区管理职责委托给 WorkspaceManager
- 保持向后兼容的公共API
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .registry_manager import RegistryManager
from .workspace_manager import WorkspaceManager


class MemberRole(Enum):
    """成员角色类型"""
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    AUDITOR = "auditor"
    HISTORIAN = "historian"
    ARTIST = "artist"
    ADMIN = "admin"


class MemberStatus(Enum):
    """成员状态"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


@dataclass
class MemberConfig:
    """成员配置"""
    name: str
    code_name: str
    role: str
    model: str
    workspace: str
    capabilities: List[str]
    description: str = ""
    avatar: str = ""


@dataclass
class Member:
    """成员实体"""
    id: str
    name: str
    code_name: str
    role: str
    model: str
    workspace: str
    status: str
    created_at: str
    updated_at: str
    capabilities: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class Spawner:
    """
    角色孵化器

    负责动物园成员的完整生命周期管理：
    - 创建新成员
    - 初始化成员工作区
    - 管理成员状态
    - 协调 RegistryManager 和 WorkspaceManager
    """

    def __init__(self, base_path: str = None):
        """
        初始化孵化器

        Args:
            base_path: 项目根目录路径
        """
        if base_path is None:
            base_path = os.getenv("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")
        self.base_path = Path(base_path)
        self.agents_path = self.base_path / "agents"
        self.framework_path = self.base_path / "framework"
        self.data_path = self.framework_path / "data"
        self.registry_file = self.data_path / "registry.json"

        # 初始化管理器
        self.registry_manager = RegistryManager(self.registry_file)
        self.workspace_manager = WorkspaceManager(self.agents_path)

        # 加载注册表
        self.registry_manager.load()
    
    def spawn_member(self, config: MemberConfig) -> Member:
        """
        创建新成员

        Args:
            config: 成员配置

        Returns:
            创建成功的成员对象

        Raises:
            ValueError: 当成员已存在或配置无效时
        """
        member_id = config.code_name.lower()

        # 检查成员是否已存在
        if self.registry_manager.get_member(member_id) is not None:
            raise ValueError(f"成员 '{member_id}' 已存在")

        # 创建工作区
        workspace_path = self.workspace_manager.create_workspace(member_id)

        # 创建成员元数据
        member_meta = {
            "name": config.name,
            "code_name": config.code_name,
            "role": config.role,
            "model": config.model,
            "description": config.description,
            "avatar": config.avatar,
            "capabilities": config.capabilities,
            "created_at": datetime.now().isoformat(),
        }

        self.workspace_manager.save_meta(member_id, member_meta)

        # 创建成员对象
        now = datetime.now().isoformat()
        member = Member(
            id=member_id,
            name=config.name,
            code_name=config.code_name,
            role=config.role,
            model=config.model,
            workspace=str(workspace_path),
            status=MemberStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
            capabilities=config.capabilities,
            metadata=member_meta
        )

        # 注册到注册表
        registry_data = {
            "id": member.id,
            "name": member.name,
            "code_name": member.code_name,
            "role": member.role,
            "model": member.model,
            "workspace": member.workspace,
            "status": member.status,
            "created_at": member.created_at,
            "capabilities": member.capabilities,
        }

        self.registry_manager.register_member(registry_data)
        self.registry_manager.save()

        return member

    def list_members(self, status: Optional[str] = None) -> List[Member]:
        """
        列出所有成员

        Args:
            status: 可选的状态过滤

        Returns:
            成员列表
        """
        members = []
        registry_members = self.registry_manager.list_members(status)

        for member_data in registry_members:
            # 从工作区加载完整成员信息
            member_id = member_data["id"]
            metadata = self.workspace_manager.load_meta(member_id)
            metadata = metadata or {}

            member = Member(
                id=member_id,
                name=member_data["name"],
                code_name=member_data["code_name"],
                role=member_data["role"],
                model=member_data["model"],
                workspace=member_data["workspace"],
                status=member_data["status"],
                created_at=member_data["created_at"],
                updated_at=metadata.get("updated_at", member_data["created_at"]),
                capabilities=member_data.get("capabilities", []),
                metadata=metadata
            )
            members.append(member)

        return members

    def get_member(self, member_id: str) -> Optional[Member]:
        """
        获取指定成员

        Args:
            member_id: 成员ID

        Returns:
            成员对象，如果不存在则返回None
        """
        member_data = self.registry_manager.get_member(member_id)
        if member_data is None:
            return None

        metadata = self.workspace_manager.load_meta(member_id)
        metadata = metadata or {}

        return Member(
            id=member_id,
            name=member_data["name"],
            code_name=member_data["code_name"],
            role=member_data["role"],
            model=member_data["model"],
            workspace=member_data["workspace"],
            status=member_data["status"],
            created_at=member_data["created_at"],
            updated_at=metadata.get("updated_at", member_data["created_at"]),
            capabilities=member_data.get("capabilities", []),
            metadata=metadata
        )

    def update_member_status(self, member_id: str, status: str) -> bool:
        """
        更新成员状态

        Args:
            member_id: 成员ID
            status: 新状态

        Returns:
            是否更新成功
        """
        # 更新注册表
        success = self.registry_manager.update_member_status(member_id, status)

        if not success:
            return False

        # 保存变更
        self.registry_manager.save()

        # 更新成员元数据文件
        self.workspace_manager.update_meta_field(member_id, "status", status)

        return True

    def delete_member(self, member_id: str) -> bool:
        """
        删除成员

        Args:
            member_id: 成员ID

        Returns:
            是否删除成功
        """
        # 从注册表中删除
        success = self.registry_manager.delete_member(member_id)

        if not success:
            return False

        # 保存注册表变更
        self.registry_manager.save()

        # 删除工作区
        self.workspace_manager.delete_workspace(member_id)

        return True


def main():
    """示例用法"""
    spawner = Spawner()
    
    # 创建示例成员
    config = MemberConfig(
        name="测试成员",
        code_name="test_member",
        role="engineer",
        model="gpt-4",
        workspace="",
        capabilities=["coding", "debugging"],
        description="这是一个测试成员"
    )
    
    try:
        member = spawner.spawn_member(config)
        print(f"成员创建成功: {member.name} ({member.id})")
        
        # 列出所有成员
        members = spawner.list_members()
        print(f"\n当前成员总数: {len(members)}")
        for m in members:
            print(f"  - {m.name} ({m.role}): {m.status}")
            
    except ValueError as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()
