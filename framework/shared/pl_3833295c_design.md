# 设计文档：动物园成员信息配置化（v2 — 审查修复版）

**Pipeline ID:** pl_3833295c
**Design phase:** 2026-05-21 (v2, after review REJECT)
**Author:** Alpha (🐢)

---

## 1. What — 具体改动

### 核心目标
将动物园成员信息从 **5+ 个分散的硬编码数据源** 统一收敛到 **`zoo_members.yaml` 单一权威源**，所有运行时组件从此 YAML 文件读取，不再持有硬编码数据。

### 涉及的数据源（清理清单）

| # | 当前数据源 | 位置 | 改造后角色 |
|---|-----------|------|-----------|
| 1 | `zoo_members.yaml` | `framework/data/zoo_members.yaml` | ✅ **唯一权威源** |
| 2 | `ZooRegistry._DEFAULT_LABEL_MAP` | `framework/core/mesh/zoo_registry.py` | ❌ 删除，改为 YAML 加载 |
| 3 | `zoo_registry.json` | `framework/shared/zoo_registry.json` | ❌ 删除 |
| 4 | `registry.json` | `framework/data/registry.json` | ❌ 删除 |
| 5 | `MEMBERS_INFO` | `dashboard/app_enhanced.py` | ❌ 删除，改为 YAML 驱动 |
| 6 | `PHASE_DEFAULT_AGENT` | `zoo_mesh_daemon.py` | ❌ 删除，改为 `ZooRegistry.get_phase_agent()` |
| 7 | `openclaw.json agents.list` | `~/.openclaw/openclaw.json` | 🟡 保留；ZooRegistry 读取做模型验证 + 主 Agent 展示 |

### 审查修复对照

| v1 问题 | 修复方案 |
|---------|---------|
| 🔴 SessionRouter 被遗漏 | §4.4 补充 SessionRouter 改造 + label 生成规则 |
| 🔴 PHASE_DEFAULT_AGENT 删除不完整 | §5 补充 _phase_assignee() / _pick_phase_agent() 替换方案 |
| 🟡 zoo_registry.json ↔ InboxWatcher | §5.4 InboxWatcher 改用目录扫描 |
| 🟡 Dashboard registry.json + MEMBERS_INFO | §5.5 StatusManager 改用 ZooRegistry + 保留 YAML 驱动 fallback |
| 🟡 Self-contradiction fallback_map | §4.3 明确 fallback_map 硬编码不变 |
| 🟢 Label 生成规则缺失 | §4.4 label = <id>-zoomesh |
| 🟢 register_defaults() 语义 | §4.1 改为 YAML 自动加载 |

---

## 2. Why — 背景与动机

### 当前痛点

1. **成员数据漂移**：同一条信息在 5+ 位置重复定义，已出现不一致（Duci model: ZooRegistry 写 `glm-5.1`，openclaw.json 写 `minimax/MiniMax-M2.7`）
2. **Dashboard 成员残缺**：`MEMBERS_INFO` 只定义 3 个 Agent，新增成员必须同时改 4 处代码
3. **Pipeline 路由硬编码**：阶段→Agent 映射埋在 daemon 代码里，改路由必须重启 daemon
4. **InboxWatcher 配置依赖**：依赖 `zoo_registry.json` 才知道监控谁 → 删除后空转
5. **配置操作不透明**：改一个字段需要打开多个文件复制粘贴

### 设计原则

- **单一权威源**：所有成员信息仅保存在 `zoo_members.yaml`
- **运行时读取，不编译硬编码**：所有消费方在初始化时读取 YAML
- **向下兼容**：Dashboard API 响应格式不变；ZooRegistry 接口签名不变
- **自发现**：InboxWatcher 不依赖配置，直接扫描文件系统

---

## 3. Tradeoff — 权衡

| 方案 | 状态 | 放弃原因 |
|------|------|---------|
| 全量 JSON 化 | ❌ 放弃 | YAML 支持注释，更适合协作 |
| openclaw.json 驱动 | ❌ 放弃 | 缺少动物园特有字段（responsible_phases 等） |
| 数据库化 | ❌ 放弃 | 成员 ≤10，YAML + Git 足够 |
| **YAML 单一源 + 运行时缓存** | ✅ **采纳** | ~100字节，<1ms 加载 |

---

## 4. 接口定义

### 4.1 ZooRegistry — YAML 驱动改造

```python
class ZooRegistry:
    """成员注册表 — 从 zoo_members.yaml + openclaw.json 双源加载。
    
    构造时自动加载 YAML；register() 在 YAML 模式下仍可调用
    （动态更新内存数据），但不会写回文件。
    管理建议：直接编辑 zoo_members.yaml 后重启 daemon 即可。
    """
    
    def __init__(self, yaml_path: Optional[str] = None,
                 openclaw_path: Optional[str] = None):
        """自动推断默认路径：
        - yaml_path: framework/data/zoo_members.yaml
        - openclaw_path: ~/.openclaw/openclaw.json（不存在也不报错）
        """
        # 自动加载 YAML 到 self._agents（替代 _DEFAULT_LABEL_MAP）
    
    def reload(self) -> None:
        """重新加载 YAML。文件损坏 → 保留旧数据 + 打印错误日志。"""
    
    # ✅ 向下兼容（签名不变，行为语义微调）
    def register(self, agent_id, label=None, model=None) -> None:
        """YAML 模式下仍可动态注册（临时覆盖内存数据）。"""
    
    def get_info(self, agent_id) -> dict | None:
        """返回 {label, model}（向下兼容）。"""
    
    def get_label(self, agent_id) -> str | None:
        """返回 label。从 session.key 推导。
        规则：agent:<id>:main  →  <id>-zoomesh
        例：agent:alpha:main  →  alpha-zoomesh
        
        ZooRegistry 支持 label 独立配置，如果 YAML 有 label 字段优先取用。
        """
    
    def list_agents(self) -> list:
        """返回所有 YAML 中定义的 agent_id。"""
    
    # ✅ 新增方法
    def get_full_info(self, agent_id) -> dict | None:
        """返回 YAML 中全部字段。"""
    
    def get_responsible_phases(self, agent_id) -> list:
        """获取成员负责的阶段列表。"""
    
    def get_phase_agent(self, phase: str) -> str | None:
        """根据阶段名反向查询 Agent。
        冲突规则（多人负责同阶段）：
        1. 排除 is_main_agent==True 的主 Agent（全局调度者不参与执行）
        2. 按 zoo_members.yaml 定义顺序返回第一个
        3. 若无匹配 → 返回 'panda'（全局 fallback）
        """
    
    def get_model_display(self, agent_id) -> str:
        """Dashboard 展示用模型名。
        - 非主 Agent: zoo_members.yaml 的 model 字段，查 openclaw.json 转 alias
        - 主 Agent (is_main_agent==true): openclaw.json defaults.model.primary → alias
        - openclaw.json 不可读 → 返回原始 model ID 字符串
        """
```

### 4.2 Dashboard API 响应（向下兼容）

```json
{
  "id": "alpha",
  "name": "阿尔法 Alpha",
  "code_name": "Alpha",
  "role_display": "首席架构师",
  "species": "玄龟",
  "avatar": "/static/avatars/alpha.png",
  "avatar_emoji": "🐢",
  "status": "online",
  "model": "DeepSeek V4 Flash",
  "description": "首席架构师 · 玄龟",
  "session_key": "agent:alpha:main"
}
```

**字段映射（旧→新）**：

| 旧来源 | 新来源 |
|--------|--------|
| `MEMBERS_INFO["alpha"]["name"]` | `zoo_members.yaml.members.alpha.name` + `code_name` 拼接 |
| `MEMBERS_INFO["alpha"]["role"]` | `zoo_members.yaml.members.alpha.display_name` |
| `MEMBERS_INFO["alpha"]["species"]` | `zoo_members.yaml.members.alpha.species` |
| `MEMBERS_INFO["alpha"]["emoji"]` | `zoo_members.yaml.members.alpha.emoji` |
| `ZooRegistry.get_info(model)` | `ZooRegistry.get_model_display()` |
| 无 | `zoo_members.yaml.members.alpha.session.key`（新增） |

### 4.3 PHASE_DEFAULT_AGENT 替换方案（修复自相矛盾）

**明确决定**：
- **阶段→Agent 映射**：从 `zoo_members.yaml` 各成员 `responsible_phases` 反向推导（动态）
- **Pipeline 回退逻辑（fallback_map）**：**保持硬编码**。回退是 Pipeline 工作流规则，不是成员属性，不应放在 YAML 中

`zoo_mesh_daemon.py` 中涉及的 3 处代码改动：

```python
# 第 1 处（约 line 53-68）：**删除** PHASE_DEFAULT_AGENT 整体 dict
# ← 不需要替换，因为引入 self.registry.get_phase_agent()

# 第 2 处（约 line 556）：_phase_assignee()
# 旧:
#   return PHASE_DEFAULT_AGENT.get(phase, "panda")
# 新:
#   from core.mesh.zoo_registry import ZooRegistry
#   return ZooRegistry().get_phase_agent(phase) or "panda"

# 第 3 处（约 line 561）：_pick_phase_agent()
# 旧:
#   return PHASE_DEFAULT_AGENT.get(phase, "panda")
# 新:
#   return ZooRegistry().get_phase_agent(phase) or "panda"
```

**兼容处理**：`PHASE_DEFAULT_AGENT` 中的旧兼容键 `"develop": "develop_wt"` 不再属于 `get_phase_agent()` 的职责。`develop` 阶段已在 `PHASES` 列表中移除（不存在于合法阶段列表中），旧数据会在 `requirements.json` 迁移阶段自动转为 `develop_wt`。此兼容键在删除前已无实际用途。

### 4.4 SessionRouter 改造方案

```python
class SessionRouter:
    """分阶段 Session 路由器。
    
    改造后 label 从 session.key 推导，不再依赖 _DEFAULT_LABEL_MAP。
    """
    
    def resolve(self, agent_id: str) -> Optional[str]:
        """解析 agent_id 到可路由标识。
        
        - phase1/phase2: 返回缓存的 session_key
        - phase3+: 返回 ZooRegistry.get_label(agent_id)
        
        改造前后返回值对比：
        - 改造前: get_label("alpha") → "alpha-zoomesh"
        - 改造后: get_label("alpha") → "alpha-zoomesh"（基于 session.key → <id>-zoomesh 规则）
        ✅ 返回值完全一致，Phase 3+ 路由不受影响
        """
        if self.phase in ("phase1", "phase2"):
            return self._cache.get(agent_id)
        registry = ZooRegistry()
        return registry.get_label(agent_id)
    
    # connect() / set_cache() 接口不变
```

**Label 生成规则（ZooRegistry 内部实现）**：

```
输入: session.key = "agent:alpha:main"
  1. 解析格式: agent:<id>:main
  2. 提取 id: "alpha"
  3. 拼接: "alpha-zoomesh"
输出: "alpha-zoomesh"  ← 与现有值完全一致

特例: 如果 YAML 中配置了独立的 label 字段，直接使用该值（不推导）
```

这样做的好处：
- 现有 Phase 3+ 的所有 Label 路由不受影响
- session.key 改了，label 自动跟随（无需手动同步）
- 兼容 YAML 中独立 label 字段

---

## 5. 文件清单

### 5.1 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `framework/core/mesh/zoo_registry.py` | 重写为 YAML 驱动；删除 `_DEFAULT_LABEL_MAP`；新增 `get_full_info()` / `get_phase_agent()` / `get_model_display()`；`get_label()` 改为 session.key 推导 |
| `framework/core/mesh/zoo_mesh.py` | `register_defaults()` 调用由 ZooMesh.init() 改为 YAML 自动加载（可删除 `register_defaults()` 调用，因为构造时已加载） |
| `framework/core/mesh/inbox_watcher.py` | **删除** `registry_path` 参数；`_run()` 改为扫描 `mesh_dir/*/queue` 发现 agent，而非从 JSON 文件读取列表 |
| `framework/data/zoo_members.yaml` | 确认 duci model 改为 `minimax/MiniMax-M2.7`；status 字段统一为小写 |
| `dashboard/app_enhanced.py` | **MEMBERS_INFO**: 删除硬编码，数据来源切换为 `ZooRegistry.get_full_info()`；**StatusManager**: 成员遍历改为 `ZooRegistry.list_agents()` 而非 `registry.json`；**`: 保证 ZooRegistry 不可用时仍有从 YAML 现场读取的 fallback |
| `framework/core/mesh/zoo_mesh_daemon.py` | 删除 `PHASE_DEFAULT_AGENT` dict；`_phase_assignee()` / `_pick_phase_agent()` 改为 `ZooRegistry().get_phase_agent(phase)`；`_dispatch_pending_agents()` 中 `zoo_registry.json` 读取改为 `ZooRegistry.list_agents()`；Main 中 InboxWatcher 构造移除 `registry_path` 参数 |

### 5.2 删除的文件

| 文件 | 原因 | 安全确认 |
|------|------|---------|
| `framework/shared/zoo_registry.json` | 内容已覆盖 | 仅 InboxWatcher + _dispatch_pending_agents 使用（均改造） |
| `framework/data/registry.json` | 老旧，路径过期 | 仅 Dashboard StatusManager 使用（已改造） |

### 5.3 新增文件

| 文件 | 内容 |
|------|------|
| `framework/tests/test_zoo_registry_v2.py` | 测试 YAML 加载、label 推导、get_phase_agent()、get_model_display() |

### 5.4 InboxWatcher 改造细节

```python
class InboxWatcher:
    def __init__(self, mesh_dir: str, on_wakeup=None):
        """不再需要 registry_path 参数。
        
        mesh_dir: 例如 <mesh>/inbound，包含各个 agent 的 inbox 目录
        """
    
    def _run(self) -> None:
        """不再从文件读取 agent 列表。
        
        改为扫描 mesh_dir 下的子目录（每个子目录名 = agent_id），
        目录下有 queue/ 子目录即视为有效 agent。
        这样删除 zoo_registry.json 后 InboxWatcher 仍能自发现。
        """
        # 旧:
        #   with open(self.registry_path) as f:
        #       registry = json.load(f)
        #   agent_ids = list(registry.get("agents", {}).keys())
        
        # 新:
        #   agent_ids = [d.name for d in mesh_dir.iterdir()
        #                if (mesh_dir / d.name / "queue").is_dir()]
```

### 5.5 Dashboard StatusManager 改造细节

```python
class StatusManager:
    def __init__(self, registry_path: Path, agents_dir: Path):
        # registry_path 参数保留（为兼容构造签名），但内部不再使用
        
    def update_all(self) -> None:
        """遍历成员改为使用 ZooRegistry.list_agents()。"""
        # 旧:
        #   with open(self.registry_path) as f:
        #       registry = json.load(f)
        #   for member_id in registry.get("members", {}):
        
        # 新:
        #   from core.mesh.zoo_registry import ZooRegistry
        #   registry = ZooRegistry()
        #   for member_id in registry.list_agents():
```

Dashboard `_get_member_data()` 的双层防御保留：

```python
def _get_member_data(self):
    # 第一层: ZooRegistry（YAML 驱动）
    try:
        registry = ZooRegistry()
        ...  # 从 registry.get_full_info() 读取
    except Exception as e:
        # 第二层: 直接读取 YAML 文件 fallback
        # 而非硬编码 MEMBERS_INFO
        try:
            import yaml
            with open("framework/data/zoo_members.yaml") as f:
                members = yaml.safe_load(f)["members"]
            ...
        except Exception:
            return []  # 两层都失败才返回空
```

---

## 6. Open Questions

| # | 问题 | 决策 |
|---|------|------|
| Q1 | Duci model: ZooRegistry 写 `glm-5.1` 但 openclaw.json 配 `minimax/MiniMax-M2.7` | → 统一为 `minimax/MiniMax-M2.7`（与 openclaw.json 一致） |
| Q2 | 主 Agent 模型展示：panda 无独立 model，走 defaults 的 primary (volcengine-plan/glm-5.1) → 转 alias 为... 空（无 alias 配置） | → 取 `defaults.models` 中第一个 alias 非空的模型（`minimax/MiniMax-M2.7` → "Minimax"） |
| Q3 | YAML 加载失败时 ZooRegistry 的行为 | → 构造函数抛出异常（fail-fast）；`reload()` 保持旧数据 |
| Q4 | Dashboard 原有 `_get_member_species()` 从 IDENTITY.md 读取，新逻辑以 YAML 为准 | → YAML 的 `species` 是权威；删除 IDENTITY.md fallback |
| Q5 | `zoo_members.yaml` 中 weaver/aeterna/gulu 的 status 为 `inactive`，Dashboard 是否隐藏？ | → 否，仍然显示但标记为"非活跃"。是否显示由前端看板决定 |
| Q6 | InboxWatcher 目录扫描发现新 agent 后是否动态更新监控列表？ | → 是，每次轮询都重新扫描目录列表 |

---

## 7. Next Action — 希望审查方重点审查

### 🔴 必须审查

1. **label 生成规则**
   - `agent:<id>:main` → `<id>-zoomesh` 是否与现有 label 值完全一致？（alpha→alpha-zoomesh ✅）
   - 成员变更 session.key 后 label 自动跟随，是否会产生不可预期的下游影响？

2. **`get_phase_agent()` 的并发安全**
   - daemon 中 `_phase_assignee()` 和 `_pick_phase_agent()` 在多个线程中调用
   - ZooRegistry 单例读取 YAML 是否线程安全？（建议：YAML 读一次后缓存，只读访问不需要锁）

3. **InboxWatcher 目录扫描方案**
   - 当前 InboxWatcher 每 2 秒轮询所有 agent inbox
   - 目录扫描版本在 agent 数量增加时开销是否可接受？（O(n) 目录遍历 + stat，n ≤ 10）

4. **Dashboard fallback 有效性**
   - 从 YAML 直接读取作为 fallback，确实不依赖 ZooRegistry 初始化
   - 但读取路径是相对路径还是绝对路径？建议用 `PROJECT_ROOT / "framework/data/zoo_members.yaml"`

### 🟡 建议审查

5. **`PHASE_DEFAULT_AGENT` 删除后，develop 兼容键丢失的影响**
   - 旧 requirements.json 中 `status: "develop"` 的数据已在 `_load_requirements()` 的自动迁移中转为 `develop_wt`
   - 确认凌晨运行的旧数据不会因 dict 删除而报 KeyError
