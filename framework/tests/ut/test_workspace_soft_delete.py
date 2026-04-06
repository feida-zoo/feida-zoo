"""Test soft delete functionality using Workspace class"""
import os
import tempfile
import pytest
from pathlib import Path

from framework.core.workspace import Workspace


class TestWorkspaceSoftDelete:
    """Test soft delete functionality of Workspace class"""
    
    def test_soft_delete_file(self):
        """Test soft deleting a file moves it to .trash directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # Soft delete the file
            workspace.soft_delete(test_file)
            
            # Verify file moved to .trash
            trash_file = Path(tmpdir) / ".trash" / "test.txt"
            assert trash_file.exists(), "File should be in .trash"
            assert trash_file.read_text() == "test content", "Content should be preserved"
            assert not test_file.exists(), "Original location should be empty"
    
    def test_soft_delete_directory(self):
        """Test soft deleting a directory moves it to .trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create test directory with files
            test_dir = Path(tmpdir) / "test_dir"
            test_dir.mkdir()
            (test_dir / "file1.txt").write_text("file1")
            (test_dir / "file2.txt").write_text("file2")
            
            # Soft delete the directory
            workspace.soft_delete(test_dir)
            
            # Verify directory moved to .trash
            trash_dir = Path(tmpdir) / ".trash" / "test_dir"
            assert trash_dir.exists(), "Directory should be in .trash"
            assert trash_dir.is_dir(), "Should be a directory"
            assert (trash_dir / "file1.txt").read_text() == "file1"
            assert (trash_dir / "file2.txt").read_text() == "file2"
            assert not test_dir.exists(), "Original location should be empty"
    
    def test_soft_delete_nonexistent_file(self):
        """Test soft deleting non-existent file raises FileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            non_existent = Path(tmpdir) / "does_not_exist.txt"
            
            with pytest.raises(FileNotFoundError, match=f"File not found: {non_existent}"):
                workspace.soft_delete(non_existent)
    
    def test_soft_delete_already_in_trash(self):
        """Test soft deleting a file already in trash does nothing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create file directly in .trash
            trash_dir = Path(tmpdir) / ".trash"
            trash_dir.mkdir(exist_ok=True)
            trash_file = trash_dir / "already_in_trash.txt"
            trash_file.write_text("already deleted")
            
            # Try to soft delete it (should do nothing)
            workspace.soft_delete(trash_file)
            
            # Verify file still exists in .trash with same content
            assert trash_file.exists(), "File should still be in .trash"
            assert trash_file.read_text() == "already deleted"
    
    def test_trash_directory_auto_created(self):
        """Test .trash directory is automatically created on first soft delete"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            trash_dir = Path(tmpdir) / ".trash"
            
            # .trash should not exist initially
            assert not trash_dir.exists()
            
            # Create a file and soft delete it
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace.soft_delete(test_file)
            
            # .trash should now exist
            assert trash_dir.exists()
            assert trash_dir.is_dir()
    
    def test_soft_delete_with_nested_paths(self):
        """Test soft deleting file with nested directory structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create nested directory structure
            nested_dir = Path(tmpdir) / "a" / "b" / "c"
            nested_dir.mkdir(parents=True)
            nested_file = nested_dir / "file.txt"
            nested_file.write_text("nested content")
            
            # Soft delete the file
            workspace.soft_delete(nested_file)
            
            # Verify file moved to .trash with same structure
            trash_file = Path(tmpdir) / ".trash" / "a" / "b" / "c" / "file.txt"
            assert trash_file.exists(), "File with nested path should be in .trash"
            assert trash_file.read_text() == "nested content"
            assert not nested_file.exists(), "Original location should be empty"
