# 织巢（蚂蚁·工程师）任务 1.2 测试用例评审

**任务名称**: P1阶段 1.2 - 实现配置模板引擎
**开发者**: 织巢（蚂蚁·工程师）🐜
**评审者**: 毒刺🦂
**创建时间**: 2026-04-05
**文件位置**:
- 单元测试: `framework/tests/ut/test_config_loader.py`
- 集成测试: `framework/tests/st/test_config_loader_e2e.py`
- 技术方案参考: `framework/shared/alpha_fix_plan_p1.md`

---

## 一、测试范围概述

根据 `alpha_fix_plan_p1.md` 技术方案要求，本次实现 `ConfigLoader` 类，支持三种模板变量：
1. 环境变量：`${env:VAR_NAME}`
2. 路径变量：`${paths.xxx}`
3. 相对路径：`${base_dir}/xxx`

本次测试用例严格按照TDD流程编写，先编写测试，等待评审通过后再编写实现代码。

---

## 二、单元测试（UT）清单

### 2.1 test_config_loader_env_variable - 测试环境变量解析

**测试目的**: 验证 `${env:VAR_NAME}` 格式的环境变量能够正确解析。

**测试场景**:
- `test_config_loader_env_variable`: 基础环境变量解析
- `test_config_loader_env_variable_in_string`: 环境变量嵌入字符串中

**预期行为**:
- 当环境变量存在时，正确替换为环境变量值
- 可以在任意字符串位置嵌入环境变量

---

### 2.2 test_config_loader_path_variable - 测试路径变量解析

**测试目的**: 验证 `${paths.xxx}` 格式的路径变量能够正确解析。

**测试场景**:
- `test_config_loader_path_variable`: 基础路径变量解析
- `test_config_loader_path_variable_nested`: 路径变量组合使用

**预期行为**:
- 调用 `register_path(name, path)` 注册路径后，可以通过 `${paths.name}` 获取
- 可以与其他路径片段组合使用

---

### 2.3 test_config_loader_relative_path - 测试相对路径解析

**测试目的**: 验证 `${base_dir}/xxx` 格式的相对路径能够正确解析。

**测试场景**:
- `test_config_loader_relative_path`: 基础相对路径解析（指定 base_path）
- `test_config_loader_relative_path_default_cwd`: 默认使用当前工作目录

**预期行为**:
- 构造 `ConfigLoader(base_path=...)` 时，`${base_dir}` 替换为 base_path
- 不指定 base_path 时，默认使用当前工作目录

---

### 2.4 test_config_loader_recursive_resolution - 测试递归解析（变量嵌套）

**测试目的**: 验证变量嵌套可以正确递归解析。

**测试场景**:
- `test_config_loader_recursive_resolution`: 多层嵌套（`${paths.config} = ${base_dir}/config` → `${paths.config}/app.yaml`）
- `test_config_loader_multiple_variables`: 单个字符串包含多个变量

**预期行为**:
- 多次递归解析直到所有变量都被替换
- 支持多种变量类型混合使用

---

### 2.5 test_config_loader_missing_env_var - 测试缺失环境变量处理

**测试目的**: 验证缺失变量时抛出合理异常。

**测试场景**:
- `test_config_loader_missing_env_var`: 缺失环境变量
- `test_config_loader_unregistered_path`: 未注册路径变量

**预期行为**:
- 遇到缺失变量时抛出 `ConfigTemplateError` 异常
- 异常信息中包含缺失变量名称，便于调试

---

### 2.6 额外测试 - 语法错误处理

**测试目的**: 增强健壮性，验证语法错误处理。

**测试场景**:
- `test_config_loader_invalid_syntax`: `{env:}` 空变量名
- `test_config_loader_unclosed_brace`: `${env:VAR` 缺少闭合括号

**预期行为**:
- 抛出 `ConfigTemplateSyntaxError` 异常

---

## 三、集成测试（ST）清单

### 3.1 test_config_loader_e2e - 测试端到端配置加载流程

**测试目的**: 验证完整的配置加载流程。

**测试场景**:
- `test_config_loader_e2e`: 完整流程（环境变量 + 路径变量 + 相对路径）
- `test_config_loader_e2e_nested_configs`: 嵌套配置文件加载

**预期行为**:
- 从 YAML 文件加载配置
- 递归解析所有字符串值中的模板变量
- 返回正确解析后的配置字典

---

### 3.2 test_config_loader_load_yaml - 测试 YAML 文件加载与解析

**测试目的**: 验证 YAML 文件基础加载功能。

**测试场景**:
- `test_config_loader_load_yaml`: 正常 YAML 文件加载
- `test_config_loader_load_yaml_with_templates`: 带模板变量的 YAML 加载
- `test_config_loader_load_nonexistent_file`: 加载不存在的文件
- `test_config_loader_load_invalid_yaml`: 加载语法错误的 YAML

**预期行为**:
- 正常文件：返回正确的配置字典
- 不存在文件：抛出 `FileNotFoundError`
- 无效 YAML：抛出 `yaml.YAMLError`

---

## 四、异常分类设计

为了便于调用者捕获和处理不同类型的错误，设计了两类异常：

| 异常类 | 用途 |
|--------|------|
| `ConfigTemplateError` | 模板变量不存在或未注册（运行时错误） |
| `ConfigTemplateSyntaxError` | 模板语法错误（例如未闭合括号） |

---

## 五、待实现接口约定

测试用例中占位的 `ConfigLoader` 接口，实现时需要遵循以下约定：

```python
class ConfigLoader:
    def __init__(self, base_path: str = None):
        """构造函数
        :param base_path: 基础目录，用于 ${base_dir} 解析，默认使用当前工作目录
        """
        ...
    
    def resolve_template(self, value: str, context: dict = None) -> str:
        """解析单个字符串中的模板变量
        :param value: 包含模板变量的字符串
        :param context: 额外上下文（可选）
        :return: 解析后的字符串
        :raises ConfigTemplateError: 变量不存在
        :raises ConfigTemplateSyntaxError: 语法错误
        """
        ...
    
    def load(self, config_path: str) -> dict:
        """加载 YAML 配置文件并解析所有模板变量
        :param config_path: YAML 文件路径
        :return: 解析后的配置字典
        """
        ...
    
    def register_path(self, name: str, path: str):
        """注册路径变量
        :param name: 路径变量名
        :param path: 路径值
        """
        ...
```

---

## 六、目录结构

```
framework/
├── core/
│   ├── config_loader.py          # 待实现
│   └── ...
├── tests/
│   ├── ut/
│   │   └── test_config_loader.py # ✅ 已完成
│   ├── st/
│   │   └── test_config_loader_e2e.py # ✅ 已完成
│   └── ...
├── shared/
│   └── weaver_test_review_task1.2.md # 📝 当前文档
└── ...
```

---

## 七、评审检查清单

请毒刺🦂评审以下项目：

- [ ] 测试范围是否完整覆盖技术方案要求
- [ ] 测试场景设计是否合理
- [ ] 接口约定是否清晰
- [ ] 异常设计是否合理
- [ ] 是否遗漏了重要测试场景
- [ ] 是否需要调整测试结构

---

## 八、下一步计划

1. **毒刺评审通过后**，织巢将开始实现 `framework/core/config_loader.py`
2. 实现完成后运行所有测试用例
3. 提交实现代码并进行下一阶段评审

---

**文档版本**: v1.0
**状态**: 等待评审
