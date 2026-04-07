"""
飝龘动物园 - 成员注册表管理器 (RegistryManager)
P1-1.5 重构：将注册表管理职责从 Spawner 分离出来
负责：
- 加载和保存 registry.json
- 成员注册、查询、更新、删除
- 成员状态管理
- 注册表版本控制
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


class RegistryManager:
    """
    成员注册表管理器
    统一管理成员注册表的加载、保存和成员信息的CRUD操作
    """

    DEFAULT_VERSION = "1.0.0"

    def __init__(self, registry_file: Union[str, Path]):
        """
        初始化注册表管理器

        Args:
            registry_file: registry.json 文件路径
        """
        self.registry_file = Path(registry_file).resolve()
        self._registry: Dict[str, Any] = {}
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """确保注册表文件所在目录存在"""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """
        加载注册表文件

        Returns:
            完整注册表字典
        """
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                self._registry = json.load(f)
        else:
            self._registry = {
                "members": {},
                "version": self.DEFAULT_VERSION,
                "last_updated": None
            }
        return self._registry

    def save(self) -> None:
        """
        保存注册表到文件
        更新 last_updated 时间戳
        """
        self._registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self._registry, f, indent=2, ensure_ascii=False)

    def register_member(self, member_data: Dict[str, Any]) -> str:
        """
        注册新成员到注册表

        Args:
            member_data: 成员数据字典，必须包含 "id" 字段

        Returns:
            注册成功的成员ID

        Raises:
            ValueError: 如果成员ID已存在
        """
        if "id" not in member_data:
            raise ValueError("成员数据必须包含 'id' 字段")

        member_id = member_data["id"]
        if member_id in self._registry.get("members", {}):
            raise ValueError(f"成员 '{member_id}' 已存在")

        # 确保 members 字典存在
        if "members" not in self._registry:
            self._registry["members"] = {}

        # 存储成员数据
        self._registry["members"][member_id] = member_data.copy()
        return member_id

    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定成员信息

        Args:
            member_id: 成员ID

        Returns:
            成员数据字典，如果不存在返回 None
        """
        members = self._registry.get("members", {})
        return members.get(member_id)

    def list_members(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有成员，可以按状态过滤

        Args:
            status: 可选的状态过滤条件

        Returns:
            成员数据列表
        """
        members = self._registry.get("members", {})
        result = []

        for member_data in members.values():
            if status is not None:
                member_status = member_data.get("status")
                if member_status != status:
                    continue
            result.append(member_data.copy())

        return result

    def update_member(self, member_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新成员信息

        Args:
            member_id: 成员ID
            updates: 更新字段字典

        Returns:
            是否更新成功。如果成员不存在返回 False
        """
        if member_id not in self._registry.get("members", {}):
            return False

        # 更新字段
        member = self._registry["members"][member_id]
        member.update(updates)
        return True

    def delete_member(self, member_id: str) -> bool:
        """
        删除成员记录

        Args:
            member_id: 成员ID

        Returns:
            是否删除成功。如果成员不存在返回 False
        """
        members = self._registry.get("members", {})
        if member_id not in members:
            return False

        del members[member_id]
        return True

    def update_member_status(self, member_id: str, status: str) -> bool:
        """
        更新成员状态

        Args:
            member_id: 成员ID
            status: 新状态值

        Returns:
            是否更新成功。如果成员不存在返回 False
        """
        return self.update_member(member_id, {"status": status})

    def get_version(self) -> str:
        """
        获取注册表版本

        Returns:
            版本字符串
        """
        return self._registry.get("version", self.DEFAULT_VERSION)

    def get_last_updated(self) -> Optional[str]:
        """
        获取最后更新时间戳

        Returns:
            ISO格式时间戳，如果未更新过返回 None
        """
        return self._registry.get("last_updated")

    @property
    def member_count(self) -> int:
        """
        获取当前成员总数

        Returns:
            成员数量
        """
        return len(self._registry.get("members", {}))
