"""Test permanent delete functionality using Workspace class"""
import os
import tempfile
import pytest
from pathlib import Path

from framework.core.workspace import Workspace


class TestWorkspacePermanentDelete:
    """Test permanent delete functionality of Workspace class"""
    
    def test_permanent_delete_file_from_trash(self):
        """Test permanently deleting a file from .trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and soft delete a file
            test_file = Path(tmpdir) / "delete_me.txt"
            test_file.write_text("to be deleted")
            workspace.soft_delete(test_file)
            
            # Verify file is in .trash
            trash_file = Path(tmpdir) / ".trash" / "delete_me.txt"
            assert trash_file.exists()
            
            # Permanently delete from trash
            workspace.permanent_delete(trash_file)
            
            # Verify file is gone
            assert not trash_file.exists(), "File should be permanently deleted"
    
    def test_permanent_delete_directory_from_trash(self):
        """Test permanently deleting a directory from .trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and soft delete a directory
            test_dir = Path(tmpdir) / "delete_dir"
            test_dir.mkdir()
            (test_dir / "file1.txt").write_text("file1")
            (test_dir / "subdir").mkdir()
            (test_dir / "subdir" / "file2.txt").write_text("file2")
            
            workspace.soft_delete(test_dir)
            
            # Permanently delete from trash
            trash_dir = Path(tmpdir) / ".trash" / "delete_dir"
            workspace.permanent_delete(trash_dir)
            
            # Verify directory is gone
            assert not trash_dir.exists()
    
    def test_permanent_delete_non_trash_file_blocked(self):
        """Test that deleting non-trash files is blocked with ValueError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create a normal file outside trash
            normal_file = Path(tmpdir) / "normal.txt"
            normal_file.write_text("normal file")
            
            # Try to permanently delete - should raise ValueError
            with pytest.raises(ValueError, match="Cannot permanently delete non-trash file"):
                workspace.permanent_delete(normal_file)
            
            # File should still exist
            assert normal_file.exists()
    
    def test_permanent_delete_nonexistent_trash_file(self):
        """Test that deleting non-existent trash file is idempotent"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Ensure .trash exists
            trash_dir = Path(tmpdir) / ".trash"
            trash_dir.mkdir(exist_ok=True)
            
            # Try to delete a file that doesn't exist in trash
            non_existent = trash_dir / "ghost.txt"
            
            # Should not raise any exception (idempotent)
            workspace.permanent_delete(non_existent)
            
            # Verify the file still doesn't exist
            assert not non_existent.exists()
    
    def test_permanent_delete_file_not_in_trash_but_same_name(self):
        """Test that a file with same name but not in .trash cannot be permanently deleted"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create a file that looks like it could be in .trash but isn't
            fake_trash = Path(tmpdir) / "fake.trash"  # Directory named "fake.trash"
            fake_trash.mkdir()
            fake_file = fake_trash / "file.txt"
            fake_file.write_text("fake trash file")
            
            # This file is NOT in the actual .trash directory
            # so permanent_delete should fail
            with pytest.raises(ValueError, match="Cannot permanently delete non-trash file"):
                workspace.permanent_delete(fake_file)
    
    def test_permanent_delete_multiple_files(self):
        """Test permanently deleting multiple files from trash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and delete multiple files
            files = []
            for i in range(3):
                test_file = Path(tmpdir) / f"file{i}.txt"
                test_file.write_text(f"content{i}")
                workspace.soft_delete(test_file)
                files.append(Path(tmpdir) / ".trash" / f"file{i}.txt")
            
            # Permanently delete all files
            for file in files:
                assert file.exists()
                workspace.permanent_delete(file)
                assert not file.exists()
    
    def test_permanent_delete_after_restore(self):
        """Test scenario: delete, restore, delete again, then permanent delete"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            
            # Soft delete
            workspace.soft_delete(test_file)
            trash_file = Path(tmpdir) / ".trash" / "test.txt"
            assert trash_file.exists()
            
            # Restore
            workspace.restore(test_file)
            assert test_file.exists()
            assert not trash_file.exists()
            
            # Soft delete again
            workspace.soft_delete(test_file)
            assert trash_file.exists()
            
            # Permanently delete
            workspace.permanent_delete(trash_file)
            assert not trash_file.exists()
            assert not test_file.exists()
    
    def test_is_in_trash_method(self):
        """Test the internal _is_in_trash method"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create .trash directory
            trash_dir = Path(tmpdir) / ".trash"
            trash_dir.mkdir(exist_ok=True)
            
            # Create files
            in_trash_file = trash_dir / "in_trash.txt"
            in_trash_file.write_text("in trash")
            
            normal_file = Path(tmpdir) / "normal.txt"
            normal_file.write_text("normal")
            
            # Test _is_in_trash method (we'll use reflection to test it)
            # Since it's a private method, we'll test through public API
            # by trying to permanently delete
            
            # File in trash can be permanently deleted
            workspace.permanent_delete(in_trash_file)
            assert not in_trash_file.exists()
            
            # File not in trash cannot be permanently deleted
            with pytest.raises(ValueError):
                workspace.permanent_delete(normal_file)
            assert normal_file.exists()
