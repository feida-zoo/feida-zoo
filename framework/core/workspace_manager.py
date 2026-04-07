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
import re
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
        安全验证：防止绝对路径逃逸和路径遍历攻击
        使用多层验证：输入验证 + 规范化 + 物理路径对比，抵御Unicode/URL/HTML编码攻击

        Args:
            member_id: 成员ID

        Returns:
            成员工作区的完整路径

        Raises:
            ValueError: 如果成员ID包含不安全字符或路径逃逸
        """
        # 第一层：安全验证输入成员ID
        self._validate_member_id(member_id)

        # 构建原始路径
        raw_path = self.agents_base_path / member_id

        # 第二层：使用os.path规范化处理，解析任何. .. ~等符号
        # 同时使用abspath确保获取绝对路径
        normalized_str = os.path.normpath(os.path.abspath(raw_path))
        workspace_path = Path(normalized_str).resolve()

        # 第三层：严格物理路径前缀匹配，防止任何编码绕过
        # 转换为绝对路径字符串进行比较
        base_abs = os.path.abspath(self.agents_base_path)
        workspace_abs = os.path.abspath(workspace_path)

        # 确保工作区路径确实以基础路径为前缀
        if not workspace_abs.startswith(base_abs + os.sep) and workspace_abs != base_abs:
            raise ValueError(
                f"成员ID '{member_id}' 导致路径逃逸攻击。"
                f"结果路径：{workspace_abs} 不在基础目录 {base_abs} 内。"
            )

        # 保留原有的relative_to检查作为备用
        try:
            workspace_path.relative_to(self.agents_base_path)
        except ValueError:
            raise ValueError(
                f"成员ID '{member_id}' 导致路径逃逸攻击。"
                f"结果路径：{workspace_path} 不在基础目录 {self.agents_base_path} 内。"
            )

        return workspace_path
    
    def _validate_member_id(self, member_id: str) -> None:
        """
        验证成员ID的安全性
        
        Args:
            member_id: 要验证的成员ID
            
        Raises:
            ValueError: 如果成员ID不安全
        """
        if not member_id:
            raise ValueError("成员ID不能为空")
        
        # 检查绝对路径
        if os.path.isabs(member_id):
            raise ValueError(f"成员ID不能是绝对路径: '{member_id}'")
        
        # 检查路径遍历模式
        if ".." in member_id:
            raise ValueError(f"成员ID不能包含路径遍历字符 '..': '{member_id}'")
        
        # 检查其他危险模式
        dangerous_patterns = [
            r'^/.*',           # 以斜杠开头
            r'.*/$',           # 以斜杠结尾
            r'.*//.*',         # 双斜杠
            r'.*\\\\.*',     # 双反斜杠（Windows）
            r'.*/\..*',       # 隐藏的路径遍历
            r'.*\\.\..*',    # Windows隐藏路径遍历
        ]
        
        for pattern in dangerous_patterns:
            if re.match(pattern, member_id):
                raise ValueError(f"成员ID包含危险模式: '{member_id}'")
        
        # 检查特殊字符（除了字母、数字、下划线、连字符、点）
        if not re.match(r'^[a-zA-Z0-9_.\-]+$', member_id):
            raise ValueError(
                f"成员ID只能包含字母、数字、下划线、连字符和点: '{member_id}'"
            )
        
        # 检查长度限制
        if len(member_id) > 255:
            raise ValueError(f"成员ID过长（最大255字符）: '{member_id}'")
        
        # 检查保留名称
        reserved_names = [".", "..", "", "CON", "PRN", "AUX", "NUL", 
                         "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                         "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"]
        if member_id.upper() in [name.upper() for name in reserved_names]:
            raise ValueError(f"成员ID是保留名称: '{member_id}'")
        
        # 检查以点开头（隐藏文件）
        if member_id.startswith('.'):
            raise ValueError(f"成员ID不能以点开头（隐藏文件）: '{member_id}'")

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
            ValueError: 如果工作区已存在或成员ID不安全
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
