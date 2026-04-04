"""
ConfigLoader 集成测试（系统测试）
测试端到端配置加载流程

测试覆盖范围：
- 单个配置文件完整加载
- 嵌套配置文件解析
- 多文件引用与包含
- 错误恢复处理
- 性能测试
"""
import os
import pytest
import tempfile
import yaml
import time
from pathlib import Path
from unittest.mock import patch

# 从实际模块导入
from framework.core.config_loader import ConfigLoader, ConfigTemplateError, ConfigTemplateSyntaxError


class TestConfigLoaderE2EBasic:
    """测试基础端到端配置加载流程"""
    
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
            with patch.dict(os.environ, {'APP_VERSION': '1.0.0'}):
                # Act
                loader = ConfigLoader(base_path=str(tmpdir))
                loader.register_path('data', str(Path(tmpdir) / "data"))
                config = loader.load(str(main_config_path))
                
                # Assert
                assert config['app']['name'] == 'TestApp'
                assert config['app']['version'] == '1.0.0'
                assert config['paths']['data'] == str(Path(tmpdir) / "data")
                assert config['paths']['logs'] == str(Path(tmpdir) / "logs")
    
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
            with patch.dict(os.environ, {'DB_HOST': 'localhost'}):
                # Act
                loader = ConfigLoader(base_path=str(tmpdir))
                config = loader.load(str(db_config_path))
                
                # Assert
                assert config['database']['host'] == 'localhost'
                assert config['database']['port'] == 5432


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
            with patch.dict(os.environ, {'SERVICE_NAME': 'MyService'}):
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


class TestConfigLoaderE2EAdvanced:
    """高级集成测试 - 多文件包含、错误处理等"""
    
    def test_config_loader_include_other_config(self):
        """测试配置文件包含其他配置文件（多级引用）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建目录结构
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            
            # 1. 创建基础配置（数据库）
            with patch.dict(os.environ, {
                'DB_HOST': 'db.example.com',
                'DB_PORT': '5432'
            }):
                db_config = {
                    'database': {
                        'host': '${env:DB_HOST}',
                        'port': '${env:DB_PORT}',
                        'name': 'production'
                    }
                }
                db_path = config_dir / "database.yaml"
                with open(db_path, 'w') as f:
                    yaml.dump(db_config, f)
                
                # 2. 创建应用配置，包含多个路径变量
                app_config = {
                    'app': {
                        'name': 'MyApp',
                        'env': 'production'
                    },
                    'logging': {
                        'path': '${base_dir}/logs/app.log',
                        'level': 'info'
                    }
                }
                app_path = config_dir / "app.yaml"
                with open(app_path, 'w') as f:
                    yaml.dump(app_config, f)
                
                # 3. 创建主配置，组合前面两个配置
                main_config = {
                    'include': [
                        str(db_path),
                        str(app_path)
                    ],
                    'global': {
                        'debug': False,
                        'temp_dir': '${base_dir}/tmp'
                    }
                }
                main_path = config_dir / "main.yaml"
                with open(main_path, 'w') as f:
                    yaml.dump(main_config, f)
                
                # Act - 加载主配置，应该递归包含其他配置
                loader = ConfigLoader(base_path=str(tmpdir))
                config = loader.load(str(main_path))
                
                # Assert - 所有配置都应该正确加载和解析
                assert config['database']['host'] == 'db.example.com'
                assert config['database']['port'] == '5432'
                assert config['app']['name'] == 'MyApp'
                assert config['logging']['path'] == f"{tmpdir}/logs/app.log"
                assert config['global']['temp_dir'] == f"{tmpdir}/tmp"
                assert config['global']['debug'] is False
    
    def test_config_loader_partial_failure_handling(self):
        """测试部分解析失败时的错误处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange - 创建一个包含有效变量和无效变量的配置
            config_path = Path(tmpdir) / "mixed.yaml"
            config_data = {
                'valid_key': 'Valid value',
                'valid_templated': 'Hello world',
                'missing_env': '${env:THIS_VAR_DOES_NOT_EXIST}',  # 这会失败
                'nested': {
                    'valid': 'still valid',
                    'missing_path': '${paths.not_registered}'  # 这也会失败
                }
            }
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            loader = ConfigLoader(base_path=str(tmpdir))
            
            # Act & Assert - 遇到缺失变量应该立即失败，而不是忽略
            with pytest.raises(ConfigTemplateError):
                loader.load(str(config_path))
    
    def test_config_loader_complex_nested_structures(self):
        """测试复杂嵌套数据结构的完整解析"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'REGION': 'us-east-1',
                'AZ': 'us-east-1a',
                'ENV': 'production'
            }):
                # Arrange - 创建一个复杂的生产级配置结构
                config_path = Path(tmpdir) / "complex.yaml"
                config_data = {
                    'cluster': {
                        'name': '${env:ENV}-${env:REGION}',
                        'region': '${env:REGION}',
                        'availability_zone': '${env:AZ}',
                        'nodes': [
                            {
                                'name': 'node-1',
                                'address': '10.0.0.1',
                                'tags': ['cluster', '${env:REGION}']
                            },
                            {
                                'name': 'node-2',
                                'address': '10.0.0.2',
                                'tags': ['cluster', '${env:REGION}']
                            }
                        ]
                    },
                    'services': {
                        'frontend': {
                            'replicas': 3,
                            'resources': {
                                'cpu': '1000m',
                                'memory': '512Mi'
                            },
                            'env': [
                                {'name': 'REGION', 'value': '${env:REGION}'},
                                {'name': 'ENV', 'value': '${env:ENV}'}
                            ]
                        },
                        'backend': {
                            'replicas': 2,
                            'resources': {
                                'cpu': '2000m',
                                'memory': '1Gi'
                            }
                        }
                    }
                }
                with open(config_path, 'w') as f:
                    yaml.dump(config_data, f)
                
                # Act
                loader = ConfigLoader()
                resolved = loader.load(str(config_path))
                
                # Assert - 所有层级都应该正确解析
                assert resolved['cluster']['name'] == 'production-us-east-1'
                assert resolved['cluster']['region'] == 'us-east-1'
                assert resolved['cluster']['availability_zone'] == 'us-east-1a'
                assert len(resolved['cluster']['nodes']) == 2
                assert resolved['cluster']['nodes'][0]['tags'][1] == 'us-east-1'
                assert resolved['cluster']['nodes'][1]['tags'][1] == 'us-east-1'
                assert len(resolved['services']['frontend']['env']) == 2
                assert resolved['services']['frontend']['env'][0]['value'] == 'us-east-1'
                assert resolved['services']['frontend']['replicas'] == 3
    
    def test_config_loader_performance_large_config(self):
        """测试大配置文件的解析性能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Arrange - 创建一个包含大量模板变量的大型配置
            config_path = Path(tmpdir) / "large.yaml"
            
            # 生成 100 个服务配置
            services = {}
            for i in range(100):
                services[f'service_{i}'] = {
                    'name': f'Service {i}',
                    'endpoint': f'http://service-{i}.${{env:DOMAIN}}',
                    'port': 8080 + i,
                    'enabled': True
                }
            
            config_data = {
                'global': {
                    'environment': '${env:ENV}',
                    'domain': '${env:DOMAIN}'
                },
                'services': services
            }
            
            with patch.dict(os.environ, {
                'ENV': 'staging',
                'DOMAIN': 'example.com'
            }):
                with open(config_path, 'w') as f:
                    yaml.dump(config_data, f)
                
                # Act - 测量解析时间
                loader = ConfigLoader()
                start_time = time.time()
                resolved = loader.load(str(config_path))
                end_time = time.time()
                
                # Assert
                assert resolved['global']['environment'] == 'staging'
                assert resolved['global']['domain'] == 'example.com'
                assert len(resolved['services']) == 100
                # 检查随机一个服务是否正确解析
                assert resolved['services']['service_42']['endpoint'] == 'http://service-42.example.com'
                # 应该在 500ms 内完成解析
                assert end_time - start_time < 0.5, f"Large config parsing too slow: {end_time - start_time:.3f}s"
    
    def test_config_loader_type_preservation(self):
        """测试解析后类型保持（非字符串类型不应被改变）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "types.yaml"
            config_data = {
                'int_value': 42,
                'float_value': 3.14159,
                'bool_true': True,
                'bool_false': False,
                'null_value': None,
                'string_value': 'plain string',
                'templated_string': 'version ${env:VERSION}',
                'list_of_ints': [1, 2, 3, 4],
                'list_of_mixed': [1, 'two', 3.0, True, None]
            }
            
            with patch.dict(os.environ, {'VERSION': '1.0'}):
                with open(config_path, 'w') as f:
                    yaml.dump(config_data, f)
                
                loader = ConfigLoader()
                resolved = loader.load(str(config_path))
                
                # Assert - 保持原始类型
                assert isinstance(resolved['int_value'], int)
                assert resolved['int_value'] == 42
                
                assert isinstance(resolved['float_value'], float)
                assert resolved['float_value'] == pytest.approx(3.14159)
                
                assert isinstance(resolved['bool_true'], bool)
                assert resolved['bool_true'] is True
                
                assert isinstance(resolved['bool_false'], bool)
                assert resolved['bool_false'] is False
                
                assert resolved['null_value'] is None
                
                assert isinstance(resolved['string_value'], str)
                assert resolved['templated_string'] == 'version 1.0'
                
                assert isinstance(resolved['list_of_ints'], list)
                assert resolved['list_of_ints'] == [1, 2, 3, 4]
                
                assert isinstance(resolved['list_of_mixed'], list)
                assert resolved['list_of_mixed'] == [1, 'two', 3.0, True, None]
