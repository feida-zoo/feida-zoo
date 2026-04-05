import os
from unittest.mock import patch, MagicMock

class ConfigLoader:
    def load(self, path):
        pass

def get_workspace_root(config_loader):
    config = config_loader.load("paths.yaml")
    return config.get("paths", {}).get("workspace_root", ".")

def test_no_hardcoded_paths_with_mock():
    mock_loader = MagicMock()
    mock_loader.load.return_value = {
        "paths": {
            "workspace_root": "/mocked/workspace/root"
        }
    }
    
    root_path = get_workspace_root(mock_loader)
    mock_loader.load.assert_called_once_with("paths.yaml")
    assert root_path == "/mocked/workspace/root"
    assert "panda" not in root_path
