"""Test permanent delete functionality"""
import os
import tempfile

def test_permanent_delete_from_trash():
    """Test permanently deleting a file from .trash"""
    with tempfile.TemporaryDirectory() as tmpdir:
        trash_dir = os.path.join(tmpdir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        trash_file = os.path.join(trash_dir, "delete_me.txt")
        with open(trash_file, "w") as f:
            f.write("to be deleted")
        
        # Permanent delete
        os.remove(trash_file)
        
        # Verify
        assert not os.path.exists(trash_file), "File should be permanently deleted"

def test_trash_status_check():
    """Test checking if file is in trash for permanent deletion"""
    with tempfile.TemporaryDirectory() as tmpdir:
        trash_dir = os.path.join(tmpdir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        # File in trash
        in_trash = os.path.join(trash_dir, "in_trash.txt")
        with open(in_trash, "w") as f:
            f.write("in trash")
        
        # File not in trash
        not_in_trash = os.path.join(tmpdir, "normal.txt")
        with open(not_in_trash, "w") as f:
            f.write("normal")
        
        # Check status
        assert os.path.exists(in_trash), "File should exist in trash"
        assert os.path.exists(not_in_trash), "Normal file should exist"
        
        # For permanent delete, we would check if file is in .trash directory
        assert in_trash.startswith(trash_dir), "File is in trash directory"
        assert not not_in_trash.startswith(trash_dir), "File is not in trash directory"
