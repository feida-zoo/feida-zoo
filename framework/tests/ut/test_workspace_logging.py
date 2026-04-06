"""Test logging functionality of Workspace class"""
import os
import tempfile
import pytest
import json
from pathlib import Path
from datetime import datetime

from framework.core.workspace import Workspace


class TestWorkspaceLogging:
    """Test logging functionality of Workspace class"""
    
    def test_log_file_created(self):
        """Test that log file is created when Workspace is initialized"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            log_file = Path(tmpdir) / ".deletion_log.json"
            
            assert log_file.exists(), "Log file should be created on initialization"
            
            # Log file should contain empty list
            with open(log_file, 'r') as f:
                content = json.load(f)
            assert content == [], "Log file should contain empty list initially"
    
    def test_soft_delete_logged(self):
        """Test that soft delete operations are logged"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create and soft delete a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace.soft_delete(test_file)
            
            # Check log
            log = workspace.get_deletion_log()
            assert len(log) == 1, "Should have one log entry"
            
            entry = log[0]
            assert entry['operation'] == 'soft_delete'
            assert entry['path'] == str(test_file)
            assert entry['success'] == True
            assert 'Moved to trash' in entry['details']
            
            # Check timestamp is valid ISO format
            try:
                datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            except ValueError:
                pytest.fail("Timestamp is not valid ISO format")
    
    def test_restore_logged(self):
        """Test that restore operations are logged"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create, delete, and restore
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace.soft_delete(test_file)
            workspace.restore(test_file)
            
            # Check log
            log = workspace.get_deletion_log()
            assert len(log) == 2, "Should have two log entries"
            
            # Second entry should be restore
            entry = log[1]
            assert entry['operation'] == 'restore'
            assert entry['path'] == str(test_file)
            assert entry['success'] == True
            assert 'Restored from trash' in entry['details']
    
    def test_permanent_delete_logged(self):
        """Test that permanent delete operations are logged"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create, delete, and permanently delete
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace.soft_delete(test_file)
            
            trash_file = Path(tmpdir) / ".trash" / "test.txt"
            workspace.permanent_delete(trash_file)
            
            # Check log
            log = workspace.get_deletion_log()
            assert len(log) == 2, "Should have two log entries"
            
            # Second entry should be permanent delete
            entry = log[1]
            assert entry['operation'] == 'permanent_delete'
            assert entry['path'] == str(trash_file)
            assert entry['success'] == True
            assert 'Permanently deleted' in entry['details']
    
    def test_failed_operations_logged(self):
        """Test that failed operations are logged with success=False"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Try to restore non-existent file
            non_existent = Path(tmpdir) / "ghost.txt"
            with pytest.raises(FileNotFoundError):
                workspace.restore(non_existent)
            
            # Check log
            log = workspace.get_deletion_log()
            assert len(log) == 1, "Should have one log entry"
            
            entry = log[0]
            assert entry['operation'] == 'restore'
            assert entry['path'] == str(non_existent)
            assert entry['success'] == False
            assert 'File not found in trash' in entry['details']
    
    def test_get_deletion_log_with_limit(self):
        """Test getting deletion log with limit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create multiple operations
            for i in range(5):
                test_file = Path(tmpdir) / f"file{i}.txt"
                test_file.write_text(f"content{i}")
                workspace.soft_delete(test_file)
            
            # Get all logs
            all_logs = workspace.get_deletion_log()
            assert len(all_logs) == 5
            
            # Get limited logs
            recent_logs = workspace.get_deletion_log(limit=3)
            assert len(recent_logs) == 3
            
            # Recent logs should be the last 3 entries
            assert recent_logs == all_logs[-3:]
    
    def test_clear_deletion_log(self):
        """Test clearing deletion log"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Workspace(tmpdir)
            
            # Create some operations
            for i in range(3):
                test_file = Path(tmpdir) / f"file{i}.txt"
                test_file.write_text(f"content{i}")
                workspace.soft_delete(test_file)
            
            # Verify logs exist
            assert len(workspace.get_deletion_log()) == 3
            
            # Clear logs
            workspace.clear_deletion_log()
            
            # Verify logs are cleared
            assert len(workspace.get_deletion_log()) == 0
            
            # Log file should contain empty list
            log_file = Path(tmpdir) / ".deletion_log.json"
            with open(log_file, 'r') as f:
                content = json.load(f)
            assert content == []
    
    def test_log_persistence(self):
        """Test that logs persist across Workspace instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first workspace and log operations
            workspace1 = Workspace(tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace1.soft_delete(test_file)
            
            # Create second workspace with same directory
            workspace2 = Workspace(tmpdir)
            
            # Logs should be accessible from second instance
            log = workspace2.get_deletion_log()
            assert len(log) == 1
            assert log[0]['operation'] == 'soft_delete'
    
    def test_log_file_corruption_handling(self):
        """Test that corrupted log file is handled gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / ".deletion_log.json"
            
            # Create corrupted log file
            with open(log_file, 'w') as f:
                f.write("not valid json")
            
            # Workspace should initialize without error
            workspace = Workspace(tmpdir)
            
            # Should have empty log
            assert len(workspace.get_deletion_log()) == 0
            
            # Should be able to log new operations
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            workspace.soft_delete(test_file)
            
            assert len(workspace.get_deletion_log()) == 1
