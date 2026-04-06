"""
存储适配器实现

提供具体的文件系统操作实现，支持：
- LocalFileSystemAdapter: 基于 os/shutil 的本地文件系统操作
"""

import os
import shutil
from pathlib import Path
from typing import Union

from .interfaces import IStorageAdapter


class LocalFileSystemAdapter(IStorageAdapter):
    """
    本地文件系统适配器
    
    实现 IStorageAdapter 接口，提供基于 os/shutil 的
    本地文件系统操作。
    """
    
    def move(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        将文件或目录从源路径移动到目标路径。
        
        Args:
            src: 源路径
            dst: 目标路径
            
        Raises:
            FileNotFoundError: 如果源文件不存在
        """
        src_path = Path(src)
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        shutil.move(str(src_path), str(dst))
    
    def copy(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        将文件或目录从源路径复制到目标路径。
        
        Args:
            src: 源路径
            dst: 目标路径
            
        Raises:
            FileNotFoundError: 如果源文件不存在
        """
        src_path = Path(src)
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        
        dst_path = Path(dst)
        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(str(dst_path))
            shutil.copytree(str(src_path), str(dst_path))
        else:
            shutil.copy2(str(src_path), str(dst_path))
    
    def delete(self, path: Union[str, Path]) -> None:
        """
        永久删除文件或目录（物理删除）。
        
        Args:
            path: 要删除的文件或目录路径
            
        Raises:
            FileNotFoundError: 如果文件不存在
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if file_path.is_file():
            os.remove(str(file_path))
        elif file_path.is_dir():
            shutil.rmtree(str(file_path))
    
    def exists(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否存在。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径存在返回 True，否则返回 False
        """
        return Path(path).exists()
    
    def is_file(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否为文件。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径是文件返回 True，否则返回 False
        """
        return Path(path).is_file()
    
    def is_dir(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否为目录。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径是目录返回 True，否则返回 False
        """
        return Path(path).is_dir()
    
    def mkdir(self, path: Union[str, Path], parents: bool = True, exist_ok: bool = True) -> None:
        """
        创建目录。
        
        Args:
            path: 要创建的目录路径
            parents: 是否创建父目录
            exist_ok: 如果目录已存在是否不抛出异常
        """
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)
    
    def resolve(self, path: Union[str, Path]) -> Path:
        """
        解析路径为绝对路径（解析符号链接）。
        
        Args:
            path: 要解析的路径
            
        Returns:
            解析后的绝对路径
        """
        return Path(path).resolve()
    
    def relative_to(self, path: Union[str, Path], base: Union[str, Path]) -> Path:
        """
        计算相对路径。
        
        Args:
            path: 目标路径
            base: 基准路径
            
        Returns:
            相对于基准路径的相对路径
        """
        return Path(path).relative_to(base)
    
    def parents(self, path: Union[str, Path]) -> list[Path]:
        """
        获取路径的所有父目录。
        
        Args:
            path: 目标路径
            
        Returns:
            父目录列表（从近到远）
        """
        return list(Path(path).parents)