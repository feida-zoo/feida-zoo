"""
存储适配器接口定义

定义存储操作的抽象接口，实现关注点分离：
- Workspace 负责权限校验、回收站逻辑、事务流转
- IStorageAdapter 负责具体的物理操作（移动、删除、复制等）
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Optional


class IStorageAdapter(ABC):
    """
    存储适配器接口
    
    定义物理文件系统操作的抽象接口，使 Workspace 类
    从具体的 os/shutil 操作中解耦出来。
    """
    
    @abstractmethod
    def move(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        将文件或目录从源路径移动到目标路径。
        
        Args:
            src: 源路径
            dst: 目标路径
            
        Raises:
            FileNotFoundError: 如果源文件不存在
        """
        pass
    
    @abstractmethod
    def copy(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """
        将文件或目录从源路径复制到目标路径。
        
        Args:
            src: 源路径
            dst: 目标路径
            
        Raises:
            FileNotFoundError: 如果源文件不存在
        """
        pass
    
    @abstractmethod
    def delete(self, path: Union[str, Path]) -> None:
        """
        永久删除文件或目录（物理删除）。
        
        Args:
            path: 要删除的文件或目录路径
            
        Raises:
            FileNotFoundError: 如果文件不存在
        """
        pass
    
    @abstractmethod
    def exists(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否存在。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径存在返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def is_file(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否为文件。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径是文件返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def is_dir(self, path: Union[str, Path]) -> bool:
        """
        检查路径是否为目录。
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果路径是目录返回 True，否则返回 False
        """
        pass
    
    @abstractmethod
    def mkdir(self, path: Union[str, Path], parents: bool = True, exist_ok: bool = True) -> None:
        """
        创建目录。
        
        Args:
            path: 要创建的目录路径
            parents: 是否创建父目录
            exist_ok: 如果目录已存在是否不抛出异常
        """
        pass
    
    @abstractmethod
    def resolve(self, path: Union[str, Path]) -> Path:
        """
        解析路径为绝对路径（解析符号链接）。
        
        Args:
            path: 要解析的路径
            
        Returns:
            解析后的绝对路径
        """
        pass
    
    @abstractmethod
    def relative_to(self, path: Union[str, Path], base: Union[str, Path]) -> Path:
        """
        计算相对路径。
        
        Args:
            path: 目标路径
            base: 基准路径
            
        Returns:
            相对于基准路径的相对路径
        """
        pass
    
    @abstractmethod
    def parents(self, path: Union[str, Path]) -> list[Path]:
        """
        获取路径的所有父目录。
        
        Args:
            path: 目标路径
            
        Returns:
            父目录列表（从近到远）
        """
        pass