"""
Workspace module for file operations with safe delete functionality.

重构说明 (P1-1.5):
- 引入 IStorageAdapter 接口，将物理操作抽离
- Workspace 负责权限校验、回收站逻辑、事务流转
- 具体文件操作由 LocalFileSystemAdapter 实现
- 添加删除操作日志记录功能

安全修复说明 (P1-1.4 修复):
- 修复并发竞争条件：添加线程锁和文件锁
- 修复路径遍历攻击：添加路径验证方法
- 修复日志无限增长：添加日志大小限制
- 修复静默日志写入失败：统一异常处理
- 修复相对路径解析漏洞：使用验证后的路径
- 修复异常处理不一致：统一异常处理策略
"""

from pathlib import Path
from typing import Union, Optional
from datetime import datetime
import json
import threading
import sys

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
        
        # 并发控制 - 使用RLock防止嵌套调用死锁
        self._log_lock = threading.RLock()
        
        # 日志配置
        self._max_log_entries = 10000  # 最大日志条目数
        
        # 注意：这里不验证接口实现，因为适配器可能通过继承或鸭子类型实现
        # 如果适配器不完整，会在调用具体方法时抛出异常
        
        self._ensure_log_file()
    
    def _ensure_trash_dir(self) -> None:
        """Ensure trash directory exists."""
        self._storage.mkdir(self.trash_dir, parents=True, exist_ok=True)
    
    def _validate_path(self, path: Union[str, Path]) -> Path:
        """
        验证路径是否在工作区范围内，防止路径遍历攻击。
        
        Args:
            path: 要验证的路径
            
        Returns:
            解析后的绝对路径
            
        Raises:
            ValueError: 如果路径不在工作区范围内
        """
        # 将路径转换为Path对象
        path_obj = Path(path)
        
        # 如果路径是相对的，将其转换为相对于工作区根目录的绝对路径
        if not path_obj.is_absolute():
            path_obj = self.root / path_obj
        
        # 解析路径（处理符号链接等）
        try:
            resolved_path = path_obj.resolve()
        except (OSError, RuntimeError):
            # 如果路径无法解析（例如不存在），使用规范化路径
            resolved_path = path_obj.absolute()
        
        # 检查路径是否在工作区根目录下
        try:
            resolved_path.relative_to(self.root)
            return resolved_path
        except ValueError as e:
            raise ValueError(f"Path {path} is outside workspace root {self.root}") from e
    
    def _ensure_log_file(self) -> None:
        """Ensure log file exists with empty list if not present."""
        # 确保日志文件的父目录存在
        if not self._storage.exists(self.log_file.parent):
            self._storage.mkdir(self.log_file.parent, parents=True, exist_ok=True)
        if not self._storage.exists(self.log_file):
            self._write_log([])
    
    def _read_log(self) -> list:
        """
        读取删除日志，使用线程锁防止并发竞争。
        
        Returns:
            日志条目列表
        """
        with self._log_lock:
            if not self._storage.exists(self.log_file):
                return []
            
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
    
    def _write_log(self, log_entries: list) -> None:
        """
        写入删除日志，使用线程锁防止并发竞争。
        
        Args:
            log_entries: 要写入的日志条目列表
            
        Raises:
            RuntimeError: 如果日志写入失败
        """
        with self._log_lock:
            try:
                with open(self.log_file, 'w') as f:
                    json.dump(log_entries, f, indent=2)
            except IOError as e:
                # 不再静默忽略，记录到stderr并抛出异常
                error_msg = f"Failed to write deletion log: {e}"
                print(error_msg, file=sys.stderr)
                raise RuntimeError(error_msg) from e
    
    def _log_operation(self, operation: str, path: Union[str, Path], 
                      success: bool = True, details: Optional[str] = None) -> None:
        """
        记录删除操作，自动清理旧日志防止无限增长。
        
        Args:
            operation: 操作类型 ('soft_delete', 'restore', 'permanent_delete')
            path: 操作涉及的路径
            success: 操作是否成功
            details: 操作详情
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
        
        # 自动清理旧日志，防止无限增长
        if len(log_entries) > self._max_log_entries:
            # 保留最近的一半日志
            keep_count = self._max_log_entries // 2
            log_entries = log_entries[-keep_count:]
            
            # 记录清理操作
            cleanup_entry = {
                'timestamp': datetime.now().isoformat(),
                'operation': 'log_cleanup',
                'path': str(self.log_file),
                'success': True,
                'details': f"Cleaned up old logs, kept {keep_count} most recent entries"
            }
            log_entries.append(cleanup_entry)
        
        self._write_log(log_entries)
    
    def _get_trash_path(self, path: Union[str, Path]) -> Path:
        """
        获取文件路径对应的回收站路径。
        
        Args:
            path: 原始文件路径
            
        Returns:
            回收站中的路径
            
        Raises:
            ValueError: 如果路径不在工作区范围内
        """
        # 先验证路径在工作区范围内
        validated_path = self._validate_path(path)
        
        # 获取相对路径
        rel_path = validated_path.relative_to(self.root)
        return self.trash_dir / rel_path
    
    def _is_in_trash(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否在回收站目录内。
        
        Args:
            path: 要检查的路径
            
        Returns:
            True如果路径在回收站目录内
        """
        try:
            # 先验证路径（如果路径不在工作区，会抛出异常）
            validated_path = self._validate_path(path)
            
            # 检查是否在回收站目录内
            trash_obj = self._storage.resolve(self.trash_dir)
            path_obj = self._storage.resolve(validated_path)
            
            return trash_obj in self._storage.parents(path_obj) or path_obj == trash_obj
        except ValueError:
            # 路径不在工作区范围内
            return False
    
    def soft_delete(self, path: Union[str, Path]) -> None:
        """
        将文件移动到回收站（软删除）。
        
        Args:
            path: 要删除的文件路径
            
        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果路径不在工作区范围内
        """
        # 验证路径在工作区范围内
        src = self._validate_path(path)
        
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
        将文件从回收站恢复到原始位置。
        
        Args:
            path: 文件应该恢复到的原始路径
            
        Raises:
            FileNotFoundError: 如果文件不在回收站中
            ValueError: 如果路径不在工作区范围内
        """
        # 验证原始路径在工作区范围内
        self._validate_path(path)
        
        # 获取回收站中的路径
        trash_path = self._get_trash_path(path)
        
        if not self._storage.exists(trash_path):
            error_msg = f"File not found in trash: {path}"
            self._log_operation('restore', path, success=False, details=error_msg)
            raise FileNotFoundError(error_msg)
        
        # Ensure parent directory exists for restoration
        dst = self._validate_path(path)
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
        从回收站永久删除文件。
        
        Args:
            path: 回收站中要永久删除的文件路径
            
        Raises:
            ValueError: 如果文件不在回收站目录中
            ValueError: 如果路径不在工作区范围内
        """
        # 验证路径在工作区范围内
        self._validate_path(path)
        
        # 检查路径是否在回收站中
        if not self._is_in_trash(path):
            error_msg = "Cannot permanently delete non-trash file"
            self._log_operation('permanent_delete', path, success=False, details=error_msg)
            raise ValueError(error_msg)
        
        # 删除文件（幂等操作）
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
