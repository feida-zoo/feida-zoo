"""
Workspace module for file operations with safe delete functionality.
"""

import os
import shutil
from pathlib import Path
from typing import Union


class Workspace:
    """Workspace manager with safe delete operations."""
    
    TRASH_DIR_NAME = ".trash"
    
    def __init__(self, root_path: Union[str, Path]):
        """
        Initialize workspace with root path.
        
        Args:
            root_path: Root directory of the workspace
        """
        self.root = Path(root_path).resolve()
        self.trash_dir = self.root / self.TRASH_DIR_NAME
        
    def _ensure_trash_dir(self) -> None:
        """Ensure trash directory exists."""
        self.trash_dir.mkdir(exist_ok=True)
    
    def _get_trash_path(self, path: Union[str, Path]) -> Path:
        """
        Get the trash path for a given file path.
        
        Args:
            path: Original file path
            
        Returns:
            Path in trash directory
        """
        rel_path = Path(path).relative_to(self.root)
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
            path_obj = Path(path).resolve()
            trash_obj = self.trash_dir.resolve()
            return trash_obj in path_obj.parents or path_obj == trash_obj
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
        if not src.exists():
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
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file to trash
        shutil.move(str(src), str(dst))
    
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
        
        if not trash_path.exists():
            raise FileNotFoundError(f"File not found in trash: {path}")
        
        # Ensure parent directory exists for restoration
        dst = Path(path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Move file from trash to original location (overwrite if exists)
        shutil.move(str(trash_path), str(dst))
    
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
        if file_path.exists():
            if file_path.is_file():
                os.remove(str(file_path))
            elif file_path.is_dir():
                shutil.rmtree(str(file_path))