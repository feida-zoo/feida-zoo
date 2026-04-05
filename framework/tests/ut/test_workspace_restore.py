"""Test restore functionality"""
import os
import tempfile
import shutil

def test_restore_from_trash():
    """Test restoring a file from .trash to original location"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .trash with file
        trash_dir = os.path.join(tmpdir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        trash_file = os.path.join(trash_dir, "test.txt")
        with open(trash_file, "w") as f:
            f.write("restore test")
        
        # Restore to original location
        original = os.path.join(tmpdir, "test.txt")
        shutil.move(trash_file, original)
        
        # Verify
        assert os.path.exists(original), "File should be restored"
        assert not os.path.exists(trash_file), "Trash should be empty"

def test_restore_preserves_content():
    """Test that restored file content is preserved"""
    with tempfile.TemporaryDirectory() as tmpdir:
        content = "important data"
        
        trash_dir = os.path.join(tmpdir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        
        trash_file = os.path.join(trash_dir, "data.txt")
        with open(trash_file, "w") as f:
            f.write(content)
        
        original = os.path.join(tmpdir, "data.txt")
        shutil.move(trash_file, original)
        
        with open(original, "r") as f:
            restored = f.read()
        assert restored == content, "Content should be preserved"
