"""
ConfigLoader 单元测试
测试模板变量解析功能
"""
import os
import pytest
import tempfile
from unittest.mock import patch

# 待测试的类（将在实现后导入）
# from framework.core.config_loader import ConfigLoader, ConfigTemplateError, ConfigTemplateSyntaxError


class TestConfigLoaderEnvVariable:
    """测试环境变量解析 ${env:VAR_NAME}"""
    
    def test_config_loader_env_variable(self):
        """测试环境变量解析 ${env:VAR_NAME}"""
        # Arrange
        os.environ['TEST_VAR'] = 'test_value'
        loader = ConfigLoader()
        
        # Act
        result = loader.resolve_template('${env:TEST_VAR}')
        
        # Assert
        assert result == 'test_value'
        
        # Cleanup
        del os.environ['TEST_VAR']
    
    def test_config_loader_env_variable_in_string(self):
        """测试环境变量嵌入在字符串中"""
        # Arrange
        os.environ['APP_NAME'] = 'MyApp'
        loader = ConfigLoader()
        
        # Act
        result = loader.resolve_template('Welcome to ${env:APP_NAME}!')
        
        # Assert
        assert result == 'Welcome to MyApp!'
        
        # Cleanup
        del os.environ['APP_NAME']


class TestConfigLoaderPathVariable:
    """测试路径变量解析 ${paths.xxx}"""
    
    def test_config_loader_path_variable(self):
        """测试路径变量解析 ${paths.xxx}"""
        # Arrange
        loader = ConfigLoader()
        loader.register_path('data', '/var/data')
        
        # Act
        result = loader.resolve_template('${paths.data}')
        
        # Assert
        assert result == '/var/data'
    
    def test_config_loader_path_variable_nested(self):
        """测试路径变量在路径中"""
        # Arrange
        loader = ConfigLoader()
        loader.register_path('logs', '/app/logs')
        
        # Act
        result = loader.resolve_template('${paths.logs}/error.log')
        
        # Assert
        assert result == '/app/logs/error.log'


class TestConfigLoaderRelativePath:
    """测试相对路径解析 ${base_dir}/xxx"""
    
    def test_config_loader_relative_path(self):
        """测试相对路径解析 ${base_dir}/xxx"""
        # Arrange
        base_path = '/home/user/project'
        loader = ConfigLoader(base_path=base_path)
        
        # Act
        result = loader.resolve_template('${base_dir}/config/app.yaml')
        
        # Assert
        assert result == '/home/user/project/config/app.yaml'
    
    def test_config_loader_relative_path_default_cwd(self):
        """测试默认使用当前工作目录"""
        # Arrange
        loader = ConfigLoader()  # 不指定 base_path
        
        # Act - 应该使用当前工作目录
        result = loader.resolve_template('${base_dir}/test.yaml')
        
        # Assert
        assert result.endswith('/test.yaml')
        assert os.getcwd() in result


class TestConfigLoaderRecursiveResolution:
    """测试递归解析（变量嵌套）"""
    
    def test_config_loader_recursive_resolution(self):
        """测试递归解析（变量嵌套）"""
        # Arrange
        os.environ['DB_HOST'] = 'localhost'
        loader = ConfigLoader(base_path='/app')
        loader.register_path('config', '${base_dir}/config')
        
        # Act
        result = loader.resolve_template('${paths.config}/database.yaml')
        
        # Assert - 应该先解析 paths.config，再解析其中的 ${base_dir}
        assert result == '/app/config/database.yaml'
        
        # Cleanup
        del os.environ['DB_HOST']
    
    def test_config_loader_multiple_variables(self):
        """测试字符串中包含多个变量"""
        # Arrange
        os.environ['USER'] = 'admin'
        loader = ConfigLoader(base_path='/home/app')
        
        # Act
        result = loader.resolve_template('${base_dir}/users/${env:USER}/config')
        
        # Assert
        assert result == '/home/app/users/admin/config'
        
        # Cleanup
        del os.environ['USER']


class TestConfigLoaderMissingEnvVar:
    """测试缺失环境变量处理"""
    
    def test_config_loader_missing_env_var(self):
        """测试缺失环境变量处理"""
        # Arrange
        loader = ConfigLoader()
        
        # 确保环境变量不存在
        if 'NON_EXISTENT_VAR' in os.environ:
            del os.environ['NON_EXISTENT_VAR']
        
        # Act & Assert
        with pytest.raises(ConfigTemplateError) as exc_info:
            loader.resolve_template('${env:NON_EXISTENT_VAR}')
        
        assert 'NON_EXISTENT_VAR' in str(exc_info.value)
        assert 'environment variable' in str(exc_info.value).lower()
    
    def test_config_loader_unregistered_path(self):
        """测试未注册路径变量处理"""
        # Arrange
        loader = ConfigLoader()
        # 确保 'unregistered' 未注册
        
        # Act & Assert
        with pytest.raises(ConfigTemplateError) as exc_info:
            loader.resolve_template('${paths.unregistered}')
        
        assert 'unregistered' in str(exc_info.value)
        assert 'available paths' in str(exc_info.value).lower() or 'registered' in str(exc_info.value).lower()


class TestConfigLoaderSyntaxError:
    """测试语法错误处理"""
    
    def test_config_loader_invalid_syntax(self):
        """测试无效语法处理"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert
        with pytest.raises(ConfigTemplateSyntaxError) as exc_info:
            loader.resolve_template('${env:}')  # 空变量名
        
        assert 'syntax' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()
    
    def test_config_loader_unclosed_brace(self):
        """测试未闭合的大括号"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert
        with pytest.raises(ConfigTemplateSyntaxError) as exc_info:
            loader.resolve_template('${env:VAR')  # 缺少闭合 }
        
        assert 'unclosed' in str(exc_info.value).lower() or 'syntax' in str(exc_info.value).lower()


# 占位符类，确保测试可以导入（实现后将删除）  
class ConfigLoader:
    """配置加载器 - 待实现"""
    
    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.getcwd()
        self.paths_registry = {}
    
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