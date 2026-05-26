# 审查报告：pl_3833295c — 动物园成员信息配置化（v2）

**Pipeline ID:** pl_3833295c
**Review phase:** 2026-05-21 23:37
**Reviewer:** Duci 🦂
**Design version:** v2（审查修复版）
**Input:** pl_3833295c_design.md
**Output:** pl_3833295c_review.md

---

## 审查总览

v2 设计相比 v1 有**显著改进**：SessionRouter 被纳入、PHASE_DEFAULT_AGENT 删除方案完整、InboxWatcher 改为目录扫描、StatusManager 改为 ZooRegistry、所有 Open Questions 均给出明确决策。

设计方向正确，**核心架构无本质缺陷**。

但仍存在 **3 处细节遗漏**，可能导致实现阶段卡住：

| # | 严重程度 | 问题 |
|---|---------|------|
| 1 | 🟡 **重要** | Dashboard `StatusManager` 签名不兼容：构造参数 `registry_path: Path` 保留但内部不再使用，调用方传参存在性未说明 |
| 2 | 🟡 **重要** | Dashboard `_get_member_data()` 的 YAML fallback 读取路径未明确（相对 vs 绝对） |
| 3 | 🟢 **次要** | `zoo_mesh.py:72` 调用 `register_defaults()` 的处理方案与 §4.1 描述不一致 |

**结论：pass（附 3 项实现建议）**

---

## 1. 架构合理性 ✅

### 1.1 核心架构 ✅

单一权威源设计正确。YAML 双源（zoo_members.yaml + openclaw.json）分工清晰：
- `zoo_members.yaml`：成员属性、session key、responsible_phases（权威源）
- `openclaw.json`：模型别名解析、主 Agent 模型展示（只读引用）

### 1.2 label 生成规则 ✅

规则 `agent:<id>:main → <id>-zoomesh` 与现有值完全一致，Phase 3+ 路由不受影响。

关键验证：
- `agent:alpha:main` → `alpha-zoomesh` ✅（现有值）
- `agent:duci:main` → `duci-zoomesh` ✅（现有值）
- `agent:panda:main` → `panda-zoomesh` ✅（现有值）

YAML 中可选 `label` 字段作为独立覆盖，兼容未来扩展。

### 1.3 `get_phase_agent()` 设计 ✅

冲突解决规则（排除主 Agent → 按定义顺序 → fallback to "panda"）清晰合理。

需注意：`panda` 的 `responsible_phases` 包含 `request/final_check/deliver`，这些阶段的派发会优先选 panda（因为它是唯一非主 Agent 的候选人），这符合"全局调度者不参与执行"的原则。

### 1.4 InboxWatcher 目录扫描 ✅

自发现机制比维护文件列表更健壮。O(n) 目录遍历（n ≤ 10），2 秒轮询间隔无性能问题。

---

## 2. 安全风险 ✅

无新增安全风险。

- Token 鉴权问题未改变（原地踏步），但 ZooMesh 监听 `127.0.0.1:18793`，本地端口复用场景风险可控
- YAML 文件只读，不含敏感凭证
- `openclaw.json` 只读引用，不写入

---

## 3. 遗漏检查

### 3.1 🟡 Dashboard `StatusManager` 构造签名不兼容

**设计描述**（§5.5）：
```python
class StatusManager:
    def __init__(self, registry_path: Path, agents_dir: Path):
        # registry_path 参数保留（为兼容构造签名），但内部不再使用
```

**实际问题**：调用方 `app_enhanced.py:440`：
```python
status_manager = MemberStatusManager(REGISTRY_PATH, AGENTS_DIR)
```

其中 `REGISTRY_PATH = PROJECT_ROOT / "framework" / "data" / "registry.json"`。

设计说要删除 `registry.json`，但调用方依然传 `registry.json` 路径。如果 `StatusManager` 内部不再使用该参数而直接用 ZooRegistry，那传什么路径都可以。但这里存在隐含依赖：

- 如果 `StatusManager.__init__` 验证 `registry_path` 存在性（如父类或装饰器），删除文件后启动即崩
- 如果 `StatusManager` 内部完全不检查 `registry_path`，那这个参数就是死参数，应该从签名中移除

**建议**：明确 `StatusManager` 的 `registry_path` 参数是否保留。若保留，文档说明"传任意路径均可，参数被忽略"；若移除，同步修改 `app_enhanced.py:440` 的调用方式。

### 3.2 🟡 Dashboard `_get_member_data()` YAML fallback 路径未明确

**设计描述**（§5.5）：
```python
# 新:
try:
    import yaml
    with open("framework/data/zoo_members.yaml") as f:  # ← 相对路径
        members = yaml.safe_load(f)["members"]
```

**问题**：`open()` 使用相对路径 `"framework/data/zoo_members.yaml"`。

Dashboard 运行时的 cwd（当前工作目录）不确定。实际部署中 cwd 可能是：
- `/Users/zoo/workspace/code/feida_zoo/dashboard`（从 dashboard 目录运行）
- `/Users/zoo/workspace/code/feida_zoo`（从项目根运行）
- `/Users/zoo/workspace/members/panda`（从 panda 目录运行）

不同 cwd 下同一相对路径解析到不同文件，导致 fallback 失效。

**建议**：fallback 路径用绝对路径：
```python
from pathlib import Path
YAML_FALLBACK_PATH = Path(__file__).parent.parent / "framework" / "data" / "zoo_members.yaml"
# 或者用 PROJECT_ROOT：
YAML_FALLBACK_PATH = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
```

### 3.3 🟢 `register_defaults()` 处理方案与描述不一致

**设计 §4.1**：
> ZooMesh.init() 调用由 ZooMesh.init() 改为 YAML 自动加载（**可删除** `register_defaults()` 调用，因为构造时已加载）

**设计 §5.1 文件清单**：
> `framework/core/mesh/zoo_mesh.py` - `register_defaults()` 调用由 ZooMesh.init() 改为 YAML 自动加载（可删除 `register_defaults()` 调用，因为构造时已加载）

**实际 `zoo_mesh.py:72`**：
```python
self._registry.register_defaults()
```

设计说"可删除"，但没有明确说"删除了"，也没有说"保留但行为改变"。

如果 ZooRegistry 构造时自动加载 YAML，则 `register_defaults()` 成为空操作（或抛出）。建议在§4.1 或§5.1 中明确说明：是删除调用语句，还是保留调用但其内部改为加载 YAML（`self.reload()`）。

---

## 4. 改进建议

### 4.1 （已采纳，验证有效性）label 生成覆盖

设计 §4.4 提到"如果 YAML 中配置了独立的 label 字段，直接使用该值（不推导）"。

建议 ZooRegistry 实现时优先检查 YAML 的 `label` 字段：
```python
def get_label(self, agent_id) -> str | None:
    info = self._agents.get(agent_id)
    if not info:
        return None
    # 优先用 YAML 中配置的 label
    if "label" in info:
        return info["label"]
    # 其次从 session.key 推导
    session_key = info.get("session", {}).get("key", "")
    if session_key.startswith("agent:"):
        parts = session_key.split(":")
        if len(parts) >= 2:
            return f"{parts[1]}-zoomesh"
    return None
```

### 4.2 daemon 线程安全确认

`ZooRegistry` 单例在 daemon 多线程环境中被 `_phase_assignee()` 和 `_pick_phase_agent()` 并发调用。YAML 加载后 `self._agents` 为只读字典（不再修改），线程安全无问题。

但如果 `register()` 在 YAML 模式下仍可调用（§4.1 描述），则存在写竞争。建议明确：YAML 模式下 `register()` 是否仍然开放？如果不开放，直接在 `register()` 开头加 `if self._yaml_loaded: raise RuntimeError(...)`。

### 4.3 实现顺序建议

建议按以下顺序实现，便于提前发现衔接问题：
1. `ZooRegistry` YAML 加载（核心）
2. `get_phase_agent()` / `get_label()` / `get_model_display()` 实现
3. `inbox_watcher.py` 删除 registry_path + 目录扫描
4. `dashboard/app_enhanced.py` StatusManager + _get_member_data() fallback
5. `zoo_mesh_daemon.py` 删除 PHASE_DEFAULT_AGENT + 3 处替换
6. 删除 `zoo_registry.json` 和 `registry.json`

---

## 5. 结论

| 维度 | 评分 |
|------|------|
| 核心理念 | ✅ 正确且必要 |
| v1 阻塞项修复 | ✅ 全部覆盖 |
| 架构完整性 | ✅ 细节充分，接口清晰 |
| 向后兼容性 | ✅ 接口签名不变，label 路由兼容 |
| 可实现性 | ✅ 仅 3 处次要遗漏，不阻断开发 |
| 文档清晰度 | ✅ Open Questions 全部关闭，决策明确 |

### 决定：**PASS**

### 实现前需同步明确（不影响 PASS）

1. `StatusManager` 的 `registry_path` 参数是否从签名中移除；如保留，明确参数被忽略
2. `_get_member_data()` fallback 路径用绝对路径（`PROJECT_ROOT / "framework/data/zoo_members.yaml"`）
3. `register_defaults()` 调用是删除还是保留改造（建议删除，ZooRegistry 构造时自动加载）

### 不影响 PASS 的次要项

4. 确认 `register()` 在 YAML 模式下是否仍然开放（线程安全边界）
5. `inbox_watcher.py` 目录扫描时是否忽略隐藏目录（如 `.` / `..` / `.git`）

---

**Reviewer:** Duci 🦂
**Timestamp:** 2026-05-21 23:50 GMT+8
**Result:** pass