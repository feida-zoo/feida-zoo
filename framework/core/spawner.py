"""
飝龘动物园 - 角色孵化器 (Spawner)
负责成员的创建、初始化和管理
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


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
    metadata: Dict[str, Any]


class Spawner:
    """
    角色孵化器
    
    负责动物园成员的完整生命周期管理：
    - 创建新成员
    - 初始化成员工作区
    - 管理成员状态
    - 记录成员信息到注册表
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
        
        # 确保目录结构存在
        self._ensure_directories()
        
        # 加载注册表
        self._registry = self._load_registry()
    
    def _ensure_directories(self) -> None:
        """确保必要的目录结构存在"""
        self.agents_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    def _load_registry(self) -> Dict[str, Any]:
        """加载成员注册表"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"members": {}, "version": "1.0.0", "last_updated": None}
    
    def _save_registry(self) -> None:
        """保存成员注册表"""
        self._registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self._registry, f, indent=2, ensure_ascii=False)
    
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
        if member_id in self._registry["members"]:
            raise ValueError(f"成员 '{member_id}' 已存在")
        
        # 创建工作区
        workspace_path = self.agents_path / member_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 创建成员目录结构
        (workspace_path / "src").mkdir(exist_ok=True)
        (workspace_path / "docs").mkdir(exist_ok=True)
        (workspace_path / "outputs").mkdir(exist_ok=True)
        
        # 创建成员元数据文件
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
        
        with open(workspace_path / "member.json", 'w', encoding='utf-8') as f:
            json.dump(member_meta, f, indent=2, ensure_ascii=False)
        
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
        
        # 更新注册表
        self._registry["members"][member_id] = {
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
        
        self._save_registry()
        
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
        for member_data in self._registry["members"].values():
            if status and member_data.get("status") != status:
                continue
            
            # 从工作区加载完整成员信息
            member_id = member_data["id"]
            workspace_path = Path(member_data["workspace"])
            meta_file = workspace_path / "member.json"
            
            metadata = {}
            if meta_file.exists():
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            
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
        if member_id not in self._registry["members"]:
            return None
        
        members = self.list_members()
        for member in members:
            if member.id == member_id:
                return member
        return None
    
    def update_member_status(self, member_id: str, status: str) -> bool:
        """
        更新成员状态
        
        Args:
            member_id: 成员ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        if member_id not in self._registry["members"]:
            return False
        
        self._registry["members"][member_id]["status"] = status
        self._save_registry()
        
        # 更新成员元数据文件
        member_data = self._registry["members"][member_id]
        workspace_path = Path(member_data["workspace"])
        meta_file = workspace_path / "member.json"
        
        if meta_file.exists():
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            metadata["status"] = status
            metadata["updated_at"] = datetime.now().isoformat()
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return True
    
    def delete_member(self, member_id: str) -> bool:
        """
        删除成员
        
        Args:
            member_id: 成员ID
            
        Returns:
            是否删除成功
        """
        if member_id not in self._registry["members"]:
            return False
        
        # 获取工作区路径
        workspace_path = Path(self._registry["members"][member_id]["workspace"])
        
        # 从注册表中移除
        del self._registry["members"][member_id]
        self._save_registry()
        
        # 删除工作区（谨慎操作，这里只删除标记）
        # 实际删除操作可以注释掉，改为标记删除
        if workspace_path.exists():
            import shutil
            shutil.rmtree(workspace_path)
        
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
