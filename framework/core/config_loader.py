"""
配置模板引擎 - ConfigLoader
P1阶段任务1.2 - 配置模板引擎实现

功能：
- 解析配置文件中的模板变量
- 支持 ${env:VAR_NAME} 环境变量引用
- 支持 ${paths.name} 路径变量引用
- 支持 ${base_dir} 基准目录引用
- 支持 ${context.key} 上下文变量引用
- 递归解析，支持嵌套变量
- 检测并防止无限递归循环
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List, Union


class ConfigTemplateError(Exception):
    """配置模板错误基类"""
    pass


class ConfigTemplateSyntaxError(ConfigTemplateError):
    """配置模板语法错误"""
    pass


class ConfigLoader:
    """
    配置模板加载器
    
    支持解析配置中的模板变量：
    - ${env:VAR_NAME} - 环境变量
    - ${paths.name} - 已注册路径变量
    - ${base_dir} - 配置文件基准目录
    - ${context.key} - 上下文变量（动态传入）
    """
    
    # 模板变量正则表达式：匹配 ${...} 格式的变量
    TEMPLATE_PATTERN = re.compile(r'\$\{([^}]+)\}')
    
    def __init__(self, base_path: Optional[str] = None):
        """
        初始化 ConfigLoader
        
        Args:
            base_path: 基准目录路径，用于解析 ${base_dir}
        """
        self.base_path = base_path if base_path is not None else os.getcwd()
        self.paths_registry: Dict[str, str] = {}
    
    def register_path(self, name: str, path: str) -> None:
        """
        注册一个路径变量
        
        Args:
            name: 变量名
            path: 路径值（可以包含模板变量，将在解析时递归处理）
        """
        self.paths_registry[name] = path
    
    def resolve_template(self, value: str, context: Optional[Dict[str, Any]] = None, 
                        max_depth: int = 100) -> str:
        """
        解析字符串中的模板变量
        
        Args:
            value: 包含模板变量的字符串
            context: 额外的上下文变量，用于 ${context.key} 引用
            max_depth: 最大递归深度，防止无限递归
        
        Returns:
            解析后的字符串
        
        Raises:
            ConfigTemplateError: 当变量未定义或解析错误时
            ConfigTemplateSyntaxError: 当模板语法错误时
        """
        if not isinstance(value, str):
            return str(value)
        
        # 检查未闭合的大括号：如果有 ${ 但没有对应的 }
        # 统计出现次数，如果不相等则说明有未闭合
        open_count = value.count('${')
        close_count = value.count('}')
        if open_count > close_count:
            raise ConfigTemplateSyntaxError(
                f"Invalid syntax: unclosed brace in template '{value}'. "
                f"Expected '}}' to close '${{'."
            )
        
        current_value = value
        current_depth = 0
        
        while current_depth < max_depth:
            current_depth += 1
            
            # 检查是否还有模板变量需要解析
            matches = list(self.TEMPLATE_PATTERN.finditer(current_value))
            if not matches:
                break
            
            # 构建新的值，替换所有匹配的变量
            new_value = current_value
            for match in reversed(matches):  # 从后往前替换，避免位置偏移
                var_expr = match.group(1)
                start, end = match.span()
                
                # 解析变量表达式
                replacement = self._evaluate_variable(var_expr, context)
                new_value = new_value[:start] + replacement + new_value[end:]
            
            current_value = new_value
        
        # 检查是否超过最大递归深度
        if current_depth >= max_depth:
            raise ConfigTemplateError(
                f"Template resolution exceeded maximum recursion depth ({max_depth}). "
                f"Possible circular reference in: {value}"
            )
        
        return current_value
    
    def _evaluate_variable(self, var_expr: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        评估单个模板变量表达式
        
        Args:
            var_expr: 变量表达式（不包含 ${}）
            context: 上下文变量
        
        Returns:
            变量值字符串
        
        Raises:
            ConfigTemplateError: 当变量未定义时
            ConfigTemplateSyntaxError: 当语法错误时
        """
        var_expr = var_expr.strip()
        
        if not var_expr:
            raise ConfigTemplateSyntaxError(
                f"Empty variable expression in template"
            )
        
        # 环境变量: ${env:VAR_NAME}
        if var_expr.startswith('env:'):
            env_var_name = var_expr[4:]
            if not env_var_name:
                raise ConfigTemplateSyntaxError(
                    f"Invalid syntax: empty environment variable name in '${{env:}}'"
                )
            env_value = os.environ.get(env_var_name)
            if env_value is None:
                raise ConfigTemplateError(
                    f"Environment variable '{env_var_name}' is not defined. "
                    f"Please set this environment variable and try again."
                )
            return env_value
        
        # 路径变量: ${paths.name}
        elif var_expr.startswith('paths.'):
            path_key = var_expr[6:]
            if not path_key:
                raise ConfigTemplateSyntaxError(
                    f"Invalid syntax: empty path variable name in '${{paths.}}'"
                )
            if path_key not in self.paths_registry:
                available_paths = list(self.paths_registry.keys())
                available_str = ', '.join(f"'{p}'" for p in available_paths) if available_paths else 'none registered'
                raise ConfigTemplateError(
                    f"Path variable '{path_key}' is not registered. "
                    f"Available paths: {available_str}. "
                    f"Use loader.register_path('{path_key}', '/path/to/dir') to register."
                )
            return self.paths_registry[path_key]
        
        # 上下文变量: ${context.key}
        elif var_expr.startswith('context.'):
            if context is None:
                raise ConfigTemplateError(
                    f"Context variable '{var_expr}' requested but no context provided. "
                    f"Pass context dictionary to resolve_template() or load() method."
                )
            context_key = var_expr[8:]
            if context_key not in context:
                available_context = list(context.keys())
                available_str = ', '.join(f"'{c}'" for c in available_context) if available_context else 'empty'
                raise ConfigTemplateError(
                    f"Context variable '{context_key}' not found in context. "
                    f"Available context keys: {available_str}."
                )
            return str(context[context_key])
        
        # 基准目录: ${base_dir}
        elif var_expr == 'base_dir':
            return str(self.base_path)
        
        # 未知前缀
        else:
            # 检查是否包含冒号（可能是错误的前缀）
            if ':' in var_expr:
                prefix = var_expr.split(':')[0]
                raise ConfigTemplateSyntaxError(
                    f"Unknown variable prefix '{prefix}:' in '${{{var_expr}}}'. "
                    f"Supported prefixes are: env:, paths:, context:. "
                    f"Use '${{env:VAR}}' for environment variables, "
                    f"'${{paths.name}}' for registered paths, "
                    f"'${{base_dir}}' for base directory."
                )
            else:
                # 纯变量名，检查是否注册为路径
                if var_expr in self.paths_registry:
                    return self.paths_registry[var_expr]
                raise ConfigTemplateSyntaxError(
                    f"Unrecognized variable expression '${{{var_expr}}}'. "
                    f"Supported formats: ${{env:VAR}}, ${{paths.name}}, ${{context.key}}, ${{base_dir}}. "
                    f"Use loader.register_path('{var_expr}', '/path') to register as path variable."
                )
    
    def resolve_recursive(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        递归解析数据结构中的所有模板变量
        
        Args:
            data: 任意数据结构（dict, list, str, 其他类型保持不变）
            context: 上下文变量
        
        Returns:
            解析后的数据结构
        
        Raises:
            ConfigTemplateError: 当变量未定义时
        """
        if isinstance(data, str):
            return self.resolve_template(data, context)
        elif isinstance(data, dict):
            return {
                key: self.resolve_recursive(value, context)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                self.resolve_recursive(item, context)
                for item in data
            ]
        else:
            # 其他类型保持不变（int, float, bool, None）
            return data
    
    def load(self, config_path: str) -> Dict[str, Any]:
        """
        加载并解析 YAML 配置文件
        
        Args:
            config_path: 配置文件路径
        
        Returns:
            解析后的配置字典
        
        Raises:
            FileNotFoundError: 文件不存在
            yaml.YAMLError: YAML 语法错误
            ConfigTemplateError: 模板解析错误
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # 读取 YAML 内容
        with open(config_file, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
        
        if raw_config is None:
            return {}
        
        # 处理 include 指令：递归加载包含的配置文件
        merged_config = {}
        include_files = []
        
        # 如果有 include 键，先加载包含的配置
        if isinstance(raw_config, dict) and 'include' in raw_config:
            include_list = raw_config.pop('include')
            if not isinstance(include_list, list):
                include_list = [include_list]
            
            # 加载每个包含的配置文件
            # 相对路径相对于当前配置文件所在目录
            config_dir = config_file.parent
            for include_path in include_list:
                # 如果是相对路径，相对于当前配置目录
                if not Path(include_path).is_absolute():
                    full_include_path = str(config_dir / include_path)
                else:
                    full_include_path = include_path
                
                # 递归加载
                included_config = self.load(full_include_path)
                merged_config.update(included_config)
        
        # 合并当前配置（覆盖include中的配置）
        merged_config.update(raw_config)
        
        # 递归解析所有模板变量
        resolved_config = self.resolve_recursive(merged_config)
        
        return resolved_config
