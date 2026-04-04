"""
ConfigLoader 单元测试
测试模板变量解析功能

测试覆盖范围：
- 环境变量解析 ${env:VAR_NAME}
- 路径变量解析 ${paths.xxx}
- 相对路径解析 ${base_dir}/xxx
- 递归解析（变量嵌套）
- 异常处理和边界条件
- 复杂数据结构解析
- 递归循环检测
"""
import os
import pytest
import time
from unittest.mock import patch

# 从实际模块导入
from framework.core.config_loader import ConfigLoader, ConfigTemplateError, ConfigTemplateSyntaxError


class TestConfigLoaderEnvVariable:
    """测试环境变量解析 ${env:VAR_NAME}"""
    
    def test_config_loader_env_variable(self):
        """测试环境变量解析 ${env:VAR_NAME}"""
        # Arrange - 使用 mock.patch.dict 安全修改环境变量
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            loader = ConfigLoader()
            
            # Act
            result = loader.resolve_template('${env:TEST_VAR}')
            
            # Assert
            assert result == 'test_value'
    
    def test_config_loader_env_variable_in_string(self):
        """测试环境变量嵌入在字符串中"""
        # Arrange
        with patch.dict(os.environ, {'APP_NAME': 'MyApp'}):
            loader = ConfigLoader()
            
            # Act
            result = loader.resolve_template('Welcome to ${env:APP_NAME}!')
            
            # Assert
            assert result == 'Welcome to MyApp!'
    
    def test_config_loader_empty_env_var(self):
        """测试空环境变量处理"""
        # Arrange
        with patch.dict(os.environ, {'EMPTY_VAR': ''}):
            loader = ConfigLoader()
            
            # Act
            result = loader.resolve_template('${env:EMPTY_VAR}')
            
            # Assert - 空值应该被保留
            assert result == ''
    
    def test_config_loader_variable_name_conflict(self):
        """测试路径变量与环境变量同名时的处理"""
        # Arrange - 两者都定义 'same_name'
        with patch.dict(os.environ, {'same_name': 'from_env'}):
            loader = ConfigLoader()
            loader.register_path('same_name', 'from_paths')
            
            # Act - 变量类型由前缀决定，不会冲突
            result_env = loader.resolve_template('${env:same_name}')
            result_path = loader.resolve_template('${paths.same_name}')
            
            # Assert
            assert result_env == 'from_env'
            assert result_path == 'from_paths'
    
    def test_config_loader_special_characters(self):
        """测试变量名包含特殊字符（-、_、.）"""
        # Arrange
        with patch.dict(os.environ, {
            'API-KEY': 'abc123',
            'api.key': 'def456',
            'api_key': 'ghi789'
        }):
            loader = ConfigLoader()
            
            # Act & Assert - 特殊字符名称应该能够正确解析
            assert loader.resolve_template('${env:API-KEY}') == 'abc123'
            assert loader.resolve_template('${env:api.key}') == 'def456'
            assert loader.resolve_template('${env:api_key}') == 'ghi789'


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
        with patch.dict(os.environ, {'DB_HOST': 'localhost'}):
            loader = ConfigLoader(base_path='/app')
            loader.register_path('config', '${base_dir}/config')
            
            # Act
            result = loader.resolve_template('${paths.config}/database.yaml')
            
            # Assert - 应该先解析 paths.config，再解析其中的 ${base_dir}
            assert result == '/app/config/database.yaml'
    
    def test_config_loader_multiple_variables(self):
        """测试字符串中包含多个变量"""
        # Arrange
        with patch.dict(os.environ, {'USER': 'admin'}):
            loader = ConfigLoader(base_path='/home/app')
            
            # Act
            result = loader.resolve_template('${base_dir}/users/${env:USER}/config')
            
            # Assert
            assert result == '/home/app/users/admin/config'
    
    def test_config_loader_context_parameter(self):
        """测试 resolve_template 的 context 参数使用"""
        # Arrange
        loader = ConfigLoader(base_path='/app')
        context = {
            'app_name': 'MyApp',
            'version': '1.0.0'
        }
        
        # Act - context 参数应该提供额外的变量
        result = loader.resolve_template('${context.app_name} v${context.version}', context)
        
        # Assert
        assert result == 'MyApp v1.0.0'
    
    def test_config_loader_deep_nesting(self):
        """测试深度嵌套解析（多级嵌套）"""
        # Arrange
        loader = ConfigLoader(base_path='/root')
        loader.register_path('a', '${base_dir}')
        loader.register_path('b', '${paths.a}/a')
        loader.register_path('c', '${paths.b}/b')
        loader.register_path('d', '${paths.c}/c')
        
        # Act
        result = loader.resolve_template('${paths.d}')
        
        # Assert
        assert result == '/root/a/b/c'
    
    def test_config_loader_recursive_loop_detection(self):
        """测试递归循环检测（防止无限递归）${a} -> ${b} -> ${a}"""
        # Arrange
        loader = ConfigLoader()
        # 创建循环引用
        loader.register_path('a', '${paths.b}')
        loader.register_path('b', '${paths.a}')
        
        # Act & Assert - 应该检测到循环并抛出异常
        with pytest.raises(ConfigTemplateError) as exc_info:
            loader.resolve_template('${paths.a}')
        
        assert 'recursion' in str(exc_info.value).lower() or 'loop' in str(exc_info.value).lower()
    
    def test_config_loader_nested_dict_resolution(self):
        """测试嵌套字典结构中的变量解析"""
        # Arrange
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'DB_NAME': 'test_db'
        }):
            loader = ConfigLoader()
            
            # 嵌套数据结构（模拟实际配置中的结构）
            nested_data = {
                'database': {
                    'host': '${env:DB_HOST}',
                    'port': '${env:DB_PORT}',
                    'credentials': {
                        'username': 'admin',
                        'database': '${env:DB_NAME}'
                    }
                },
                'app': {
                    'name': 'Test App',
                    'url': 'http://${env:DB_HOST}:${env:DB_PORT}'
                }
            }
            
            # Act - 递归解析整个嵌套结构
            resolved = loader.resolve_recursive(nested_data)
            
            # Assert - 所有层级都应该被正确解析
            assert resolved['database']['host'] == 'localhost'
            assert resolved['database']['port'] == '5432'
            assert resolved['database']['credentials']['database'] == 'test_db'
            assert resolved['app']['url'] == 'http://localhost:5432'
    
    def test_config_loader_list_resolution(self):
        """测试列表中的变量解析"""
        # Arrange
        with patch.dict(os.environ, {
            'NODE1': '192.168.1.10',
            'NODE2': '192.168.1.11'
        }):
            loader = ConfigLoader()
            
            # 包含模板变量的列表
            data = {
                'nodes': [
                    '${env:NODE1}',
                    '${env:NODE2}',
                    '192.168.1.12'  # 不需要解析
                ],
                'configs': [
                    {'host': '${env:NODE1}'},
                    {'host': '${env:NODE2}'}
                ]
            }
            
            # Act
            resolved = loader.resolve_recursive(data)
            
            # Assert
            assert resolved['nodes'][0] == '192.168.1.10'
            assert resolved['nodes'][1] == '192.168.1.11'
            assert resolved['nodes'][2] == '192.168.1.12'
            assert resolved['configs'][0]['host'] == '192.168.1.10'
            assert resolved['configs'][1]['host'] == '192.168.1.11'
    
    def test_config_loader_mixed_types(self):
        """测试混合类型（字符串与非字符串混合）"""
        # Arrange
        loader = ConfigLoader()
        loader.register_path('data', '/data')
        
        # 混合类型数据
        data = {
            'string_var': '${paths.data}/file.txt',  # 需要解析
            'int_var': 42,                          # 不需要解析
            'bool_var': True,                       # 不需要解析
            'float_var': 3.14,                      # 不需要解析
            'none_var': None,                       # 不需要解析
            'empty_str': '',                        # 不需要解析
        }
        
        # Act
        resolved = loader.resolve_recursive(data)
        
        # Assert
        assert resolved['string_var'] == '/data/file.txt'
        assert resolved['int_var'] == 42
        assert resolved['bool_var'] is True
        assert resolved['float_var'] == 3.14
        assert resolved['none_var'] is None
        assert resolved['empty_str'] == ''
    
    def test_config_loader_long_variable_name(self):
        """测试超长变量名处理"""
        # Arrange
        long_name = 'a' * 100  # 100 字符的超长名称
        with patch.dict(os.environ, {long_name: 'long_value'}):
            loader = ConfigLoader()
            
            # Act
            template = '${env:' + long_name + '}'
            result = loader.resolve_template(template)
            
            # Assert
            assert result == 'long_value'
    
    def test_config_loader_escape_characters(self):
        """测试转义字符处理（$、{、}）"""
        # Arrange
        loader = ConfigLoader()
        
        # 测试包含 $ 但不是模板的情况
        # 测试文本中的美元符号、大括号
        result = loader.resolve_template('Price: $100')
        assert result == 'Price: $100'
        
        # 测试不完整的 $ 符号
        result = loader.resolve_template('$')
        assert result == '$'
        
        # 测试大括号不构成模板的情况
        result = loader.resolve_template('{plain} text')
        assert result == '{plain} text'


class TestConfigLoaderMissingHandling:
    """测试缺失变量处理"""
    
    def test_config_loader_missing_env_var(self):
        """测试缺失环境变量处理"""
        # Arrange
        loader = ConfigLoader()
        
        # 确保环境变量不存在，使用 mock 清除
        with patch.dict(os.environ, {}, clear=True):
            # Act & Assert
            with pytest.raises(ConfigTemplateError) as exc_info:
                loader.resolve_template('${env:NON_EXISTENT_VAR}')
            
            assert 'NON_EXISTENT_VAR' in str(exc_info.value)
            assert 'environment variable' in str(exc_info.value).lower()
    
    def test_config_loader_unregistered_path(self):
        """测试未注册路径变量处理"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert
        with pytest.raises(ConfigTemplateError) as exc_info:
            loader.resolve_template('${paths.unregistered}')
        
        assert 'unregistered' in str(exc_info.value)
        assert 'available paths' in str(exc_info.value).lower() or 'registered' in str(exc_info.value).lower()


class TestConfigLoaderSyntaxError:
    """测试语法错误处理"""
    
    def test_config_loader_invalid_syntax_empty_name(self):
        """测试无效语法处理 - 空变量名"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert
        with pytest.raises(ConfigTemplateSyntaxError) as exc_info:
            loader.resolve_template('${env:}')  # 空变量名
        
        assert 'syntax' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()
        assert 'empty' in str(exc_info.value).lower()
    
    def test_config_loader_unclosed_brace(self):
        """测试未闭合的大括号"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert
        with pytest.raises(ConfigTemplateSyntaxError) as exc_info:
            loader.resolve_template('${env:VAR')  # 缺少闭合 }
        
        assert 'unclosed' in str(exc_info.value).lower() or 'syntax' in str(exc_info.value).lower()
    
    def test_config_loader_invalid_prefix(self):
        """测试未知前缀处理"""
        # Arrange
        loader = ConfigLoader()
        
        # Act & Assert - 未知前缀应该抛出语法错误
        with pytest.raises(ConfigTemplateSyntaxError) as exc_info:
            loader.resolve_template('${unknown:var}')
        
        assert 'prefix' in str(exc_info.value).lower() or 'unknown' in str(exc_info.value).lower()


class TestConfigLoaderPerformance:
    """简单性能测试"""
    
    def test_config_loader_performance_many_variables(self):
        """测试大量模板变量的解析性能"""
        # Arrange
        loader = ConfigLoader()
        
        # 注册 100 个路径变量
        for i in range(100):
            loader.register_path(f'path_{i}', f'/path/{i}')
        
        # 构建包含所有变量的模板
        template_parts = [f'${{paths.path_{i}}}' for i in range(100)]
        template = '/'.join(template_parts)
        
        # Act - 测量解析时间
        start_time = time.time()
        result = loader.resolve_template(template)
        end_time = time.time()
        
        # Assert - 应该在合理时间内完成（100ms 以内）
        assert end_time - start_time < 0.1  # 100ms
        # 每个注册路径 /path/{i} 包含 2 个斜杠，用 / 连接 100 个变量 → 总斜杠数 = (100-1) + 100*2 = 299 → 分割长度 = 300
        assert len(result.split('/')) == 300
