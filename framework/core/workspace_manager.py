"""
飝龘动物园 - 工作区管理器 (WorkspaceManager)
P1-1.5 重构：将工作区管理职责从 Spawner 分离出来
负责：
- 创建成员工作区目录结构
- 管理成员元数据文件 (member.json)
- 删除成员工作区
- 读取和更新成员元数据
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Union

from .interfaces import IStorageAdapter
from .adapters import LocalFileSystemAdapter


class WorkspaceManager:
    """
    成员工作区管理器
    统一管理成员工作区的创建、删除和元数据操作
    """

    META_FILE_NAME = "member.json"
    DEFAULT_SUBDIRS = ["src", "docs", "outputs"]

    def __init__(
        self,
        agents_base_path: Union[str, Path],
        storage_adapter: Optional[IStorageAdapter] = None
    ):
        """
        初始化工作区管理器

        Args:
            agents_base_path: agents 根目录路径，所有成员工作区都在此目录下
            storage_adapter: 存储适配器，默认为 LocalFileSystemAdapter
        """
        self.agents_base_path = Path(agents_base_path).resolve()
        self._storage = storage_adapter or LocalFileSystemAdapter()
        self._ensure_base_directory()

    def _ensure_base_directory(self) -> None:
        """确保 agents 根目录存在"""
        self._storage.mkdir(self.agents_base_path, parents=True, exist_ok=True)

    def get_workspace_path(self, member_id: str) -> Path:
        """
        获取成员工作区路径

        Args:
            member_id: 成员ID

        Returns:
            成员工作区的完整路径
        """
        return self.agents_base_path / member_id

    def get_meta_file_path(self, member_id: str) -> Path:
        """
        获取成员元数据文件路径

        Args:
            member_id: 成员ID

        Returns:
            member.json 文件的完整路径
        """
        return self.get_workspace_path(member_id) / self.META_FILE_NAME

    def workspace_exists(self, member_id: str) -> bool:
        """
        检查成员工作区是否存在

        Args:
            member_id: 成员ID

        Returns:
            如果工作区存在返回 True，否则返回 False
        """
        workspace_path = self.get_workspace_path(member_id)
        return self._storage.exists(workspace_path)

    def create_workspace(self, member_id: str) -> Path:
        """
        创建成员工作区目录结构

        Args:
            member_id: 成员ID

        Returns:
            创建的工作区路径

        Raises:
            ValueError: 如果工作区已存在
        """
        workspace_path = self.get_workspace_path(member_id)

        if self._storage.exists(workspace_path):
            raise ValueError(f"成员工作区 '{member_id}' 已存在")

        # 创建主工作区目录
        self._storage.mkdir(workspace_path, parents=True, exist_ok=True)

        # 创建标准子目录
        for subdir in self.DEFAULT_SUBDIRS:
            subdir_path = workspace_path / subdir
            self._storage.mkdir(subdir_path, exist_ok=True)

        return workspace_path

    def save_meta(self, member_id: str, meta_data: Dict[str, Any]) -> None:
        """
        保存成员元数据到 member.json 文件

        Args:
            member_id: 成员ID
            meta_data: 元数据字典

        Raises:
            ValueError: 如果工作区不存在
        """
        if not self.workspace_exists(member_id):
            raise ValueError(f"成员工作区 '{member_id}' 不存在")

        meta_file = self.get_meta_file_path(member_id)

        # 添加更新时间戳
        meta_data_copy = meta_data.copy()
        meta_data_copy["updated_at"] = datetime.now().isoformat()

        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta_data_copy, f, indent=2, ensure_ascii=False)

    def load_meta(self, member_id: str) -> Optional[Dict[str, Any]]:
        """
        读取成员元数据

        Args:
            member_id: 成员ID

        Returns:
            元数据字典，如果工作区或元数据文件不存在返回 None
        """
        meta_file = self.get_meta_file_path(member_id)

        if not self._storage.exists(meta_file):
            return None

        with open(meta_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_meta(self, member_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新成员元数据的部分字段

        Args:
            member_id: 成员ID
            updates: 要更新的字段字典

        Returns:
            是否更新成功。如果工作区或元数据不存在返回 False
        """
        current_meta = self.load_meta(member_id)

        if current_meta is None:
            return False

        current_meta.update(updates)
        self.save_meta(member_id, current_meta)
        return True

    def update_meta_field(self, member_id: str, field: str, value: Any) -> bool:
        """
        更新单个元数据字段

        Args:
            member_id: 成员ID
            field: 字段名
            value: 新值

        Returns:
            是否更新成功
        """
        return self.update_meta(member_id, {field: value})

    def delete_workspace(self, member_id: str) -> bool:
        """
        删除成员工作区（物理删除）

        Args:
            member_id: 成员ID

        Returns:
            是否删除成功。如果工作区不存在返回 False
        """
        workspace_path = self.get_workspace_path(member_id)

        if not self._storage.exists(workspace_path):
            return False

        self._storage.delete(workspace_path)
        return True

    def list_workspace_ids(self) -> list[str]:
        """
        列出所有现有的工作区ID

        Returns:
            工作区ID列表
        """
        if not self._storage.exists(self.agents_base_path):
            return []

        workspace_ids = []
        for item in self.agents_base_path.iterdir():
            if self._storage.is_dir(item):
                # 只包含有元数据文件的目录作为有效工作区
                meta_file = item / self.META_FILE_NAME
                if self._storage.exists(meta_file):
                    workspace_ids.append(item.name)

        return workspace_ids

    def get_storage_adapter(self) -> IStorageAdapter:
        """
        获取当前存储适配器

        Returns:
            存储适配器实例
        """
        return self._storage

    def set_storage_adapter(self, adapter: IStorageAdapter) -> None:
        """
        设置存储适配器

        Args:
            adapter: 新的存储适配器实例
        """
        self._storage = adapter
