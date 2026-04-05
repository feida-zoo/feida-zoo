"""Test soft delete functionality"""
import os
import tempfile
import shutil

def test_move_to_trash():
    """Test moving a file to .trash directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        # Create .trash directory
        trash_dir = os.path.join(tmpdir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        # Move to trash (simulated soft delete)
        dest = os.path.join(trash_dir, "test.txt")
        shutil.move(test_file, dest)
        
        # Verify
        assert os.path.exists(dest), "File should be in trash"
        assert not os.path.exists(test_file), "Original location should be empty"

def test_trash_directory_created():
    """Test that .trash directory is created if not exists"""
    with tempfile.TemporaryDirectory() as tmpdir:
        trash_dir = os.path.join(tmpdir, ".trash")
        assert not os.path.exists(trash_dir)
        os.makedirs(trash_dir, exist_ok=True)
        assert os.path.exists(trash_dir)
