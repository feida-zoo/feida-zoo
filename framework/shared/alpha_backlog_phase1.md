# P1问题修复工作清单

> 创建者：阿尔法（玄龟）🐢
> 创建时间：2026-04-05
> 阶段：Phase 1 - P1阻断级问题修复

---

## 📋 任务清单

### 🔴 优先级1：立即修复（阻塞问题）

#### 任务 1.1：修复 datetime 导入错误
**文件**: `framework/core/permissions.py`
**严重性**: P1 - 运行时崩溃
**状态**: ⏳ 待处理
**描述**: 在 `_log_access` 方法中使用了 `datetime.now().isoformat()`，但文件顶部没有导入 `datetime` 模块。

**修复步骤**:
1. 在文件顶部添加 `from datetime import datetime`
2. 验证修复后运行 `python -m py_compile permissions.py`
3. 运行单元测试确保没有其他导入问题

**验收标准**:
- [ ] permissions.py 可以正常编译
- [ ] 权限检查功能不会因导入错误崩溃

---

#### 任务 1.2：实现配置模板引擎
**文件**: `framework/core/config_loader.py` (新建)
**严重性**: P1 - 配置无法加载
**状态**: ⏳ 待处理
**描述**: `system.yaml` 使用了 `${paths.logs}` 等模板变量，但代码中没有实现变量替换功能。

**修复步骤**:
1. 创建 `framework/core/config_loader.py`
2. 实现模板变量解析器，支持：
   - 环境变量替换：`${env:VAR_NAME}`
   - 路径变量替换：`${paths.xxx}`
   - 相对路径解析
3. 修改 `permissions.py` 使用新的配置加载器
4. 更新 `system.yaml` 和 `default.yaml` 的变量定义

**验收标准**:
- [ ] 配置文件可以正确加载
- [ ] 模板变量正确解析
- [ ] 路径引用正确解析

---

#### 任务 1.3：移除路径硬编码
**文件**: `framework/core/spawner.py`, `framework/core/permissions.py`
**严重性**: P1 - 无法部署到其他环境
**状态**: ⏳ 待处理
**依赖**: 任务 1.2
**描述**: 多个文件中硬编码了绝对路径 `/home/afei/workspace/code/feida_zoo`

**修复步骤**:
1. 创建 `framework/configs/paths.yaml` 存放所有路径配置
2. 实现路径解析器，支持：
   - 从环境变量读取 `FEIDA_ZOO_HOME`
   - 从配置文件读取默认路径
   - 相对路径解析
3. 修改 `Spawner.__init__()` 使用配置化路径
4. 修改 `PermissionManager.__init__()` 使用配置化路径
5. 更新 `registry.json` 中的 workspace 字段使用相对路径或模板

**验收标准**:
- [ ] 代码中不再有硬编码的绝对路径
- [ ] 可以通过环境变量配置根目录
- [ ] 部署到不同环境时只需修改配置

---

#### 任务 1.4：实现安全的删除机制
**文件**: `framework/core/spawner.py`
**严重性**: P1 - 数据永久丢失风险
**状态**: ⏳ 待处理
**描述**: `delete_member` 方法直接使用 `shutil.rmtree` 删除整个工作区，没有确认机制和备份功能。

**修复步骤**:
1. 创建 `framework/core/workspace_manager.py` 实现工作区管理
2. 实现软删除机制：
   - 添加 `deleted_members` 目录
   - 删除时移动到回收站而不是直接删除
   - 记录删除时间和原因
3. 添加恢复功能 `restore_member()`
4. 添加永久删除功能 `permanent_delete_member()` (需要二次确认)
5. 更新 `delete_member()` 调用新的安全删除机制

**验收标准**:
- [ ] 删除的成员工作区移动到回收站
- [ ] 可以从回收站恢复
- [ ] 永久删除需要二次确认
- [ ] 记录删除操作日志

---

#### 任务 1.5：重构架构 - 分离关注点
**文件**: `framework/core/`
**严重性**: P1 - 违反单一职责原则
**状态**: ⏳ 待处理
**依赖**: 任务 1.3, 任务 1.4
**描述**: `Spawner` 和 `PermissionManager` 类职责过多，违反 SOLID 原则。

**修复步骤**:
1. 创建 `framework/core/registry_manager.py` 专门处理注册表操作
2. 创建 `framework/core/workspace_manager.py` 专门管理工作区
3. 重构 `Spawner` 类：
   - 只保留成员创建和生命周期管理
   - 注册表操作委托给 `RegistryManager`
   - 工作区管理委托给 `WorkspaceManager`
4. 重构 `PermissionManager` 类：
   - 只保留权限检查逻辑
   - 权限授予/撤销委托给单独的方法
   - 日志记录委托给 `Logger` 组件

**验收标准**:
- [ ] 每个类职责单一，符合单一职责原则
- [ ] 代码可测试性提升
- [ ] 保持原有功能不变

---

### 📊 进度统计

| 状态 | 数量 |
|------|------|
| 待处理 | 5 |
| 进行中 | 0 |
| 已完成 | 0 |
| 已验收 | 0 |

---

## 🎯 总体进度

**完成度**: 0% (0/5 任务完成)
**预计工时**: 4-6 小时
**目标完成时间**: 2026-04-05

---

## 📝 备注

- 所有修复任务必须遵守动物园核心守则
- 修复完成后需要提交给毒刺进行🦂二次审计
- 二次审计通过后方可合入主分支

---

**文档版本**: v1.0
**最后更新**: 2026-04-05 00:20 GMT+8
