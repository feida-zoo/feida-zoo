"""
Workspace module for file operations with safe delete functionality.

重构说明 (P1-1.5):
- 引入 IStorageAdapter 接口，将物理操作抽离
- Workspace 负责权限校验、回收站逻辑、事务流转
- 具体文件操作由 LocalFileSystemAdapter 实现
"""

from pathlib import Path
from typing import Union, Optional

from .interfaces import IStorageAdapter
from .adapters import LocalFileSystemAdapter


class Workspace:
    """Workspace manager with safe delete operations."""
    
    TRASH_DIR_NAME = ".trash"
    
    def __init__(
        self, 
        root_path: Union[str, Path],
        storage_adapter: Optional[IStorageAdapter] = None
    ):
        """
        Initialize workspace with root path.
        
        Args:
            root_path: Root directory of the workspace
            storage_adapter: Storage adapter for file operations.
                           Defaults to LocalFileSystemAdapter if None.
        """
        self.root = Path(root_path).resolve()
        self.trash_dir = self.root / self.TRASH_DIR_NAME
        self._storage = storage_adapter or LocalFileSystemAdapter()
    
    def _ensure_trash_dir(self) -> None:
        """Ensure trash directory exists."""
        self._storage.mkdir(self.trash_dir, parents=True, exist_ok=True)
    
    def _get_trash_path(self, path: Union[str, Path]) -> Path:
        """
        Get the trash path for a given file path.
        
        Args:
            path: Original file path
            
        Returns:
            Path in trash directory
        """
        rel_path = self._storage.relative_to(path, self.root)
        return self.trash_dir / rel_path
    
    def _is_in_trash(self, path: Union[str, Path]) -> bool:
        """
        Check if a path is within the trash directory.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is in trash directory
        """
        try:
            path_obj = self._storage.resolve(path)
            trash_obj = self._storage.resolve(self.trash_dir)
            return trash_obj in self._storage.parents(path_obj) or path_obj == trash_obj
        except ValueError:
            return False
    
    def soft_delete(self, path: Union[str, Path]) -> None:
        """
        Move a file to trash (soft delete).
        
        Args:
            path: Path to file to delete
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        src = Path(path)
        if not self._storage.exists(src):
            raise FileNotFoundError(f"File not found: {path}")
        
        # Check if file is already in trash
        if self._is_in_trash(src):
            # File is already in trash, do nothing
            return
        
        # Ensure trash directory exists
        self._ensure_trash_dir()
        
        # Get destination in trash
        dst = self._get_trash_path(src)
        
        # Ensure parent directory exists in trash
        self._storage.mkdir(dst.parent, parents=True, exist_ok=True)
        
        # Move file to trash (delegate to adapter)
        self._storage.move(src, dst)
    
    def restore(self, path: Union[str, Path]) -> None:
        """
        Restore a file from trash to its original location.
        
        Args:
            path: Original path where file should be restored
            
        Raises:
            FileNotFoundError: If file does not exist in trash
        """
        # Get the path in trash
        trash_path = self._get_trash_path(path)
        
        if not self._storage.exists(trash_path):
            raise FileNotFoundError(f"File not found in trash: {path}")
        
        # Ensure parent directory exists for restoration
        dst = Path(path)
        self._storage.mkdir(dst.parent, parents=True, exist_ok=True)
        
        # Move file from trash to original location (overwrite if exists)
        # Delegate to adapter
        self._storage.move(trash_path, dst)
    
    def permanent_delete(self, path: Union[str, Path]) -> None:
        """
        Permanently delete a file from trash.
        
        Args:
            path: Path to file in trash to delete permanently
            
        Raises:
            ValueError: If file is not in trash directory
        """
        # Check if path is in trash
        if not self._is_in_trash(path):
            raise ValueError("Cannot permanently delete non-trash file")
        
        # Delete file if it exists (idempotent)
        file_path = Path(path)
        if self._storage.exists(file_path):
            # Delegate to adapter
            self._storage.delete(file_path)
    
    # ==================== 扩展方法（供未来使用）====================
    
    def get_storage_adapter(self) -> IStorageAdapter:
        """
        获取当前使用的存储适配器。
        
        Returns:
            存储适配器实例
        """
        return self._storage
    
    def set_storage_adapter(self, adapter: IStorageAdapter) -> None:
        """
        设置存储适配器（用于测试或替换实现）。
        
        Args:
            adapter: 新的存储适配器实例
        """
        self._storage = adapter