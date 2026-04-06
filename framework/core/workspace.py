"""
Workspace module for file operations with safe delete functionality.

重构说明 (P1-1.5):
- 引入 IStorageAdapter 接口，将物理操作抽离
- Workspace 负责权限校验、回收站逻辑、事务流转
- 具体文件操作由 LocalFileSystemAdapter 实现
- 添加删除操作日志记录功能
"""

from pathlib import Path
from typing import Union, Optional
from datetime import datetime
import json

from .interfaces import IStorageAdapter
from .adapters import LocalFileSystemAdapter


class Workspace:
    """Workspace manager with safe delete operations."""
    
    TRASH_DIR_NAME = ".trash"
    LOG_FILE_NAME = ".deletion_log.json"
    
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
        self.log_file = self.root / self.LOG_FILE_NAME
        self._storage = storage_adapter or LocalFileSystemAdapter()
        self._ensure_log_file()
    
    def _ensure_trash_dir(self) -> None:
        """Ensure trash directory exists."""
        self._storage.mkdir(self.trash_dir, parents=True, exist_ok=True)
    
    def _ensure_log_file(self) -> None:
        """Ensure log file exists with empty list if not present."""
        if not self._storage.exists(self.log_file):
            self._write_log([])
    
    def _read_log(self) -> list:
        """Read the deletion log."""
        if not self._storage.exists(self.log_file):
            return []
        
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def _write_log(self, log_entries: list) -> None:
        """Write to the deletion log."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(log_entries, f, indent=2)
        except IOError:
            # Silently fail if can't write log
            pass
    
    def _log_operation(self, operation: str, path: Union[str, Path], 
                      success: bool = True, details: Optional[str] = None) -> None:
        """
        Log a deletion operation.
        
        Args:
            operation: Type of operation ('soft_delete', 'restore', 'permanent_delete')
            path: Path involved in the operation
            success: Whether the operation was successful
            details: Additional details about the operation
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'path': str(path),
            'success': success,
            'details': details
        }
        
        log_entries = self._read_log()
        log_entries.append(log_entry)
        self._write_log(log_entries)
    
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
            error_msg = f"File not found: {path}"
            self._log_operation('soft_delete', path, success=False, details=error_msg)
            raise FileNotFoundError(error_msg)
        
        # Check if file is already in trash
        if self._is_in_trash(src):
            # File is already in trash, do nothing but log
            self._log_operation('soft_delete', path, success=True, 
                              details="File already in trash, no operation performed")
            return
        
        # Ensure trash directory exists
        self._ensure_trash_dir()
        
        # Get destination in trash
        dst = self._get_trash_path(src)
        
        # Ensure parent directory exists in trash
        self._storage.mkdir(dst.parent, parents=True, exist_ok=True)
        
        # Move file to trash (delegate to adapter)
        try:
            self._storage.move(src, dst)
            self._log_operation('soft_delete', path, success=True, 
                              details=f"Moved to trash: {dst}")
        except Exception as e:
            error_msg = f"Failed to move to trash: {e}"
            self._log_operation('soft_delete', path, success=False, details=error_msg)
            raise
    
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
            error_msg = f"File not found in trash: {path}"
            self._log_operation('restore', path, success=False, details=error_msg)
            raise FileNotFoundError(error_msg)
        
        # Ensure parent directory exists for restoration
        dst = Path(path)
        self._storage.mkdir(dst.parent, parents=True, exist_ok=True)
        
        # Move file from trash to original location (overwrite if exists)
        try:
            self._storage.move(trash_path, dst)
            self._log_operation('restore', path, success=True, 
                              details=f"Restored from trash: {trash_path}")
        except Exception as e:
            error_msg = f"Failed to restore: {e}"
            self._log_operation('restore', path, success=False, details=error_msg)
            raise
    
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
            error_msg = "Cannot permanently delete non-trash file"
            self._log_operation('permanent_delete', path, success=False, details=error_msg)
            raise ValueError(error_msg)
        
        # Delete file if it exists (idempotent)
        file_path = Path(path)
        if self._storage.exists(file_path):
            try:
                self._storage.delete(file_path)
                self._log_operation('permanent_delete', path, success=True, 
                                  details="Permanently deleted from trash")
            except Exception as e:
                error_msg = f"Failed to permanently delete: {e}"
                self._log_operation('permanent_delete', path, success=False, details=error_msg)
                raise
    
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
    
    def get_deletion_log(self, limit: Optional[int] = None) -> list:
        """
        获取删除操作日志。
        
        Args:
            limit: 最多返回的日志条目数（最新优先）
            
        Returns:
            删除操作日志列表
        """
        log_entries = self._read_log()
        if limit is not None and limit > 0:
            log_entries = log_entries[-limit:]  # 获取最新的条目
        
        return log_entries
    
    def clear_deletion_log(self) -> None:
        """清空删除操作日志。"""
        self._write_log([])
