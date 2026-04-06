"""System test for complete workspace lifecycle"""
import os
import tempfile
import pytest
from pathlib import Path

from framework.core.workspace import Workspace


class TestWorkspaceLifecycle:
    """System test for complete file lifecycle in workspace"""
    
    def test_complete_lifecycle_file(self):
        """Test complete lifecycle: create → soft delete → restore → soft delete → permanent delete"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Phase 1: Create file
            test_file = Path(tmpdir) / "lifecycle.txt"
            original_content = "This file will go through the complete lifecycle"
            test_file.write_text(original_content)
            assert test_file.exists()
            assert test_file.read_text() == original_content
            
            # Phase 2: Soft delete
            workspace.soft_delete(test_file)
            trash_file = Path(tmpdir) / ".trash" / "lifecycle.txt"
            assert not test_file.exists(), "Original file should be gone"
            assert trash_file.exists(), "File should be in .trash"
            assert trash_file.read_text() == original_content, "Content should be preserved in trash"
            
            # Phase 3: Restore
            workspace.restore(test_file)
            assert test_file.exists(), "File should be restored"
            assert not trash_file.exists(), "Trash should be empty"
            assert test_file.read_text() == original_content, "Content should be preserved after restore"
            
            # Phase 4: Soft delete again
            workspace.soft_delete(test_file)
            assert not test_file.exists(), "Original file should be gone again"
            assert trash_file.exists(), "File should be back in .trash"
            
            # Phase 5: Permanent delete
            workspace.permanent_delete(trash_file)
            assert not trash_file.exists(), "File should be permanently deleted from trash"
            assert not test_file.exists(), "File should not exist anywhere"
    
    def test_lifecycle_with_directory(self):
        """Test complete lifecycle with a directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create directory structure
            test_dir = Path(tmpdir) / "project"
            test_dir.mkdir()
            (test_dir / "README.md").write_text("# Project")
            (test_dir / "src" / "main.py").parent.mkdir()
            (test_dir / "src" / "main.py").write_text("print('hello')")
            (test_dir / "data" / "config.json").parent.mkdir()
            (test_dir / "data" / "config.json").write_text('{"key": "value"}')
            
            # Soft delete directory
            workspace.soft_delete(test_dir)
            trash_dir = Path(tmpdir) / ".trash" / "project"
            assert not test_dir.exists()
            assert trash_dir.exists()
            assert (trash_dir / "README.md").read_text() == "# Project"
            
            # Restore directory
            workspace.restore(test_dir)
            assert test_dir.exists()
            assert not trash_dir.exists()
            assert (test_dir / "src" / "main.py").read_text() == "print('hello')"
            
            # Soft delete and permanent delete
            workspace.soft_delete(test_dir)
            workspace.permanent_delete(Path(tmpdir) / ".trash" / "project")
            assert not test_dir.exists()
            assert not trash_dir.exists()
    
    def test_multiple_files_lifecycle(self):
        """Test lifecycle with multiple independent files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            files = []
            for i in range(3):
                file = Path(tmpdir) / f"doc{i}.txt"
                file.write_text(f"Document {i}")
                files.append(file)
            
            # Soft delete all files
            for file in files:
                workspace.soft_delete(file)
            
            # Verify all in trash
            for i, file in enumerate(files):
                trash_file = Path(tmpdir) / ".trash" / f"doc{i}.txt"
                assert trash_file.exists()
                assert trash_file.read_text() == f"Document {i}"
            
            # Restore first file
            workspace.restore(files[0])
            assert files[0].exists()
            assert not (Path(tmpdir) / ".trash" / "doc0.txt").exists()
            
            # Permanently delete second file
            trash_file2 = Path(tmpdir) / ".trash" / "doc1.txt"
            workspace.permanent_delete(trash_file2)
            assert not trash_file2.exists()
            assert not files[1].exists()
            
            # Third file should still be in trash
            trash_file3 = Path(tmpdir) / ".trash" / "doc2.txt"
            assert trash_file3.exists()
            
            # Restore third file
            workspace.restore(files[2])
            assert files[2].exists()
            assert not trash_file3.exists()
    
    def test_lifecycle_with_concurrent_operations(self):
        """Test that operations don't interfere with each other"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create multiple files
            file_a = Path(tmpdir) / "file_a.txt"
            file_b = Path(tmpdir) / "file_b.txt"
            file_c = Path(tmpdir) / "file_c.txt"
            
            file_a.write_text("A")
            file_b.write_text("B")
            file_c.write_text("C")
            
            # Soft delete A and B, keep C
            workspace.soft_delete(file_a)
            workspace.soft_delete(file_b)
            
            # Verify state
            assert not file_a.exists()
            assert not file_b.exists()
            assert file_c.exists()
            assert (Path(tmpdir) / ".trash" / "file_a.txt").exists()
            assert (Path(tmpdir) / ".trash" / "file_b.txt").exists()
            
            # Restore A
            workspace.restore(file_a)
            assert file_a.exists()
            assert not file_b.exists()
            assert file_c.exists()
            
            # Permanent delete B from trash
            trash_b = Path(tmpdir) / ".trash" / "file_b.txt"
            workspace.permanent_delete(trash_b)
            
            # Soft delete C
            workspace.soft_delete(file_c)
            
            # Final state
            assert file_a.exists()
            assert not file_b.exists()
            assert not file_c.exists()
            assert not (Path(tmpdir) / ".trash" / "file_a.txt").exists()
            assert not (Path(tmpdir) / ".trash" / "file_b.txt").exists()
            assert (Path(tmpdir) / ".trash" / "file_c.txt").exists()
    
    def test_error_handling_in_lifecycle(self):
        """Test error handling during lifecycle operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Try to restore non-existent file (should raise)
            non_existent = Path(tmpdir) / "ghost.txt"
            with pytest.raises(FileNotFoundError):
                workspace.restore(non_existent)
            
            # Create a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            
            # Try to permanently delete non-trash file (should raise)
            with pytest.raises(ValueError):
                workspace.permanent_delete(test_file)
            
            # File should still exist
            assert test_file.exists()
            
            # Now do valid lifecycle
            workspace.soft_delete(test_file)
            trash_file = Path(tmpdir) / ".trash" / "test.txt"
            
            # Try to restore with wrong path (should raise)
            wrong_path = Path(tmpdir) / "wrong.txt"
            with pytest.raises(FileNotFoundError):
                workspace.restore(wrong_path)
            
            # Correct restore
            workspace.restore(test_file)
            assert test_file.exists()
