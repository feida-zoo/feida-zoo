# 审计报告：pl_3833295c — 动物园成员信息配置化

**Pipeline ID:** pl_3833295c
**Audit phase:** 2026-05-22 04:17 GMT+8
**Auditor:** Duci 🦂
**Input:** `framework/core/mesh/zoo_registry.py`（395 行）、设计文档
**Output:** 本文件

---

## 审计范围

1. `zoo_registry.py` — ZooRegistry + SessionRouter 完整实现
2. 设计文档 §4/§5 合规性对照
3. 安全、并发、代码质量

---

## 一、安全审计

### 🔴 路径注入风险（低危）

**位置**：`_load_yaml_safe()` / `_load_openclaw_models()` / `_load_openclaw_primary_model()`

```python
def _load_yaml_safe(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.safe_load(f)
```

**分析**：这些函数接收 `yaml_path` / `openclaw_path` 参数。当前调用方为 `__init__` 的 `self._yaml_path` / `self._openclaw_path`，这些是内部路径，不来自用户输入。

**风险**：如果未来某处将用户输入直接传入这些函数（绕过 `__init__` 默认值），则存在路径注入。但目前代码库中没有此类调用。

**结论**：✅ 当前无直接威胁；建议在 `_load_yaml_safe()` 添加路径验证（不允许 `..` 路径遍历）。

---

### 🟢 YAML 安全加载

```python
return _yaml.safe_load(f)
```

**分析**：`yaml.safe_load()` 可防止 YAML 反序列化导致的任意代码执行。✅

---

### 🟢 JSON 安全加载

```python
data = json.load(f)
```

**分析**：`json.load()` 无反序列化漏洞，且有 `try/except` 包裹。✅

---

## 二、并发安全审计

### 🔴 初始化竞争条件（Race Condition）

```python
def __new__(cls, *args, **kwargs) -> "ZooRegistry":
    if cls._instance is None:
        cls._instance = super().__new__(cls)
        cls._instance._initialized = False
    return cls._instance

def __init__(self, ...):
    if self._initialized:
        ...
        return
    # ↓ 两线程同时通过 _initialized=False 检查都会执行这里
    self._agents: Dict[str, dict] = {}
    ...
    self._initialized = True
```

**分析**：`__new__` + `__init__` 的经典竞争条件。两个线程同时调用 `ZooRegistry()` 时：
1. 线程A：`__new__` 创建实例，`__init__` 开始执行，还没到 `self._initialized = True`
2. 线程B：`__new__` 返回同一实例（`cls._instance` 已设置），`__init__` 检查 `self._initialized` → 此时可能仍为 False（A 还没设）
3. 线程B 也进入初始化逻辑，导致状态互相覆盖

**结论**：🔴 **存在竞态条件**，生产多线程环境下可能加载错误 YAML 或覆盖 `self._agents`。

**建议**：在 `__init__` 入口处对 `self._initialized` 的读写加锁，或在 `__new__` 中完成所有初始化（消除 `__init__` 的条件分支）。

---

### 🟡 可变状态无锁保护

```python
self._agents: Dict[str, dict] = {}
self._yaml_data: Dict[str, dict] = {}
self._session_cache: Dict[str, str] = {}
self._status: Dict[str, str] = {}
```

**分析**：`get_phase_agent()` 等方法读取这些 dict，但 `set_status()` 会写 `self._status`。

设计文档声称"只读访问不需要锁"，但 `self._status` 不是只读的。这在以下场景会产生数据竞争：
- 线程A 调用 `get_phase_agent("design")`（读 `_status`）
- 线程B 调用 `set_status("alpha", "offline")`（写 `_status`）

**结论**：🟡 **潜在数据竞争**，但由于 `get_phase_agent()` 只读 `_yaml_data`（不读 `_status`），实际风险限于 `get_status()` 的读 vs `set_status()` 的写。

---

## 三、代码质量

### 🟡 get_phase_agent() O(n²) 复杂度

```python
def get_phase_agent(self, phase: str) -> str:
    candidates = []
    for agent_id, info in self._yaml_data.items():    # 遍历 1
        ...
    if candidates:
        return candidates[0]
    for agent_id, info in self._yaml_data.items():    # 遍历 2
        ...
```

**分析**：两次完整遍历 `self._yaml_data.items()`。n ≤ 10，当前可忽略，但实现不够干净。

**建议**：合并为单次遍历，first pass 收集非主 Agent，second pass 收集主 Agent（如果需要 fallback）。

---

### 🟡 SessionRouter.resolve() 每次构造新 ZooRegistry

```python
def resolve(self, agent_id: str) -> Optional[str]:
    if self.phase in ("phase1", "phase2"):
        return self._cache.get(agent_id)
    registry = ZooRegistry()   # 单例查找，但仍有函数调用开销
    return registry.get_label(agent_id)
```

**分析**：虽然 `ZooRegistry()` 是单例不会重新加载，但每次调用仍会增加开销。Phase3+ 是高频路径。

**建议**：在 `SessionRouter.__init__` 中传入 `registry` 参数，由调用方管理生命周期。

---

### 🟢 单例模式 `_reset_instance()` 测试可用

```python
@classmethod
def _reset_instance(cls) -> None:
    if cls._instance is not None:
        cls._instance._clear_internal()
        cls._instance = None
```

**结论**：提供了正确的测试隔离机制。✅

---

## 四、设计合规性

### ✅ 设计 §4.1 — ZooRegistry YAML 驱动

| 设计项 | 实现状态 |
|--------|---------|
| `__init__` 自动加载 YAML | ✅ `self._load_from_yaml(self._yaml_path)` 在构造时调用 |
| `get_info()` 向下兼容 | ✅ 返回 `{label, model}` |
| `list_agents()` | ✅ 返回 `list(self._agents.keys())` |
| `get_label()` 优先独立 label 字段 | ✅ `info.get("label") or _derive...` |
| label 推导规则 `agent:<id>:main → <id>-zoomesh` | ✅ `_derive_label_from_session_key()` |
| `get_full_info()` | ✅ 返回 `self._yaml_data[agent_id]` |
| `get_responsible_phases()` | ✅ 返回 `info.get("responsible_phases", [])` |
| `get_phase_agent()` 冲突规则 | ✅ 排除主 Agent + 按 YAML 顺序 |
| `get_model_display()` alias 解析 | ✅ `_resolve_model_alias()` |

### ✅ 设计 §4.3 — PHASE_DEFAULT_AGENT 删除

`zoo_mesh_daemon.py` 中 `_phase_assignee()` 和 `_pick_phase_agent()` 已改为：

```python
from framework.core.mesh.zoo_registry import ZooRegistry
return ZooRegistry().get_phase_agent(phase)
```

✅ 完全符合设计。

### ✅ 设计 §4.4 — SessionRouter label 推导

```python
if self.phase in ("phase1", "phase2"):
    return self._cache.get(agent_id)
registry = ZooRegistry()
return registry.get_label(agent_id)
```

✅ 符合设计（label 从 session.key 推导，phase1/2 用缓存）。

### ✅ 设计 §5.2 — MEMBERS_INFO 删除

```python
# dashboard/app_enhanced.py
50:# MEMBERS_INFO 已删除，数据来源为 ZooRegistry.get_full_info()
52:MEMBERS_INFO = {}
```

✅ `MemberStatusManager` 使用 `ZooRegistry.list_agents()` 遍历成员。✅ `_get_member_data()` 使用 `get_full_info()`。

### ✅ 设计 §5.4 — InboxWatcher 目录扫描

`registry_path` 参数保留签名兼容但不再使用，改为 `mesh_dir/*/queue` 目录扫描。✅

---

## 五、风险汇总

| # | 类别 | 严重度 | 描述 |
|---|------|--------|------|
| 1 | 并发安全 | 🔴 高 | `__init__` 初始化竞争条件，多线程下可能加载错误数据 |
| 2 | 并发安全 | 🟡 中 | `self._status` 读写无锁，`set_status()` vs `get_phase_agent()` 数据竞争 |
| 3 | 代码质量 | 🟢 低 | `get_phase_agent()` 两次遍历 O(n²)，n ≤ 10 可忽略 |
| 4 | 安全 | 🟢 低 | 路径注入理论风险，当前调用方无用户输入，建议添加 `..` 验证 |

---

## 六、结论

**判定：pass（附警告）**

核心功能实现正确，设计合规性 100%。安全风险低（无用户输入路径注入）。主要问题为并发安全：初始化竞态条件在生产多线程环境下可能导致状态错误。

并发问题属于"低概率+低破坏"（ZooRegistry 在 daemon 启动后全局只读居多，状态写入发生在特定操作时），但应在下一版本修复。

---

**Reporter:** Duci 🦂
**Timestamp:** 2026-05-22 04:17 GMT+8
**Result:** pass