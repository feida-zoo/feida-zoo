# 🏗️ 飝龘动物园 · P2P 架构 + Harness 化改造设计

> **作者**: 阿尔法（玄龟）🐢  
> **版本**: v1.0  
> **日期**: 2026-05-10  
> **状态**: 设计稿 · 待毒刺审核  
> **设计范围**: 两件事合为一次架构升级 —— P2P 通信网格 + 流程代码 Harness 化

---

## 一、现状痛点回顾

### 1.1 当前架构：Hub-and-Spoke

```
      园长 (飝龘龘)
           │
           ▼
     ┌──────────┐
     │  Panda   │ ← 所有消息在这里转发
     │ (转发器) │
     └────┬─────┘
           │
     ┌─────┼──────┬─────┬─────┐
     ▼     ▼      ▼     ▼     ▼
   Alpha Weaver  Duci Aeterna Gulu
```

### 1.2 问题清单

| # | 问题 | 当前状态 | 严重程度 |
|---|------|----------|----------|
| P1 | **Panda 主会话上下文爆炸** — 所有成员交互内容堆在 main session 里 | 已有 zillion 行背景 | 🔴 高 |
| P1 | **成员间无直接认知** — 不知道其他成员在做什么，全靠 Panda 转述 | 每次 spawn 是新生 | 🔴 高 |
| P1 | **Skill 流程依赖 LLM 理解** — YAML + SKILL.md 靠 LLM 解读，流程步骤可能丢失或跳过 | 典型的"强协议弱执行" | 🔴 高 |
| P2 | **mode="run" 用完即焚** — 每次唤醒都是"出生→干活→死亡"，没有持久身份 | 无法接收消息 | 🟡 中 |
| P2 | **串行阻塞** — 所有消息经 Panda 转发，天然串行 | 无法并行 | 🟡 中 |
| P3 | **知识零散** — 决策只在 SKILL.md 里，无程序化约束和审计 | 修复才留痕 | 🟢 低 |

---

## 二、目标架构全景

```
═══════════════════════════════════════════════════════
              飝龘动物园 V2 — 全面进化
═══════════════════════════════════════════════════════

                   园长 (飝龘龘)
                       │
                       │  (园长可直接 @ 任意成员)
                       ▼
                ┌──────────────┐
                │    Panda     │ ← 从转发器 → 协调员
                │ (Orchestrator│   → 任务派发 + 状态监控
                │  + 园长接口) │   → 不承载消息内容
                └──────┬───────┘
                       │
          ╔════════════╧════════════════════════╗
          ║        ZooMesh 共享知识总线          ║
          ║  ┌──────────────────────────────┐  ║
          ║  │  • Event Bus (文件级消息队列)  │  ║
          ║  │  • 共享目录 (交付物)           │  ║
          ║  │  • sessions_send (直连通道)    │  ║
          ║  │  • Knowledge Lake (永久归档)   │  ║
          ║  └──────────────────────────────┘  ║
          ╚════════════╤════════════════════════╝
                       │
              ┌────────┼────────┬────────┬────────┐
              ▼        ▼        ▼        ▼        ▼
           Alpha ──→ Weaver ──→ Duci ──→ Aeterna ──→ Gulu
            │         │         │         │          │
            │  ╔══════╧══════╗  │         │          │
            │  ║ sessions_send ║  │         │          │
            │  ╚══════╤══════╝  │         │          │
            └─────────┴─────────┴─────────┴──────────┘
              ↑ 所有成员之间可以直接对话 ↑

═══════════════════════════════════════════════════════
          Harness Engine（流程约束引擎）
═══════════════════════════════════════════════════════

  ┌──────────────────────────────────────────────────┐
  │              ZooPipeline Harness                  │
  │                                                   │
  │  task_request → validate → dispatch(agent)        │
  │       → collect → review_cycle → deliver          │
  │       → archive                                   │
  │                                                   │
  │  ├── 每个阶段是 Python 代码方法，不是自然语言描述    │
  │  ├── 阶段转换有严格的状态机约束                      │
  │  ├── 所有 Agent 交互通过 sessions_send + shared    │
  │  └── 异常有代码兜底，不会"忘了步骤"                 │
  └──────────────────────────────────────────────────┘
```

---

## 三、P2P 架构详细设计

### 3.1 设计原则

1. **Panda 不承载消息内容** — 只发「Alpha 有东西给你，去读 shared/」
2. **Agent 之间直连** — 通过 `sessions_send` 直接对话，不需中间人
3. **ZooMesh 知库** — Event Bus 升级版，所有归档/决策/历史永久留存
4. **平等自治互连** — 每个成员都是平等节点，可主动发起通信
5. **渐进落地** — 先改配置再改代码，不炸现有体系

### 3.2 组件设计

#### 3.2.1 通信层：AgentSession

```
┌─────────────────────┐
│    AgentSession      │  ← 每个 Agent 在 ZooMesh 中的通信端点
├─────────────────────┤
│ session_id: str      │  ← 持久化 session 标识
│ agent_id: str        │  ← alpha / weaver / duci / aeterna / gulu
│ inbox: List[str]     │  ← 收件箱（未读消息 ID 列表）
│ status: str          │  ← online / busy / idle / offline
│ last_seen: float     │  ← 最后一次心跳时间
├─────────────────────┤
│ send(target, msg)    │  ← 通过 sessions_send 发送
│ receive()            │  ← 轮询收件箱
│ notify(target)       │  ← 发送简短通知（读取 shared/ 目录）
└─────────────────────┘
```

**实现方式**：每个 Agent 在 ZooMesh 的 `zoomesh/sessions/{agent_id}/` 目录下拥有：
- `inbox.jsonl` — 收件箱（持久化消息队列）
- `status.json` — 当前在线状态
- `metadata.json` — 绑定的 model、工具权限等

#### 3.2.2 知识层：ZooMesh 总线

```
framework/shared/zoomesh/
├── inbox/                    ← 每个 Agent 的收件箱
│   ├── alpha/                ← Alpha 的收件箱
│   │   └── inbox.jsonl
│   ├── weaver/
│   ├── duci/
│   ├── aeterna/
│   └── gulu/
├── events/                   ← Event Bus 持久化事件
│   └── {yyyy-mm-dd}.jsonl
├── sessions/                 ← Agent 持久化会话元数据
│   ├── alpha/metadata.json
│   ├── weaver/metadata.json
│   └── ...
├── archives/                 ← Aeterna 管理的历史归档
└── pipeline/                 ← Harness 执行状态
    ├── active_tasks.json
    └── task_logs/
```

#### 3.2.3 发现层：ZooRegistry

每个 Agent 知道其他成员的存在，无需经 Panda 查找。

```json
// zoomexh/sessions/registry.json
{
  "version": "2.0",
  "members": {
    "alpha": {
      "name": "Alpha",
      "title": "首席架构师",
      "model": "deepseek/deepseek-v4-flash",
      "session_key": "agent:alpha:zoomesh:<uuid>",
      "capabilities": ["architecture_design", "code_review", "schema_design"],
      "status": "online",
      "last_seen": "2026-05-10T12:00:00+08:00"
    },
    "weaver": {
      "name": "Weaver",
      "title": "疯狂工程师",
      "model": "minimax/MiniMax-M2.7",
      "session_key": "agent:weaver:zoomesh:<uuid>",
      "capabilities": ["code_implementation", "bug_fix", "test_automation"],
      "status": "idle",
      "last_seen": "2026-05-10T11:30:00+08:00"
    }
    // ... duci, aeterna, gulu, panda
  }
}
```

#### 3.2.4 通信协议

| 场景 | 通信方式 | 示例 |
|------|----------|------|
| **发送任务/请求** | `sessions_send(agentId, msg)` | Alpha → Weaver：「架构设计已发布，请实现」 |
| **交付成果** | 写入 `shared/` 目录 | Weaver 完成代码，写入 `shared/weaver_implementation_v1.py` |
| **简短通知** | `sessions_send(agentId, "去读 shared/xxx")` | Weaver → Duci：「实现完成，在 shared/，请审计」 |
| **状态广播** | Event Bus 发布事件 | Agent 上线/离线/忙碌状态变更 |
| **协作讨论** | `sessions_send` 来回对话 | 设计评审回合：Duci → Alpha → Duci |

---

## 四、Harness 流程引擎详细设计

### 4.1 为什么需要 Harness？

**当前流程的脆弱性**：

```
SKILL.md (自然语言)  →  LLM 读到 →  LLM 理解 →  LLM 执行
                                                    ↓
                                           ❌ 可能遗漏步骤
                                           ❌ 可能跳过"不重要的规则"
                                           ❌ 可能创造不存在的步骤
                                           ❌ 可能忘掉元规则
```

**目标状态：代码约束**：

```
ZooPipeline (Python 代码)  →  方法调用 →  Agent 参与决策
                                        ↓
                               ✅ 步骤顺序代码硬约束
                               ✅ 状态转换有限状态机
                               ✅ 异常有兜底策略
                               ✅ 审计日志自动记录
```

### 4.2 ZooPipeline 架构

```python
# 核心引擎 — 全流程代码约束

class ZooPipeline:
    """
    飝龘动物园流程约束引擎
    
    工作流全步骤由代码定义，每个阶段有明确的前置条件、后置输出和状态转换。
    AI Agent 仅作为"决策节点"参与具体的专业判断，流程走向由代码控制。
    """
    
    # ========== 阶段定义 ==========
    
    PHASE_REQUEST     = "request"      # 接收任务请求
    PHASE_VALIDATE    = "validate"     # 验证请求有效性
    PHASE_DESIGN      = "design"       # 架构设计（Alpha）
    PHASE_REVIEW      = "review"       # 方案评审（Duci）
    PHASE_DEVELOP     = "develop"      # 代码实现（Weaver）
    PHASE_AUDIT       = "audit"        # 代码审计（Duci）
    PHASE_FINAL_CHECK = "final_check"  # 最终合入确认（Alpha）
    PHASE_DELIVER     = "deliver"      # 交付与归档（Aeterna）
    
    # ========== 状态机 ==========
    
    STATE_MACHINE = {
        PHASE_REQUEST:     {PHASE_VALIDATE},
        PHASE_VALIDATE:    {PHASE_DESIGN, PHASE_REQUEST},  # 验证失败回退
        PHASE_DESIGN:      {PHASE_REVIEW},
        PHASE_REVIEW:      {PHASE_DESIGN, PHASE_DEVELOP},  # 评审不通过回退
        PHASE_DEVELOP:     {PHASE_AUDIT},
        PHASE_AUDIT:       {PHASE_DEVELOP, PHASE_FINAL_CHECK},  # 审计不通过回退
        PHASE_FINAL_CHECK: {PHASE_DELIVER, PHASE_DEVELOP},  # 最终确认不通过回退
        PHASE_DELIVER:     {},  # 终态
    }
    
    def run(self, task: Task) -> TaskResult:
        phase = PHASE_REQUEST
        while True:
            next_phases = self.STATE_MACHINE[phase]
            result = self._execute_phase(phase, task)
            if result.status == "blocked":
                return TaskResult(phase=phase, status="blocked", reason=result.reason)
            phase = self._decide_next(next_phases, result)
            if not next_phases:  # 终态
                break
        return TaskResult(...)
```

### 4.3 阶段执行器（Agent 交互点）

每个阶段由一个执行器（Executor）类实现。Agent 只在 Executor 内部作为"专家工具"被调用：

```python
class DesignExecutor(PhaseExecutor):
    """架构设计阶段 — Alpha 的舞台"""
    
    required_input = "task_brief"
    expected_output = ["architecture_doc", "schema_diagram"]
    
    def execute(self, task: Task, mesh: ZooMesh) -> PhaseResult:
        # 1. 代码检查前置条件
        assert task.has("task_brief"), "缺少任务简报"
        assert not task.get_last_output(self.phase), "设计阶段重复执行"
        
        # 2. 通过 ZooMesh 联系 Alpha
        alpha = mesh.get_agent("alpha")
        msg = f"【架构设计任务】简报已放在 shared/{task.id}/brief.md，请输出设计方案"
        alpha.send(msg)
        
        # 3. 等待 Alpha 交付（轮询 shared/ 目录）
        design_doc = mesh.wait_for_file(
            f"shared/{task.id}/architecture_v1.md",
            timeout=3600
        )
        
        # 4. 验证交付件是否符合规范
        if not self._validate_delivery(design_doc):
            return PhaseResult(status="failed", reason="交付件格式校验不通过")
        
        # 5. 记录执行结果
        task.record_phase(self.phase, design_doc)
        return PhaseResult(status="success", output=design_doc)
```

### 4.4 Harness 的约束边界

```
                    ╔═══════════════════════╗
                    ║   ZooPipeline (代码)   ║  ← 流程的骨：顺序、状态、约束
                    ╠═══════════════════════╣
                    ║                       ║
                    ║   PhaseExecutor       ║  ← 每阶段的执行逻辑
                    ║     ├─ 前置条件检查    ║     （代码，不是自然语言）
                    ║     ├─ 路由给 Agent    ║
                    ║     ├─ 等待交付        ║
                    ║     └─ 后置校验        ║
                    ║                       ║
                    ╠═══════════════════════╣
                    ║                       ║
                    ║   AI Agent (决策节点)  ║  ← 肉：架构判断、代码实现
                    ║     └─ 通过            ║     审计意见、设计决策
                    ║        sessions_send   ║
                    ║        参与具体任务     ║
                    ║                       ║
                    ╚═══════════════════════╝
```

**关键原则**：
- 流程顺序由 **Python 代码** 硬约束 — 不会"跳过"步骤
- 阶段间状态转换由 **有限状态机** 控制 — 只有明确允许的跳转
- AI Agent 在阶段 **内部** 作为专家 — 负责内容，不负责流程
- 交付件格式校验由 **Schema 验签** 保证 — 不是"看看写没写"
- 审计日志由 **Harness 自动记录** — 每次阶段执行都有 trace

### 4.5 和现有系统的关系

| 现有组件 | 在 Harness 中的角色 |
|----------|---------------------|
| `framework/workflows/default.yaml` | ❌ 废弃 — 被 ZooPipeline 代码替代 |
| `framework/core/ spawner.py` | ✅ 保留 — 成员孵化仍有用 |
| `framework/shared/ event_bus/` | ✅ 保留并升级为 ZooMesh 的 events 层 |
| `framework/core/ zoo_coordinator.py` | ⚠️ 重构 — 保留 @提及解析，移除工作流逻辑 |
| `framework/shared/ task_tracker.json` | ✅ 保留 — 作为 Harness 的状态持久化后端之一 |
| `framework/configs/ system.yaml` | ✅ 保留 — 作为服务配置（非流程配置） |
| SKILL.md 中的流程规则 | ❌ 废弃 — 元规则抽象转移到代码 |
| SKILL.md 中的元规则（1-14） | ⚠️ 浓缩 — 元规则 1-14 中与流程相关的规则转为代码断言 |

---

## 五、P2P + Harness 整合工作流

### 典型任务全流程示例

```
  园长发任务
      │
      ▼
┌──────────────────────────────────────┐
│ Panda 收到 → 调用 ZooPipeline       │
│   task = Pipeline.create_task()     │
└──────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────┐
│ PHASE 1: validate                   │
│ ├─ 解析任务类型                      │
│ ├─ 校验参数完整性                    │
│ └─ 根据类型路由到不同 Agent          │
└──────────────────────────────────────┘
      │
      ├── 架构任务 ─────────────┐
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 2: design       │
      │             │ ├─ sessions_send→Alpha │
      │             │ └─ 等待 shared/ 交付  │
      │             └───────────────────────┘
      │                         │
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 3: review       │
      │             │ ├─ sessions_send→Duci │
      │             │ ├─ Duci 审计 → P1/P2/P3│
      │             │ └─ 不通过 → 回到 Phase2│
      │             └───────────────────────┘
      │                         │ 通过
      │                         ▼
      ├── 开发任务 ─────────────────────┐
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 4: develop      │
      │             │ ├─ sessions_send→Weaver│
      │             │ └─ 等待 shared/ 交付  │
      │             └───────────────────────┘
      │                         │
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 5: audit        │
      │             │ ├─ sessions_send→Duci │
      │             │ ├─ 测试审计 + 代码审计 │
      │             │ └─ 不通过 → 回到 Phase4│
      │             └───────────────────────┘
      │                         │ 通过
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 6: final_check  │
      │             │ ├─ sessions_send→Alpha│
      │             │ ├─ Alpha 合入确认     │
      │             │ └─ 无明确放行 → 不放行│
      │             └───────────────────────┘
      │                         │ 放行
      │                         ▼
      │             ┌───────────────────────┐
      │             │ PHASE 7: deliver      │
      │             │ ├─ 合并代码到 main    │
      │             │ ├─ sessions_send→Aeterna │
      │             │ ├─ Aeterna 归档       │
      │             │ └─ Panda 通知园长     │
      │             └───────────────────────┘
      │
      ▼
  ┌──────────┐
  │  完成 🎉 │
  └──────────┘
```

---

## 六、分阶段实施计划

### 🟢 阶段 0 — 零成本配置启动（5分钟）

**目标**：启用 `agentToAgent` 和 session 可见性，让成员间可以 `sessions_send`

**操作**：
1. 在 `~/.openclaw/openclaw.json` 中添加 `tools.agentToAgent` 配置
2. 设置 `tools.sessions.visibility: "all"`
3. 重启网关

**验证方式**：Alpha → Weaver 发一条 `sessions_send` 测试消息

**风险**：零。纯配置变更，无代码改动，可随时回滚。

**前置条件**：无（配置即用）

---

### 🔵 阶段 1 — ZooPipeline Harness 核心（2-3天）

**目标**：开发 Harness 引擎骨架，实现最核心的 `ZooPipeline` 类和 `PhaseExecutor` 基类

**产出物**：
```
framework/shared/zoomesh/        ← ZooMesh 目录结构
framework/core/harness/          ← Harness 引擎代码
  ├── __init__.py
  ├── pipeline.py                ← ZooPipeline 主引擎
  ├── phase_executor.py          ← PhaseExecutor 基类
  ├── state_machine.py           ← 有限状态机
  └── executors/                 ← 各阶段实现
      ├── __init__.py
      ├── validate_executor.py
      ├── design_executor.py
      ├── review_executor.py
      ├── develop_executor.py
      ├── audit_executor.py
      └── deliver_executor.py
framework/core/mesh/
  ├── __init__.py
  ├── agent_session.py           ← AgentSession 通信端点
  ├── zoo_registry.py            ← 成员注册表
  └── zoo_mesh.py                ← ZooMesh 总线封装
```

**验收标准**：
- ZooPipeline 能跑通一个完整的"设计→评审→实现→审计→交付"流程（当前用 mock agent）
- 状态机严格约束阶段转换，不合法的跳转被拒绝
- PhaseExecutor 能通过 sessions_send 向真实 Agent 发消息
- 每个阶段执行有审计日志写入

**依赖条件**：阶段 0 完成（agentToAgent 已启用）

---

### 🟡 阶段 2 — 孵化器集成 + SKILL.md 迁移（2天）

**目标**：将 Panda 的 SKILL.md 工作流逻辑迁移到 Harness，废弃 YAML 流程定义

**迁移清单**：

| 来源 | 去向 | 工作内容 |
|------|------|----------|
| `SKILL.md` 第3节（元规则） | `harness/validators.py` | 规则转代码断言 |
| `SKILL.md` 第12节（工作流） | `harness/executors/*.py` | 流程步骤转 PhaseExecutor |
| `workflows/default.yaml` | 废弃 | 被 pipeline.py 替代 |
| `task_tracker.json` | `harness/state/persistence.py` | 任务状态持久化升级 |
| SKILL.md 第2节（派单规则） | `mesh/zoo_registry.py` | 发现 + 路由 |

**注意**：元规则 1-14 中 **非流程相关的**（如身份标识、对外安全、文件命名等）保留在 SKILL.md 作为公约，不迁移到代码。

---

### 🔴 阶段 3 — Agent 持久化 + 全功能 P2P（2-3天）

**目标**：成员从 `mode="run"` 切换为持久化 session，实现双向通信

**改动**：
1. 成员召唤协议从 `mode="run"` 改为持久 session
2. 每个成员拥有 ZooMesh 收件箱（inbox.jsonl）
3. 成员之间可互相唤醒：Weaver → Duci「帮我审计」
4. 园长可直接 @ 任一成员（不经过 Panda）

**验收标准**：
- Weaver 能主动给 Duci 发消息，Duci 能回复
- 成员离线后重新上线，inbox 消息不丢失
- 园长通过 QQ Bot 直接 @Alpha，Alpha 回复（不经 Panda）

---

## 七、风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Agent 会话过多占用资源 | 🟡 | 限制 maxSpawnDepth=1，空闲超时清理（30min） |
| sessions_send 消息丢失 | 🟡 | 异步写入 ZooMesh inbox.jsonl 做持久化备份 |
| Harness 代码本身有 Bug | 🔴 | 每个 PhaseExecutor 必须有单元测试覆盖，入 CI |
| 技能流程迁移遗漏规则 | 🟡 | 迁移时 Pair Review（Alpha + Duci 核对每条规则去向） |
| 园长找不到 Panda | 🟢 | 保持一条园长→Panda 直连通道不变 |
| 持久 session 的成本增加 | 🟢 | 闲置 session 的 token 消耗有限（上下文保留但无新内容） |

---

## 八、改造前后对比

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| **消息流转** | Panda 转述 | Agent 直连 sessions_send |
| **流程执行** | SKILL.md + YAML → LLM 自由发挥 | ZooPipeline 代码引擎 → Agent 在阶段内工作 |
| **流程幻觉** | ⚠️ 高（LLM 可能跳步/漏步/加戏） | ✅ 零（状态机硬约束） |
| **Panda 角色** | 传声筒 + 记忆包 | 协调员 + 园长接口 |
| **成员通信** | 只能和 Panda 说话 | 直连所有成员 |
| **成员生命周期** | mode="run" 用完即焚 | 持久 session + inbox |
| **知识留存** | 零散，修复才留痕 | Harness 自动记录审计日志 |
| **并行能力** | 串行经 Panda | Agent 多线对话并行 |
| **灾难恢复** | Panda 挂 = 全瘫 | 独立 agent session 仍可工作 |
| **可扩展性** | 每加一员 Panda 负担加重 | 新成员加入 ZooMesh 即可 |
| **园长体验** | 只能看 Panda 转述 | 可直接 @ 任一成员 |

---

## 九、决策点

| 决策 | 选项 | 建议 |
|------|------|------|
| **阶段 0 是否立即执行？** | 是 / 否 | ✅ **可以现在做**，纯配置，零风险，5分钟 |
| **Harness 用什么语言？** | Python / TypeScript | ✅ **Python** — 与已有 Event Bus / ZooCoordinator 一致 |
| **SKILL.md 要全部废弃吗？** | 是 / 部分保留 | ✅ **部分保留** — 流程规则迁到代码，公约/规范留在 MD |
| **YAML workflos 要废弃吗？** | 是 / 保留兼容 | ✅ **废弃** — 被 pipeline.py 替代，不维护两套 |
| **持久化 session 用 OpenClaw 的 session 还是自制？** | 原生 / 自制 | ✅ **混合** — 通信用原生 sessions_send，持久化用 ZooMesh 目录 |

---

> **设计者签名**: 阿尔法（玄龟）🐢  
> **状态**: ⏳ 待审 — 已提交给毒刺做架构方案评审  
> **下一站**: 毒刺审核 → 园长终审 → 等令开动  
> **文件位置**: `framework/shared/alpha_feida_zoo_P2P_Harness_Architecture_v1.0.md`
