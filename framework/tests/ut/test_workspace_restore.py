"""Test restore functionality using Workspace class"""
import os
import tempfile
import pytest
from pathlib import Path

from framework.core.workspace import Workspace


class TestWorkspaceRestore:
    """Test restore functionality of Workspace class"""
    
    def test_restore_file_from_trash(self):
        """Test restoring a file from .trash to original location"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and soft delete a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("restore test")
            workspace.soft_delete(test_file)
            
            # Verify file is in .trash
            trash_file = Path(tmpdir) / ".trash" / "test.txt"
            assert trash_file.exists()
            
            # Restore the file
            workspace.restore(test_file)
            
            # Verify file restored to original location
            assert test_file.exists(), "File should be restored"
            assert test_file.read_text() == "restore test", "Content should be preserved"
            assert not trash_file.exists(), "Trash should be empty"
    
    def test_restore_directory_from_trash(self):
        """Test restoring a directory from .trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and soft delete a directory
            test_dir = Path(tmpdir) / "test_dir"
            test_dir.mkdir()
            (test_dir / "file1.txt").write_text("file1")
            (test_dir / "file2.txt").write_text("file2")
            
            workspace.soft_delete(test_dir)
            
            # Restore the directory
            workspace.restore(test_dir)
            
            # Verify directory restored
            assert test_dir.exists()
            assert test_dir.is_dir()
            assert (test_dir / "file1.txt").read_text() == "file1"
            assert (test_dir / "file2.txt").read_text() == "file2"
    
    def test_restore_preserves_content(self):
        """Test that restored file content is preserved"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            content = "important data with special chars: éàüñ 123 !@#$%"
            
            # Create, delete, and restore
            test_file = Path(tmpdir) / "data.txt"
            test_file.write_text(content)
            workspace.soft_delete(test_file)
            workspace.restore(test_file)
            
            # Verify content
            assert test_file.read_text() == content, "Content should be exactly preserved"
    
    def test_restore_nonexistent_file(self):
        """Test restoring non-existent file from trash raises FileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            non_existent = Path(tmpdir) / "ghost.txt"
            
            with pytest.raises(FileNotFoundError, match=f"File not found in trash: {non_existent}"):
                workspace.restore(non_existent)
    
    def test_restore_overwrites_existing(self):
        """Test restoring overwrites when target already exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create initial file and delete it
            test_file = Path(tmpdir) / "conflict.txt"
            test_file.write_text("trash version")
            workspace.soft_delete(test_file)
            
            # Create another file with same name
            test_file.write_text("new version")
            
            # Restore from trash - should overwrite
            workspace.restore(test_file)
            
            # Verify file now contains trash version content
            assert test_file.read_text() == "trash version", "Restore should overwrite existing file"
    
    def test_restore_with_missing_parent_directory(self):
        """Test restoring when parent directory doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create nested file and delete it
            nested_file = Path(tmpdir) / "a" / "b" / "file.txt"
            nested_file.parent.mkdir(parents=True)
            nested_file.write_text("nested")
            workspace.soft_delete(nested_file)
            
            # Delete parent directory
            import shutil
            shutil.rmtree(Path(tmpdir) / "a")
            
            # Restore should recreate parent directories
            workspace.restore(nested_file)
            
            # Verify file restored with parent directories
            assert nested_file.exists()
            assert nested_file.read_text() == "nested"
    
    def test_restore_file_not_in_trash_but_exists(self):
        """Test restoring a file that exists but is not in trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create a file (not in trash)
            test_file = Path(tmpdir) / "normal.txt"
            test_file.write_text("normal")
            
            # Try to restore - should raise error because not in trash
            with pytest.raises(FileNotFoundError, match=f"File not found in trash: {test_file}"):
                workspace.restore(test_file)
            
            # File should still exist
            assert test_file.exists()
            assert test_file.read_text() == "normal"
