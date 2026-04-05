import yaml
import os

def test_path_config_integration():
    config_path = os.path.join(os.path.dirname(__file__), "../../configs/paths.yaml")
    assert os.path.exists(config_path), "Config file should exist"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    assert "paths" in config
    assert "workspace_root" in config["paths"]
    assert config["paths"]["workspace_root"] != "/home/afei/workspace/panda"
