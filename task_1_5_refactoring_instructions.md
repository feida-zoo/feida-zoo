# Task 1.5: 重构架构 - 分离关注点

## 任务目标
重构当前框架，将成员注册表管理和工作空间管理分离到专门的Manager类中，实现更好的关注点分离。

## 当前问题
当前`Spawner`类承担了太多职责：
1. 成员注册表管理（加载、保存、查询）
2. 工作空间创建和管理
3. 成员生命周期管理

这违反了单一职责原则，导致代码难以测试和维护。

## 重构方案

### 1. 创建 RegistryManager (framework/core/registry_manager.py)
**职责：**
- 加载和保存 registry.json
- 成员注册、查询、更新、删除
- 成员状态管理
- 注册表版本控制

**API设计：**
```python
class RegistryManager:
    def __init__(self, registry_file: Union[str, Path])
    def load(self) -> Dict
    def save(self) -> None
    def register_member(self, member_data: Dict) -> str
    def get_member(self, member_id: str) -> Optional[Dict]
    def list_members(self, status: Optional[str] = None) -> List[Dict]
    def update_member(self, member_id: str, updates: Dict) -> bool
    def delete_member(self, member_id: str) -> bool
    def update_member_status(self, member_id: str, status: str) -> bool
```

### 2. 创建 WorkspaceManager (framework/core/workspace_manager.py)
**职责：**
- 工作空间创建和初始化
- 工作空间删除（软删除/永久删除）
- 工作空间恢复
- 工作空间路径管理

**API设计：**
```python
class WorkspaceManager:
    def __init__(self, base_path: Union[str, Path], config_loader=None)
    def create_workspace(self, member_id: str, member_config: Dict) -> Path
    def delete_workspace(self, workspace_path: Union[str, Path], permanent: bool = False) -> bool
    def restore_workspace(self, workspace_path: Union[str, Path]) -> bool
    def get_workspace_path(self, member_id: str) -> Path
    def workspace_exists(self, member_id: str) -> bool
```

### 3. 重构 Spawner (framework/core/spawner.py)
**职责：**
- 协调成员创建流程
- 使用RegistryManager管理注册表
- 使用WorkspaceManager管理工作空间
- 保持原有API兼容性

**重构后的主要变化：**
1. 移除注册表加载/保存逻辑，委托给RegistryManager
2. 移除工作空间创建逻辑，委托给WorkspaceManager
3. 保持原有public API不变

### 4. 重构 PermissionManager (framework/core/permissions.py)
**重构：**
- 使用配置化的路径
- 与新的Manager类集成

## 具体实现步骤

### 步骤1: 创建RegistryManager
1. 创建`framework/core/registry_manager.py`
2. 实现成员注册表管理逻辑
3. 包含以下核心方法：
   - `load()` - 加载registry.json
   - `save()` - 保存registry.json
   - `register_member()` - 注册新成员
   - `get_member()` - 获取成员信息
   - `list_members()` - 列出所有成员
   - `update_member()` - 更新成员信息
   - `delete_member()` - 删除成员记录
   - `update_member_status()` - 更新成员状态

### 步骤2: 创建WorkspaceManager
1. 创建`framework/core/workspace_manager.py`
2. 实现工作空间管理逻辑
3. 使用现有的Workspace类进行安全删除操作
4. 包含以下核心方法：
   - `create_workspace()` - 创建工作空间
   - `delete_workspace()` - 删除工作空间
   - `restore_workspace()` - 恢复工作空间
   - `get_workspace_path()` - 获取工作空间路径
   - `workspace_exists()` - 检查工作空间是否存在

### 步骤3: 重构Spawner
1. 修改`framework/core/spawner.py`
2. 导入并使用RegistryManager和WorkspaceManager
3. 重构`spawn_member()`方法：
   - 使用WorkspaceManager创建工作空间
   - 使用RegistryManager注册成员
4. 重构`list_members()`, `get_member()`, `update_member_status()`, `delete_member()`方法
5. 保持原有API完全兼容

### 步骤4: 重构PermissionManager
1. 修改`framework/core/permissions.py`
2. 确保使用配置化的路径
3. 与新的Manager类集成

## 测试要求

### 1. RegistryManager单元测试
创建`framework/tests/ut/test_registry_manager.py`
测试用例：
- 测试注册表加载和保存
- 测试成员注册
- 测试成员查询
- 测试成员更新
- 测试成员删除
- 测试状态更新
- 测试成员列表过滤

### 2. WorkspaceManager单元测试
创建`framework/tests/ut/test_workspace_manager.py`
测试用例：
- 测试工作空间创建
- 测试工作空间删除（软删除）
- 测试工作空间恢复
- 测试工作空间永久删除
- 测试工作空间路径管理

### 3. 重构后的Spawner测试
创建`framework/tests/ut/test_spawner_refactored.py`
测试用例：
- 测试成员创建流程
- 测试原有API兼容性
- 测试错误处理
- 测试与Manager类的集成

### 4. 端到端测试
创建`framework/tests/st/test_member_creation_e2e.py`
测试用例：
- 测试完整的成员创建流程
- 测试成员管理生命周期
- 测试工作空间管理集成

## 注意事项

1. **保持向后兼容性**：确保现有代码可以无缝迁移
2. **错误处理**：保持原有的错误处理逻辑
3. **配置系统**：使用现有的ConfigLoader获取路径配置
4. **日志记录**：保持原有的日志记录功能
5. **类型提示**：添加完整的类型提示
6. **代码注释**：添加清晰的代码注释说明重构目的

## 验收标准

1. 所有现有测试通过
2. 新增的单元测试通过
3. 端到端测试通过
4. 代码覆盖率不降低
5. 原有功能保持不变
6. API完全兼容

## 文件清单

需要创建/修改的文件：
1. `framework/core/registry_manager.py` (新建)
2. `framework/core/workspace_manager.py` (新建)
3. `framework/core/spawner.py` (修改)
4. `framework/core/permissions.py` (修改)
5. `framework/core/__init__.py` (修改，导出新的Manager类)
6. `framework/tests/ut/test_registry_manager.py` (新建)
7. `framework/tests/ut/test_workspace_manager.py` (新建)
8. `framework/tests/ut/test_spawner_refactored.py` (新建)
9. `framework/tests/st/test_member_creation_e2e.py` (新建)

开始重构工作吧！