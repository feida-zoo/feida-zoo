# Test Review Report — pl_2070b427

**Task**: 成员管理界面人数不对  
**Requirement**: 6587c35b-17d0-4361-bae4-5e04ecea31fa  
**Reviewer**: Duci (🦂)  
**Date**: 2026-05-26  
**Input**: `framework/tests/ut/test_member_active_filter.py`

---

## 覆盖度：✅ 良好

| 测试场景 | 覆盖 |
|---------|------|
| ZooRegistry.list_agents() 返回全量 6 人 | ✅ |
| get_full_info() 含 metadata.status 字段 | ✅ |
| active 成员全部保留（panda/alpha/duci） | ✅ |
| inactive 成员全部排除（weaver/aeterna/gulu） | ✅ |
| 精确数量验证（== 3） | ✅ |
| YAML fallback 路径同等的 status 过滤 | ✅ |
| 缺少 status 字段默认 active（不过滤） | ✅ |
| 全部 inactive 返回空列表 | ✅ |
| 空 members 边界 | ✅ |
| MemberStatusManager 不追踪 inactive | ✅ |
| ZooRegistry + 过滤 集成流程 | ✅ |
| 双路一致性（ZooRegistry vs YAML） | ✅ |

**统计**：13 个测试用例，覆盖 7 个类（TestZooRegistryListAgents、TestGetActiveMembersFilter、TestBoundaryCases、TestMemberStatusManagerScope、TestIntegratedFilterWithZooRegistry）。

---

## 边界用例：✅ 充分

- **无 status 字段**：默认 active，不过滤 — 防止新增成员被误杀
- **全部 inactive**：返回空列表 — 防止所有成员退出时的异常行为
- **空 members**：返回空列表 — 防御性验证

---

## 关键缺陷（必须指出）

### 🔴 Issue 1：测试模拟函数，而非真实实现

**问题**：测试文件定义了 `simulated_get_active_members()` 和 `simulated_yaml_fallback()` 两个**模拟函数**，而不是直接测试 `app_enhanced.py` 中真实的 `_get_member_data()` 方法。

这意味着测试通过不代表真实代码正确。模拟函数是人手写的，和实际实现可能不一致。

**验证方法**：直接 import 并调用 `DashboardHandler._get_member_data()`（需要实例化 `MemberStatusManager`），或通过 MonkeyPatch 替换。

### 🔴 Issue 2：fallback 路径与主路径实际行为未被同时验证

**问题**：当前测试验证了"fallback 路径的**模拟函数**与 ZooRegistry 的**模拟函数**产生相同结果"，但没有测试以下场景：
- ZooRegistry 抛出异常时，真实的 fallback 路径是否正确执行
- fallback 中是否同样有 status 过滤（review 阶段指出的 Issue 1）

**需要在真实代码中验证**：当 `ZooRegistry()` 初始化失败或 `list_agents()` 抛异常时，fallback 路径的 for 循环是否包含 `status == "active"` 检查。

### 🟡 Issue 3：无法实际运行（pytest 不可用）

**问题**：测试环境没有安装 pytest（`python3 -m pytest` → `No module named pytest`）。测试文件的运行条件不满足。

**建议**：在测试文件顶部加一行检查，或提供安装 pytest 的说明：
```bash
pip install pytest pytest-timeout
```

---

## 改进建议

### 必须补充

1. **直接测试 `_get_member_data()` 真实方法**（不模拟）
   
   ```python
   def test_real_get_member_data_filters_inactive(temp_yaml_path, monkeypatch):
       # 将 ZooRegistry 替换为使用临时 YAML 的实例
       from framework.core.mesh.zoo_registry import ZooRegistry
       original_init = ZooRegistry.__init__
       def patched_init(self, yaml_path=None):
           original_init(self, yaml_path=temp_yaml_path)
       monkeypatch.setattr(ZooRegistry, '__init__', patched_init)
       
       # 实例化 handler 并调用真实方法
       # ... 验证返回的成员数量 == 3
   ```

2. **模拟 ZooRegistry 异常，验证 fallback 真实行为**
   
   ```python
   def test_fallback_path_also_filters(monkeypatch):
       import pytest
       from framework.core.mesh.zoo_registry import ZooRegistry
       
       def failing_list_agents(self):
           raise RuntimeError("ZooRegistry unavailable")
       monkeypatch.setattr(ZooRegistry, 'list_agents', failing_list_agents)
       
       # 调用 _get_member_data()，期望 fallback 路径仍过滤 inactive
       # 验证返回 len == 3
   ```

### 建议补充

3. **API 端到端测试**：启动 Dashboard，用 `requests` 调用 `GET /api/members`，验证返回 `len == 3` 且无 inactive 成员
4. **并发场景**：多线程同时调用 `_get_member_data()`，验证结果一致性（成员数据只读，无锁要求）

---

## 结论：**reject**

**Reject 原因**：测试文件存在结构性缺陷——使用模拟函数而非真实实现，导致测试通过不代表真实代码正确。核心问题（Issue 1 + Issue 2）无法被当前测试套件验证。

**修复要求**：
1. 新增至少 2 个用例直接测试 `app_enhanced.py` 中真实的 `_get_member_data()` 方法（含 MonkeyPatch 隔离）
2. 新增 ZooRegistry 异常的 fallback 路径测试，验证 fallback 中同样有 status 过滤
3. 解决 pytest 依赖问题（提供安装说明或改用 unittest）

---

## 审查摘要

| 检查项 | 结论 |
|--------|------|
| 覆盖度 | ✅ 良好（13 用例，7 类） |
| 边界用例 | ✅ 充分 |
| 模拟 vs 真实 | 🔴 使用模拟函数，无法验证真实代码 |
| Fallback 路径验证 | 🔴 未测试 ZooRegistry 异常场景 |
| 可运行性 | 🟡 pytest 未安装 |
| 最终结论 | **reject**（修复 Issue 1+2 后重审） |
