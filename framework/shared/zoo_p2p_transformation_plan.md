# 🏗️ 飝龘动物园 Agent 模式改造方案

> **作者**: Panda 🐼  
> **日期**: 2026-05-05  
> **状态**: 待园长审批  

---

## 一、现状痛点分析

### 当前架构（Hub-and-Spoke）

```
  园长 (飝龘龘)
       │
       ▼
  ┌──────────┐
  │  Panda   │ ← 所有信息都在Panda脑子里转发
  │ (转发器) │
  └────┬─────┘
       │
  ┌────┼────┬────┬────┐
  ▼    ▼    ▼    ▼    ▼
Alpha Weaver DuciAeterna Gulu
```

### 问题

1. **消息全部经过 Panda** — Agent A 想找 Agent B，Panda 要先听 A 说，再转告 B，再听 B 说，再转告 A
2. **Panda 主会话上下文爆炸** — 所有成员的交互内容都堆在 main session 里，Token 消耗巨大
3. **成员间无直接认知** — Alpha 不知道 Weaver 在干什么，只能通过 Panda 间接知道
4. **mode="run" 的临时会话** — 每次唤醒成员都是一次「出生→干活→死亡」，没有持久身份

### 已有但未用上的基础设施

| 资产 | 状态 | 说明 |
|------|------|------|
| **Event Bus** (`framework/shared/event_bus/`) | ✅ 已开发 | 文件级 Pub/Sub 消息队列，支持去重/并发安全 |
| **共享目录** (`framework/shared/`) | ✅ 已使用 | 跨成员文件交换，当前走的是「Panda通知→读文件」 |
| **zoo_chat_room_analysis.md** | ✅ 已分析 | 阿尔法4/6出的架构设计，已写明需求、可做实时聊天面板 |
| **agentToAgent** (OpenClaw 原生) | ❌ 未启用 | 底层已支持 session 级别 Agent↔Agent 通信 |
| **sessions_send** (OpenClaw 原生) | ❌ 未启用 | Agent 之间直接发送消息的能力 |

---

## 二、目标架构（Peer-to-Peer Mesh）

```
        园长 (飝龘龘)
            │
            ▼
     ┌──────────────┐
     │   Panda      │  ← 从转发器降级为协调员
     │ (Orchestrator)│    → 只做任务派发、状态监控
     └──────┬───────┘      → 不传递消息内容
            │
            │  ZooMesh (共享知识总线)
            │  ┌──────────────────────────────┐
            │  │  • Event Bus (消息队列)       │
            │  │  • 共享文件 (交付物)           │
            │  │  • 知识库 (决策归档)           │
            │  │  • agentToAgent (直连通道)     │
            │  └──────────────────────────────┘
            │              ↑
            │         ╔════╧════╗
            │         ║ 直连通道 ║ ← sessions_send
            │         ╚════╤════╝
            │              │
       ┌────┼────┬────┬────┤
       ▼    ▼    ▼    ▼    ▼
     Alpha → Weaver → Duci → Aeterna → Gulu
       │       │        │        │        │
       └───────┴────────┴────────┴────────┘
       ↑ Agent 之间可以直接 sessions_send ↑
```

### 核心原则

1. **Panda 不承载消息内容** — 只发「Alpha 有东西给你，去读 shared 目录」
2. **Agent 之间直连** — 通过 `sessions_send` 直接对话
3. **ZooMesh 知库** — Event Bus 升级版，所有归档、决策、历史永久留存
4. **平等、自治、互连** — 每个成员都是平等的节点，可以主动发起通信

---

## 三、技术实现方案

### Step 1: 启用 `agentToAgent`（最小改动，最大收益）

修改 `~/.openclaw/openclaw.json`，添加：

```json5
{
  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["main", "alpha", "weaver", "duci", "aeterna", "gulu"],
    },
    sessions: {
      visibility: "all",  // 允许跨agent看到对方会话
    },
  },
}
```

**效果**: Agent 之间可以通过 `sessions_send(agentId: "weaver")` 直接发送消息，Panda 不再需要当鹦鹉。

### Step 2: Agent 从 mode="run" 切换为 mode="session"

**当前**: 每次唤醒是新的子会话，成员用完即焚（无记忆、无接收能力）

**改造后**:
- 每个 Agent 作为持久化 session 运行在后台
- 支持接收 `sessions_send` 发来的消息
- 成员拥有独立会话历史，不再污染 Panda 的主会话

**改动点**（在 SKILL.md 中的召唤协议）:

```yaml
# 当前
sessions_spawn:
  mode: "run"          # 用完即焚
  cleanup: "delete"    # 删除会话

# 改造后
sessions_spawn:
  mode: "session"      # 持久化会话
  cleanup: "keep"      # 保留会话
```

### Step 3: Event Bus → ZooMesh 升级

**现有 Event Bus 已实现**:
- 发布订阅模式
- 并发安全文件锁
- 事件去重
- 跨进程可见

**需要升级的**:
- 添加 inbox/outbox 模式 — 每个 Agent 在 ZooMesh 有独立收件箱
- 添加 sessions_send 集成 — Event Bus 事件可直接触发 sessions_send
- 添加知识沉淀管道 — Aeterna 自动从 ZooMesh 拉取归档

### Step 4: 直接沟通协议（案例对比）

**场景: Alpha 要 Weaver 实现一个功能**

改造前 (Panda 转发):
```
Alpha → Panda: 「这是架构设计」(大段文本)
Panda → 园长:  [转发大段文本到园长聊天窗口]
Panda → Weaver: 「Alpha 说...」(Panda再加工)
Weaver → Panda: 「好的收到」
Panda → Alpha: 「Weaver回复了好」
Panda → 园长:  [再转发Weaver的回复]
```

改造后 (直接对话):
```
Alpha: (写入 shared/alpha_arch_v2.md)
     → sessions_send(agentId: "weaver",
        「架构设计已发布在 shared/alpha_arch_v2.md，请查阅」)
Weaver: (读取文件)
     → sessions_send(agentId: "alpha",
        「已阅，预计30min完成，完成后通知Duci审计」)
Weaver: → sessions_send(agentId: "duci",
        「Alpha新架构即将完成，请准备审计」)
Duci: → sessions_send(agentId: "weaver",
        「收到，请在完成后提交测试用例」)
```

**关键变化**:
- Panda 完全不参与内容传递
- 消息仅在 ZooMesh 中占一次存储（不是多次复制）
- Agent 之间通过 `sessions_send` 直连
- 沟通产生多线并行，而非串行流转

### Step 5: Panda 角色转型

| 当前 | 改造后 |
|------|--------|
| 转发所有消息 | 仅在任务开始时做派单 |
| 承担所有Token消耗 | 轻量化，只做协调 |
| 记忆所有人干了什么 | 只记录项目级状态 |
| 每次通信中间人 | 只在关键节点介入 |
| 园长→Panda→Agent→Panda→园长 | 园长→[任一Agent]，Agent之间自治 |

---

## 四、分阶段实施计划

### 🟢 阶段 0（立即，5分钟）— 最小启动

**启用 `agentToAgent`**

1. 在 `~/.openclaw/openclaw.json` 中添加 `tools.agentToAgent` 配置
2. 设置 `tools.sessions.visibility: "all"`
3. 重启网关 → Alpha 和 Weaver 可以直接对话

**风险**: 零。纯配置变更，无代码改动，可随时回滚。

**验证方式**: Panda 发一条 `sessions_send(agentId: "alpha")` 测试消息，Alpha 直接回复。

---

### 🔵 阶段 1（1-2天）— Agent 持久化

1. 修改 `feida-zoo/SKILL.md` 召唤协议：支持 `mode: "session"` 
2. 为每个 Agent 创建 inbox 收件箱目录 (`framework/shared/zoomesh/inbox/<agent>/`)
3. 添加 `sessions_send` 到 Agent 的允许工具列表
4. 编写 `ZooMeshAdapter` — Event Bus ↔ sessions_send 桥接层

**产出物**:
- 成员间可直接 `sessions_send`
- 代码在 `framework/shared/zoomesh/` 落地
- Panda 主会话上下文占用下降约 50%

---

### 🟡 阶段 2（2-3天）— 研发中心聊天面板

沿承 `zoo_chat_room_analysis.md` 的设计方案：

1. 在研发中心（port 18792）右侧添加聊天面板
2. Chat UI 绑定 ZooMesh Event Bus
3. 支持消息类型：普通发言、@成员、工作流触发、状态通知
4. 工作流引擎：A 完成 → 自动 @B

**产出物**:
- 可视化聊天界面（园长可见所有Agent的对话）
- 工作流自动流转
- 历史消息可追溯

---

### 🔴 阶段 3（后续迭代）— 全功能 P2P

1. 成员间可互相唤醒（Alpha → Weaver 「帮我跑个测试」）
2. Aeterna 自动归档所有 ZooMesh 消息
3. 园长可直接 @ 任一成员（不再经过 Panda）
4. 聊天室历史搜索/回放

---

## 五、技术验证

### 可行性验证（已在 OpenClaw 沙盒中确认）

| 能力 | OpenClaw 原生支持 | 状态 |
|------|-------------------|------|
| `sessions_send` 跨 agent | ✅ `agentToAgent` 开启即可 | 就绪 |
| Agent 看到对方会话 | ✅ `tools.sessions.visibility: "all"` | 就绪 |
| 持久化 session | ✅ `mode: "session"` | 就绪 |
| 文件共享 | ✅ 已有 `framework/shared/` | 已就绪 |
| Event Bus (Python) | ✅ 已完成 | 已就绪 |
| 研发中心前端 | ✅ 已有 dashboard 框架 | 已就绪 |

### 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Agent 会话过多占用资源 | 限制 maxSpawnDepth=1，空闲清理 |
| sessions_send 消息丢失 | 异步写入 ZooMesh 做持久化备份 |
| 同时唤醒多个 Agent 冲突 | 任务排他锁（已有 fcntl 实现） |
| 园长找不到 Panda | 保持一条园长→Panda 直连通道不变 |

---

## 六、改造前后对比

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| **消息流转** | Panda 转述 | Agent 直连 sessions_send |
| **Panda 角色** | 传声筒 | 协调员 |
| **Panda 上下文占用** | 高（包含所有成员消息内容） | 低（仅协调状态） |
| **沟通延迟** | 中等（经 Panda 过滤+转述） | 低（直连） |
| **成员自治度** | 低（依赖 Panda 唤醒） | 高（可主动联系其他成员） |
| **知识留存** | 零散（Panda 记忆） | ZooMesh 永久归档 |
| **并行能力** | 弱（所有消息串行经 Panda） | 强（Agent 多线对话并行） |
| **灾难恢复** | Panda 挂 = 全瘫 | 独立 agent session 仍可工作 |
| **可扩展性** | 每加一员 Panda 负担加重 | 新成员加入总线即可 |
| **透明可见** | 园长只能看到 Panda 转述 | 园长可在聊天面板看全貌 |

---

## 七、决策点

| 决策项 | 选项 |
|--------|------|
| **是否启用 agentToAgent?** | 阶段0，5分钟纯配置，零风险 |
| **是否推 agent 持久化?** | 阶段1，1-2天开发 |
| **是否建聊天面板?** | 阶段2，承前文设计 |
| **最终目标** | 阶段3 全功能 P2P 生态 |

---

**结论**: 改造方案的工程工作量极低（阶段 0 只需 5 分钟配置），但架构收益巨大。动物园成员从「Panda 的孩子」变成「平等的同事」。

---

*方案完毕。等待园长「飞龙在天」授权启动阶段 0。* 🐼
