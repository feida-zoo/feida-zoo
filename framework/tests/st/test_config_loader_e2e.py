"""
ConfigLoader 集成测试（系统测试）
测试端到端配置加载流程
"""
import os
import pytest
import tempfile
import yaml
from pathlib import Path

# 待测试的类（将在实现后导入）
# from framework.core.config_loader import ConfigLoader, ConfigTemplateError, ConfigTemplateSyntaxError


class TestConfigLoaderE2E:
    """测试端到端配置加载流程"""
    
    def test_config_loader_e2e(self):
        """测试端到端配置加载流程"""
        # Arrange - 创建临时配置目录和文件
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            
            # 创建主配置文件
            main_config = {
                'app': {
                    'name': 'TestApp',
                    'version': '${env:APP_VERSION}'
                },
                'paths': {
                    'data': '${paths.data}',
                    'logs': '${base_dir}/logs'
                }
            }
            
            main_config_path = config_dir / "app.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # 设置环境变量
            os.environ['APP_VERSION'] = '1.0.0'
            
            # Act
            loader = ConfigLoader(base_path=str(tmpdir))
            loader.register_path('data', str(tmpdir / "data"))
            config = loader.load(str(main_config_path))
            
            # Assert
            assert config['app']['name'] == 'TestApp'
            assert config['app']['version'] == '1.0.0'
            assert config['paths']['data'] == str(tmpdir / "data")
            assert config['paths']['logs'] == str(tmpdir / "logs")
            
            # Cleanup
            del os.environ['APP_VERSION']
    
    def test_config_loader_e2e_nested_configs(self):
        """测试嵌套配置文件加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            
            # 创建数据库配置文件
            db_config = {
                'database': {
                    'host': '${env:DB_HOST}',
                    'port': 5432,
                    'name': 'test_db'
                }
            }
            
            db_config_path = config_dir / "database.yaml"
            with open(db_config_path, 'w') as f:
                yaml.dump(db_config, f)
            
            # 设置环境变量
            os.environ['DB_HOST'] = 'localhost'
            
            # Act
            loader = ConfigLoader(base_path=str(tmpdir))
            config = loader.load(str(db_config_path))
            
            # Assert
            assert config['database']['host'] == 'localhost'
            assert config['database']['port'] == 5432
            
            # Cleanup
            del os.environ['DB_HOST']


class TestConfigLoaderLoadYaml:
    """测试 YAML 文件加载与解析"""
    
    def test_config_loader_load_yaml(self):
        """测试 YAML 文件加载与解析"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange
            config_path = Path(tmpdir) / "test.yaml"
            config_data = {
                'name': 'TestConfig',
                'items': ['item1', 'item2', 'item3'],
                'settings': {
                    'enabled': True,
                    'count': 42
                }
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            # Act
            loader = ConfigLoader()
            config = loader.load(str(config_path))
            
            # Assert
            assert config['name'] == 'TestConfig'
            assert config['items'] == ['item1', 'item2', 'item3']
            assert config['settings']['enabled'] is True
            assert config['settings']['count'] == 42
    
    def test_config_loader_load_yaml_with_templates(self):
        """测试带模板的 YAML 文件加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange
            os.environ['SERVICE_NAME'] = 'MyService'
            
            config_path = Path(tmpdir) / "service.yaml"
            config_content = """
service:
  name: ${env:SERVICE_NAME}
  endpoint: /api/v1
  port: 8080
"""
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            # Act
            loader = ConfigLoader()
            config = loader.load(str(config_path))
            
            # Assert
            assert config['service']['name'] == 'MyService'
            assert config['service']['endpoint'] == '/api/v1'
            assert config['service']['port'] == 8080
            
            # Cleanup
            del os.environ['SERVICE_NAME']
    
    def test_config_loader_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        # Arrange
        loader = ConfigLoader()
        nonexistent_path = '/nonexistent/config.yaml'
        
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            loader.load(nonexistent_path)
    
    def test_config_loader_load_invalid_yaml(self):
        """测试加载无效的 YAML 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange
            config_path = Path(tmpdir) / "invalid.yaml"
            with open(config_path, 'w') as f:
                f.write("invalid: yaml: content: [unclosed")
            
            loader = ConfigLoader()
            
            # Act & Assert
            with pytest.raises(yaml.YAMLError):
                loader.load(str(config_path))


# 占位符类，确保测试可以导入（实现后将删除）
class ConfigLoader:
    """配置加载器 - 待实现"""
    
    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.getcwd()
        self.paths_registry = {}
    
    def load(self, config_path: str) -> dict:
        """加载并解析配置文件 - 待实现"""
        raise NotImplementedError("ConfigLoader.load 待实现")
    
    def resolve_template(self, value: str, context: dict = None) -> str:
        """解析模板变量 - 待实现"""
        raise NotImplementedError("ConfigLoader.resolve_template 待实现")
    
    def register_path(self, name: str, path: str):
        """注册路径变量"""
        self.paths_registry[name] = path


class ConfigTemplateError(Exception):
    """配置模板错误"""
    pass


class ConfigTemplateSyntaxError(Exception):
    """配置模板语法错误"""
    pass