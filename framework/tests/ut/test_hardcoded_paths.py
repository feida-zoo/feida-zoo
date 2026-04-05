"""
测试硬编码路径移除
验证所有模块正确使用环境变量或默认值
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSpawnerPaths:
    """测试 Spawner 类的路径处理"""

    def test_spawner_uses_env_var(self):
        """测试 Spawner 使用 FEIDA_ZOO_HOME 环境变量"""
        from framework.core.spawner import Spawner

        test_path = "/test/workspace/feida_zoo"
        with patch.dict(os.environ, {"FEIDA_ZOO_HOME": test_path}):
            # 使用临时目录避免实际创建文件
            with patch.object(Path, 'mkdir'):
                # 返回False避免触发json.load读取文件
                with patch.object(Path, 'exists', return_value=False):
                    spawner = Spawner()
                    assert str(spawner.base_path) == test_path

    def test_spawner_uses_default_when_no_env(self):
        """测试无环境变量时使用默认值"""
        from framework.core.spawner import Spawner

        # 确保环境变量不存在
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'mkdir'):
                # 返回False避免触发json.load读取文件
                with patch.object(Path, 'exists', return_value=False):
                    spawner = Spawner()
                    assert "/home/afei/workspace/code/feida_zoo" in str(spawner.base_path)
                    assert "panda" not in str(spawner.base_path)

    def test_spawner_accepts_explicit_path(self):
        """测试 Spawner 接受显式路径参数"""
        from framework.core.spawner import Spawner

        explicit_path = "/custom/explicit/path"
        with patch.object(Path, 'mkdir'):
            # 返回False避免触发json.load读取文件
            with patch.object(Path, 'exists', return_value=False):
                spawner = Spawner(base_path=explicit_path)
                assert str(spawner.base_path) == explicit_path


class TestPermissionsPaths:
    """测试 PermissionManager 类的路径处理"""

    def test_permissions_uses_env_var(self):
        """测试 PermissionManager 使用 FEIDA_ZOO_HOME 环境变量"""
        from framework.core.permissions import PermissionManager

        test_path = "/test/workspace/feida_zoo"
        expected_config_path = Path(test_path) / "framework" / "configs" / "permissions.yaml"

        with patch.dict(os.environ, {"FEIDA_ZOO_HOME": test_path}):
            with patch.object(Path, 'exists', return_value=False):
                pm = PermissionManager()
                assert pm.config_path == expected_config_path

    def test_permissions_uses_default_when_no_env(self):
        """测试无环境变量时使用默认值"""
        from framework.core.permissions import PermissionManager

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, 'exists', return_value=False):
                pm = PermissionManager()
                expected_default = "/home/afei/workspace/code/feida_zoo/framework/configs/permissions.yaml"
                assert str(pm.config_path) == expected_default
                assert "panda" not in str(pm.config_path)

    def test_permissions_accepts_explicit_path(self):
        """测试 PermissionManager 接受显式路径参数"""
        from framework.core.permissions import PermissionManager

        explicit_path = "/custom/config.yaml"
        with patch.object(Path, 'exists', return_value=False):
            pm = PermissionManager(config_path=explicit_path)
            assert str(pm.config_path) == explicit_path


class TestSystemYamlPaths:
    """测试 system.yaml 路径配置"""

    def test_yaml_paths_use_env_var_placeholder(self):
        """测试 YAML 文件使用环境变量占位符"""
        import yaml

        system_yaml_path = Path(__file__).parent.parent.parent / "configs" / "system.yaml"

        if system_yaml_path.exists():
            with open(system_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查使用环境变量占位符
            assert "${FEIDA_ZOO_HOME" in content or "${FEIDA_ZOO_HOME:-" in content, \
                "YAML should use FEIDA_ZOO_HOME environment variable"

            # 检查不应该有硬编码的 panda 路径
            assert "/home/afei/workspace/panda" not in content, \
                "YAML should not contain hardcoded panda paths"

    def test_yaml_default_path_is_correct(self):
        """测试 YAML 默认值是正确的"""
        import yaml

        system_yaml_path = Path(__file__).parent.parent.parent / "configs" / "system.yaml"

        if system_yaml_path.exists():
            with open(system_yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 默认值应该是新的路径，不是 panda
            assert "/home/afei/workspace/code/feida_zoo" in content, \
                "Default path should be /home/afei/workspace/code/feida_zoo"


class TestNoHardcodedPandaPaths:
    """集成测试：确保没有硬编码的 panda 路径"""

    def test_no_panda_in_spawner_source(self):
        """测试 Spawner 源代码中没有硬编码 panda 路径"""
        spawner_path = Path(__file__).parent.parent.parent / "core" / "spawner.py"

        with open(spawner_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 不应该有硬编码的 panda 路径
        assert "/home/afei/workspace/panda" not in content, \
            "spawner.py should not contain hardcoded /home/afei/workspace/panda"
        # 应该使用新的 zoo 路径
        assert "/home/afei/workspace/code/feida_zoo" in content, \
            "spawner.py should use /home/afei/workspace/code/feida_zoo"

    def test_no_panda_in_permissions_source(self):
        """测试 Permissions 源代码中没有硬编码 panda 路径"""
        permissions_path = Path(__file__).parent.parent.parent / "core" / "permissions.py"

        with open(permissions_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 不应该有硬编码的 panda 路径
        assert "/home/afei/workspace/panda" not in content, \
            "permissions.py should not contain hardcoded /home/afei/workspace/panda"
        # 应该使用新的 zoo 路径
        assert "/home/afei/workspace/code/feida_zoo" in content, \
            "permissions.py should use /home/afei/workspace/code/feida_zoo"

    def test_uses_env_var_pattern(self):
        """测试使用了环境变量模式"""
        spawner_path = Path(__file__).parent.parent.parent / "core" / "spawner.py"
        permissions_path = Path(__file__).parent.parent.parent / "core" / "permissions.py"

        with open(spawner_path, 'r', encoding='utf-8') as f:
            spawner_content = f.read()

        with open(permissions_path, 'r', encoding='utf-8') as f:
            permissions_content = f.read()

        # 应该使用环境变量
        assert "FEIDA_ZOO_HOME" in spawner_content, \
            "spawner.py should use FEIDA_ZOO_HOME environment variable"
        assert "FEIDA_ZOO_HOME" in permissions_content, \
            "permissions.py should use FEIDA_ZOO_HOME environment variable"
