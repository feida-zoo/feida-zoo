# 🏗️ 飝龘动物园 · P2P 架构 + Harness 化改造设计 v1.1

> **版本**: v1.1（基于毒刺 P1/P2 审核意见的补丁版）  
> **原版**: [v1.0](alpha_feida_zoo_P2P_Harness_Architecture_v1.0.md)  
> **审核者**: 毒刺（蝎子）🦂  
> **日期**: 2026-05-10  
> **状态**: 待复审 → 园长终审

---

## 修订日志

| 修订 | 对应审核项 | 修改内容 |
|------|-----------|----------|
| v1.1a | **P1-1** | 新增 2.1 节：Inbox at-least-once 投递确认模型 |
| v1.1b | **P1-2** | 新增 2.2 节：阻塞等待改事件驱动 + 超时降级链 |
| v1.1c | **P1-3** | 新增 2.3 节：状态机补 cancel/timeout/error |
| v1.1d | **P1-4** | 新增 2.4 节：Panda 权限清单 |
| v1.1e | **P2-1** | 新增 2.5 节：动态 session 解析 |
| v1.1f | **P2-2** | 新增 2.6 节：Event Bus 写入加锁 |
| v1.1g | **P2-3** | 新增 2.7 节：回退计数器保护 |
| v1.1h | **P2-4** | 新增 2.8 节：SKILL.md → Harness 迁移映射矩阵 |
| v1.1i | **P2-5** | 新增 2.9 节：Session 生命周期管理 |

---

## 2.1 P1-1 · Inbox at-least-once 投递确认模型

### 问题

原设计的 inbox 是"写后即忘"——`send()` 追加一行到 JSONL，无 ACK、无消费确认、无重试。

### 设计方案

每个 Agent 的收件箱增加两层保障层：**持久化写入** + **消费确认**。

#### 2.1.1 收件箱目录结构

```
zoomesh/inbound/<agent_id>/
├── queue/                    ← 待消费消息（文件级，一个消息一个文件）
│   ├── msg_<uuid1>.json     ← 每条消息独立文件，避免行级交错
│   ├── msg_<uuid2>.json
│   └── ...
├── checkpoint.json           ← 最后已消费消息的偏移标记
│                              { "last_id": "msg_<uuidX>", "updated_at": "..." }
├── dlq/                      ← 死信队列（重试超限的消息）
│   └── msg_<uuid_failed>.json
└── config.json               ← 投递配置
    { "max_delivery_attempts": 3, "visibility_timeout": 300 }
```

#### 2.1.2 投递协议

```
send(agent_id, message):
  1. 生成 msg_<uuid>.json，包含：
     - id: uuid
     - from: 发送者
     - to: 接收者
     - body: 消息内容
     - timestamp: 发送时间
     - delivery_count: 0
     - ttl: 3600 (1小时后自动过期)
  2. 原子写入 queue/msg_<uuid>.json
     （使用 temp + rename，确保不出现半写文件）
  3. 返回投递成功

receive(agent_id):
  1. 读取 queue/ 目录，按 mtime 排序
  2. 取最早的一条 msg_<uuid>.json
  3. 读入内存
  4. 标记为 "in-flight"（在内存中处理，不改文件）
  5. 返回消息体
  
ack(agent_id, msg_id):
  1. 删除 queue/msg_<msg_id>.json
  2. 更新 checkpoint.json 的 last_id

nack(agent_id, msg_id):
  1. 递增 msg.json 内的 delivery_count
  2. 如果 delivery_count < max_delivery_attempts → 不改动，下次 receive 重试
  3. 如果 delivery_count >= max_delivery_attempts → 移动到 dlq/ 目录
```

#### 2.1.3 重启恢复流程

```
agent 启动：
  1. 读取 checkpoint.json，获取 last_id
  2. 读取 queue/ 目录，过滤掉 last_id 之前的所有消息
  3. 处理剩余消息（从尚未确认的最后一条开始）
  4. 处理过程中若崩溃 → 重启后，未确认的消息仍在 queue/ 中，再次消费
```

**保证**：at-least-once 语义 —— 消息要么未被消费、要么被消费至少一次。消费者端需自行处理幂等性（消息 id 去重）。

---

## 2.2 P1-2 · 事件驱动 + 超时降级链

### 问题

原设计的 `mesh.wait_for_file()` 是同步阻塞轮询，最大 1 小时，无超时降级。

### 设计方案

#### 2.2.1 异步等待模型（替代同步轮询）

使用 Event Bus 的事件订阅替代轮询：

```python
class AsyncDeliveryWatcher:
    """
    异步交付等待器
    
    不阻塞线程，通过 Event Bus 订阅事件来获知交付完成。
    """
    
    def __init__(self, mesh: ZooMesh):
        self._mesh = mesh
        self._subscriptions: Dict[str, Callable] = {}
        self._timeouts: Dict[str, Timer] = {}
    
    def expect_delivery(
        self,
        task_id: str,
        from_agent: str,
        expected_file_pattern: str,
        timeout: int = 3600,
        on_delivered: Callable = None,
        on_timeout: Callable = None,
        on_error: Callable = None,
    ) -> None:
        """
        注册一个交付期望
        - 订阅 Event Bus 的 'file_delivered' 事件
        - 注册超时定时器
        """
        # 订阅交付事件
        self._mesh.event_bus.subscribe("file_delivered", self._on_file_delivered)
        
        # 设置超时定时器
        timer = Timer(timeout, self._on_timeout, args=[task_id])
        self._timeouts[task_id] = timer
        timer.start()
        
        self._subscriptions[task_id] = {
            "from_agent": from_agent,
            "pattern": expected_file_pattern,
            "on_delivered": on_delivered,
            "on_timeout": on_timeout or self._default_timeout_handler,
            "on_error": on_error or self._default_error_handler,
        }
    
    def _on_file_delivered(self, event):
        """当 Agent 发布 file_delivered 事件时触发"""
        payload = event["payload"]
        if payload["task_id"] in self._subscriptions:
            self._subscriptions[payload["task_id"]]["on_delivered"](payload)
            self._cleanup(payload["task_id"])
```

#### 2.2.2 超时降级链

```
  超时到达
      │
      ├─> 第1级：重试（发送提醒给 Agent）
      │    └── 提醒后 +5 分钟 → 仍未交付
      │
      ├─> 第2级：escalate to Panda
      │    └── Panda 收到 → 判断：是 Agent 卡了还是正在做？
      │        ├── Agent 卡了 → Panda 通知园长
      │        └── 正常进行 → 再给 10 分钟
      │
      ├─> 第3级：escalate to 园长
      │    └── 园长决策：继续等 / 取消任务 / 替换 Agent
      │
      └─> 第4级：任务标记为 failed
            └── 记录到 task_tracker.json
                通知受影响的下游阶段
```

#### 2.2.3 交付件匹配规则（非硬编码）

```python
class DeliveryMatcher:
    """
    交付件匹配器
    
    不硬编码文件名，使用 glob pattern + 语义匹配。
    pattern 示例：
      - "architecture*" → 匹配任意 architecture 开头的文件
      - "design_v*.md" → 匹配 design_v1.md, design_v2.md...
    """
    
    @staticmethod
    def find_delivery(delivery_dir: str, expected_pattern: str) -> Optional[str]:
        """在交付目录中查找匹配的文件"""
        import glob
        files = glob.glob(os.path.join(delivery_dir, expected_pattern))
        if not files:
            return None
        # 取最新版本（按时间排序）
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]
```

---

## 2.3 P1-3 · 状态机补 cancel/timeout/error

### 完整的有限状态机

```
                         ┌──────────────────┐
                         │     cancelled     │ ← 园长主动取消，任意阶段可进入
                         └──────────────────┘
                              ↑ (任意阶段)

状态转换表 (完整版)：

┌───────────────┬──────────────────────────────────────────────────┐
│ 当前阶段       │ 可转换到                                         │
├───────────────┼──────────────────────────────────────────────────┤
│ request       │ validate, cancelled                              │
│ validate      │ request(重填), design, cancelled                 │
│ design        │ review, cancelled, timed_out                     │
│ review        │ design(回退), develop, cancelled, timed_out      │
│ develop       │ audit, cancelled, timed_out                      │
│ audit         │ develop(回退), final_check, cancelled, timed_out │
│ final_check   │ deliver, develop(未放行), cancelled              │
│ deliver       │ done, cancelled                                  │
│ done          │ (终态)                                            │
│ timed_out     │ escalated(通知园长), cancelled                   │
│ cancelled     │ (终态)                                            │
│ escalated     │ request(重新开始), cancelled                     │
└───────────────┴──────────────────────────────────────────────────┘
```

### 异常处理逻辑

```python
class StateMachine:
    
    TRANSITIONS = {
        "request":     ["validate", "cancelled"],
        "validate":    ["request", "design", "cancelled"],
        "design":      ["review", "cancelled", "timed_out"],
        "review":      ["design", "develop", "cancelled", "timed_out"],
        "develop":     ["audit", "cancelled", "timed_out"],
        "audit":       ["develop", "final_check", "cancelled", "timed_out"],
        "final_check": ["deliver", "develop", "cancelled"],
        "deliver":     ["done", "cancelled"],
        "done":        [],       # 终态
        "timed_out":   ["escalated", "cancelled"],
        "cancelled":   [],       # 终态
        "escalated":   ["request", "cancelled"],
    }
    
    def transition(self, from_state: str, to_state: str) -> bool:
        """安全的状态转换。合法返回 True，不合法拒绝并记录。"""
        if to_state in self.TRANSITIONS.get(from_state, []):
            return True
        raise InvalidTransition(f"{from_state} → {to_state} 非法")
    
    def handle_error(self, current_state: str, error: Exception):
        """错误兜底：无法处理的异常 → escalated"""
        return self.transition(current_state, "escalated")
```

### `_decide_next` 决策规则

| 场景 | 决策者 | 决策依据 |
|------|--------|----------|
| 阶段正常完成 | **代码** | 按状态机走预设分支 |
| 审核不通过（review/audit） | **代码** | 自动回退到上一阶段（design/develop） |
| 审核回退超限 | **Panda** | 判断是否需要园长介入 |
| 超时 | **代码** → **Panda** | 代码先执行自动降级链，最终 escalate |
| 取消 | **园长** | 直接标记 cancelled |
| 争议（Agent 间分歧） | **Panda** | 听取双方意见后仲裁，可 escalate 到园长 |

---

## 2.4 P1-4 · Panda 权限清单

### Panda 的权限定义

```
╔══════════════════════════════════════════════════╗
║            Panda 🐼 权限清单                      ║
╠══════════════════════════════════════════════════╣
║                                                   ║
║  ✅ 授权行为：                                     ║
║  ┌──────────────────────────────────────────┐    ║
║  │ 1. 接收园长指令 → 创建 Task → 启动 Pipeline │    ║
║  │ 2. 监控所有 Pipeline 执行状态              │    ║
║  │ 3. 审核回退超限（>3次）→ 仲裁并通知园长     │    ║
║  │ 4. 争议仲裁（Agent 间分歧）                │    ║
║  │ 5. 接收 escalated 信号 → 判断 → 处理      │    ║
║  │ 6. 向园长汇报项目级状态                     │    ║
║  └──────────────────────────────────────────┘    ║
║                                                   ║
║  ❌ 禁止行为：                                     ║
║  ┌──────────────────────────────────────────┐    ║
║  │ 1. 不允许转发消息内容（"Weaver 说……")      │    ║
║  │ 2. 不允许替 Agent 做专业决策（"架构就这样"） │    ║
║  │ 3. 不允许擅自修改 Agent 的交付件            │    ║
║  │ 4. 不允许跳过 Harness 直接驱动 Agent        │    ║
║  └──────────────────────────────────────────┘    ║
║                                                   ║
╚══════════════════════════════════════════════════╝
```

### 争议仲裁流程

```
  Agent A vs Agent B 分歧
      │
      ▼
  Panda 介入
      │
      ├─ 听取双方论点（通过 sessions_send 各自陈述）
      ├─ 检查事实依据（读取 shared/ 中的交付件）
      │
      ├── Panda 能判断 → 给出仲裁结果，记录到 task_tracker
      │
      └── Panda 无法判断 → escalate 到园长
              │
              └── 园长决策 → 写入 task_tracker 作为终审记录
```

---

## 2.5 P2-1 · 动态 session 解析

### 问题

静态 `ZooRegistry` 中的 `session_key` 会在 OpenClaw session 重启后失效。

### 方案：Label 解析 + 刷新机制

```python
class SessionResolver:
    """
    Session 动态解析器
    
    不硬编码 session_key，而是通过 agentId + label 路由，
    由 ZooMesh 在注册表中维护最新的活跃 session 映射。
    """
    
    # 静态 Label 路由表（不依赖 session_key）
    LABEL_MAP = {
        "alpha":   {"label": "alpha-zoomesh", "model": "deepseek/deepseek-v4-flash"},
        "weaver":  {"label": "weaver-zoomesh", "model": "minimax/MiniMax-M2.7"},
        "duci":    {"label": "duci-zoomesh", "model": "glm-5.1"},
        "aeterna": {"label": "aeterna-zoomesh", "model": "minimax/MiniMax-M2.7"},
        "gulu":    {"label": "gulu-zoomesh", "model": "minimax/MiniMax-M2.7"},
        "panda":   {"label": "panda-zoomesh", "model": "minimax/MiniMax-M2.7"},
    }
    
    def send(self, agent_id: str, message: str) -> bool:
        """通过 label 发送消息，不依赖 session_key"""
        entry = self.LABEL_MAP.get(agent_id)
        if not entry:
            return False
        
        # 使用 sessions_send(label=...)，OpenClaw 自动解析到最新 session
        result = sessions_send(label=entry["label"], message=message)
        return result.status == "accepted"
```

**注意**：这依赖于 OpenClaw 的 label 路由能力。如果当前版本不支持 label 路由，则在 ZooRegistry 中维护一个 `{agent_id: last_known_session_key}` 缓存，每次发送前先通过 `sessions_list` 查询最新激活的 session。

---

## 2.6 P2-2 · Event Bus 写入加锁

### 方案

Event Bus 的事件持久化写入全程使用 `fcntl.flock` 文件锁。

```python
import fcntl

class LockedJsonlWriter:
    """
    线程/进程安全的 JSONL 写入器
    
    使用 fcntl.flock 确保并发写入安全。
    自动处理行交错、半写等问题。
    """
    
    def __init__(self, path: str):
        self.path = path
    
    def append(self, event: dict):
        with open(self.path, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 获取排他锁
            try:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())  # 强制刷盘
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
    
    def read_all(self) -> List[dict]:
        """读取时也加共享锁，防止读写冲突"""
        events = []
        with open(self.path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return events
```

---

## 2.7 P2-3 · 回退计数器保护

### 方案

每个 Task 维护 `retry_count[phase]`，超过阈值自动 escalate。

```python
class Task:
    """任务实例"""
    
    MAX_RETRIES = {
        "review":  3,    # review → design 最多 3 次
        "audit":   3,    # audit → develop 最多 3 次
        "develop": 2,    # 实现阶段回退限制更严格
        "design":  2,    # 设计阶段回退限制
    }
    
    def __init__(self, task_id: str):
        self.id = task_id
        self.retry_count: Dict[str, int] = {
            "request": 0, "validate": 0, "design": 0,
            "review": 0, "develop": 0, "audit": 0,
            "final_check": 0, "deliver": 0,
        }
    
    def record_rollback(self, phase: str) -> str:
        """
        记录一次回退，返回建议动作。
        - "retry": 可以继续回退重试
        - "escalate": 超过阈值，需要 Panda/园长介入
        """
        self.retry_count[phase] += 1
        max_r = self.MAX_RETRIES.get(phase, 3)
        if self.retry_count[phase] > max_r:
            return "escalate"
        return "retry"
```

---

## 2.8 P2-4 · SKILL.md → Harness 迁移映射矩阵

| # | 元规则 | 来源位置 | 迁移去向 | 验证方式 |
|---|--------|----------|----------|----------|
| 1 | **五件套交接** | SKILL.md §1 | `PhaseExecutor._validate_delivery()` | UT: 交付件缺少任意要素 → 校验拒绝 |
| 2 | **P1/P2/P3 分级审核** | SKILL.md §2 | `AuditExecutor._parse_review_result()` | UT: 评分格式校验 |
| 3 | **不确定就提问** | SKILL.md §3 | 保留在 SOUL.md（行为公约，非流程） | —— |
| 4 | **代码合入放行信号** | SKILL.md §4 | `FinalCheckExecutor` 明确要求"LGTM/通过/可以合入"之一 | UT: 无放行信号 → 不放行 |
| 5 | **禁止表演性同意** | SKILL.md §5 | 保留在 SOUL.md（行为公约，非流程） | —— |
| 6 | **所有决策归档** | SKILL.md §6 | `DeliverExecutor` → `sessions_send(aeterna, ...)` 触发归档 | ST: 归档事件被记录 |
| 7 | **园长最终决策** | SKILL.md §7 | `ZooPipeline` 的 `_handle_cancel()` 只接受园长签名请求 | ST: 非园长取消被拒绝 |
| 8 | **对外输出安全** | SKILL.md §8 | 保留在 SOUL.md（行为公约，非流程） | —— |
| 9 | **TDD 开发铁则** | SKILL.md §9 | `DevelopExecutor._check_tdd_compliance()` | UT: 测试未先行 → 阻塞开发 |
| 10 | **工程开发标准流程** | SKILL.md §10 | `DevelopExecutor._invoke_coding_agent()` | UT: 开发路径合规检查 |
| 11 | **外骨骼调用规范** | SKILL.md §11 | `DevelopExecutor` 执行配置 | UT: 参数校验 |
| 12 | **全链路协同工作流** | SKILL.md §12 | **整条迁移到 ZooPipeline 的完整 FSM** | ST: 完整流程 E2E 测试 |
| 13 | **跨成员交互铁则** | SKILL.md §13 | `AgentSession.send()` 实现 | ST: 消息内容 `len < 200` 不写入 shared → 例外校验 |
| 14 | **工作区隔离铁则** | SKILL.md §14 | 保留在 SOUL.md（环境约束，非流程） | —— |

**迁移状态字段**：
- ✅ 已迁移 → 对应 Harness 代码已实现
- ⏳ 待迁移 → 尚未在 Harness 中落地的
- 🔒 保留 → 不迁移到代码（行为公约）

当前迁移矩阵状态：**全量 ⏳ 待迁移**（阶段 2 完成）

---

## 2.9 P2-5 · Session 生命周期管理

### Session 状态机

```
   启动
     │
     ▼
┌──────────┐  空闲超时(30min)  ┌──────────┐  园长/Panda 命令  ┌──────────┐
│  online  │ ──────────────→ │  idle   │ ──────────────→ │ sleeping │
│ (活跃)   │ ←─── 新消息 ──── │ (待机)  │                  │ (已休眠) │
└──────────┘                 └──────────┘                  └──────────┘
     │                            │
     │ 异常崩溃                    │ 10min 无唤醒
     ▼                            ▼
┌──────────┐                 ┌──────────┐
│   dead   │                 │ terminated│
│ (已死亡) │                 │ (已销毁) │
└──────────┘                 └──────────┘
```

### 各状态处理策略

| 状态 | 含义 | 通信能力 | 收件箱处理 | 自动转换 |
|------|------|----------|-----------|---------|
| **online** | 活跃工作中 | ✅ 可收发 | ✅ 可读写 | — |
| **idle** | 空闲待机 | ❌ 不主动收发 | ✅ 持续收件（消息堆积） | 新消息 → online |
| **sleeping** | 已休眠 | ❌ | ✅ 持续收件 | 园长/Panda 唤醒 → online |
| **dead** | 异常崩溃 | ❌ | ❌ | Panda 检测到 → terminated |
| **terminated** | 已销毁 | ❌ | ❌ | — |

### 销毁策略

| 触发条件 | 动作 | 影响 |
|----------|------|------|
| 空闲超过 30 分钟 | online → idle | 释放 token 上下文 |
| idle 超过 10 分钟且无新消息 | idle → sleeping | 回收进程资源 |
| sleeping 超过 24 小时 | sleeping → terminated | 销毁 session，清除 ZooMesh 元数据（保留 inbox） |
| 主动调用 `panda.shutdown(agent_id)` | 任意状态 → terminated | 立即销毁 |
| 进程崩溃超过 5 分钟未恢复 | dead → terminated | 保留 inbox 和 checkpoint，允许重建 session 恢复消费 |

---

## 审核响应汇总

| 审核项 | 严重度 | 状态 | 对应补丁 |
|--------|--------|------|----------|
| P1-1: inbox 消息丢失 | 🔴 P1 | ✅ 已修复 | §2.1 at-least-once 模型 |
| P1-2: 阻塞等待反模式 | 🔴 P1 | ✅ 已修复 | §2.2 事件驱动 + 降级链 |
| P1-3: 状态机缺陷 | 🔴 P1 | ✅ 已修复 | §2.3 完整 FSM + _decide_next 规则 |
| P1-4: Panda 权限模糊 | 🔴 P1 | ✅ 已修复 | §2.4 权限清单 + 仲裁流程 |
| P2-1: session 动态性 | 🟡 P2 | ✅ 已修复 | §2.5 Label 路由 |
| P2-2: Event Bus 写入冲突 | 🟡 P2 | ✅ 已修复 | §2.6 flock 文件锁 |
| P2-3: 回退无限循环 | 🟡 P2 | ✅ 已修复 | §2.7 回退计数器 |
| P2-4: 迁移缺映射 | 🟡 P2 | ✅ 已修复 | §2.8 完整迁移矩阵 |
| P2-5: session 生命周期 | 🟡 P2 | ✅ 已修复 | §2.9 状态机 + 销毁策略 |

---

> **设计者签名**: 阿尔法（玄龟）🐢  
> **版本**: v1.1  
> **状态**: ⏳ 待毒刺复审  
> **文件位置**: `framework/shared/alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md`

---

## 2.10 P2-N1 · 双重交付检测（Event Bus + inotify）

### 问题

AsyncDeliveryWatcher 只等待 Agent 主动发布 `file_delivered` 事件。Agent 可能忘了发或发失败。

### 方案：双重检测

```python
class DeliveryDetector:
    """
    双重交付检测器
    
    - 主检测：Event Bus 订阅 file_delivered 事件（Agent 主动通知）
    - 兜底检测：watchdog 监控 shared/ 目录文件变化（文件被动触发）
    - 任一路径首次触发即标记交付完成
    """
    
    def __init__(self, mesh: ZooMesh):
        self._watchers: Dict[str, DeliveryWatch] = {}
        self._mesh = mesh
        
        # 订阅 Event Bus
        mesh.event_bus.subscribe("file_delivered", self._on_event_delivery)
        
        # 启动 watchdog（可选，按需开启）
        self._watchdog_enabled = True
        self._start_file_watchdog()
    
    def _start_file_watchdog(self):
        """启动文件系统 inotify 监控"""
        import watchdog.observers
        observer = watchdog.observers.Observer()
        handler = DeliveryFileHandler(self)
        observer.schedule(handler, shared_dir, recursive=False)
        observer.start()
    
    def _on_event_delivery(self, event):
        """Event Bus 触发"""
        task_id = event["payload"]["task_id"]
        if task_id in self._watchers:
            self._watchers[task_id].mark_delivered(source="event_bus")
    
    def _on_file_created(self, path: str):
        """文件系统触发"""
        for task_id, watch in self._watchers.items():
            if watch.matches_pattern(path):
                watch.mark_delivered(source="watchdog")
                break
```

---

## 2.11 P2-N2 · 分阶段 session 路由策略

### 问题

Label 路由依赖 Agent 持久化 session（Phase 3），但 Phase 1-2 的 Agent 是 mode="run"，session 生命周期短。

### 方案：分阶段配置开关

```python
class SessionRouter:
    """
    分阶段 Session 路由器
    
    Phase 1-2：使用 sessions_list 动态查询 + 缓存
    Phase 3：切换到 Label 路由
    """
    
    def __init__(self, phase: str = "phase1"):
        self.phase = phase
        self._cache: Dict[str, str] = {}  # agent_id → session_key
    
    def resolve(self, agent_id: str) -> Optional[str]:
        if self.phase in ("phase1", "phase2"):
            return self._resolve_via_list(agent_id)
        else:
            return self._resolve_via_label(agent_id)
    
    def _resolve_via_list(self, agent_id: str) -> Optional[str]:
        """通过 sessions_list 查询最新活跃 session"""
        # 先查缓存
        if agent_id in self._cache:
            cached_key = self._cache[agent_id]
            # 验证是否仍然有效（可选）
            return cached_key
        
        # 实时查询
        sessions = sessions_list(kinds=["subagent"], agentId=agent_id, limit=1)
        if sessions and len(sessions) > 0:
            key = sessions[0].get("key")
            self._cache[agent_id] = key
            return key
        return None
    
    def _resolve_via_label(self, agent_id: str) -> Optional[str]:
        """OpenClaw label 路由（Phase 3+）"""
        label_map = {
            "alpha": "alpha-zoomesh",
            "weaver": "weaver-zoomesh",
            # ...
        }
        return label_map.get(agent_id)
    
    def connect(self, phase: str):
        """开发阶段切换，控制路由策略"""
        self.phase = phase
        self._cache.clear()
```

---

## 2.12 P2-N3 · 回退计数器重置 + 全局 rollback 保护

### 问题

回退到某阶段后，该阶段的 retry_count 应从 0 重新计数（因为是新输入），同时防止无限乒乓。

### 方案

```python
class Task:
    
    def record_rollback(self, from_phase: str, to_phase: str) -> str:
        """
        记录一次回退
        
        - from_phase 的 retry_count 递增
        - to_phase 的 retry_count 重置为 0（新输入新额度）
        - total_rollback_count 全局递增，防止无限乒乓
        """
        self.retry_count[from_phase] += 1
        self.retry_count[to_phase] = 0     # 重置目标阶段
        self.total_rollback_count += 1
        
        # 全局保护：总回退超过 10 次，强制 escalate
        if self.total_rollback_count > 10:
            return "escalate"
        
        # 阶段级保护
        max_r = self.MAX_RETRIES.get(from_phase, 3)
        if self.retry_count[from_phase] > max_r:
            return "escalate"
        
        return "retry"
```

---

## 2.13 P2-N4 · idle → online 触发机制

### 问题

Agent idle 时如何检测新消息并自动唤醒？

### 方案：inbox 文件系统事件驱动

Agent 不依赖自身心跳去检测 inbox。而是由 **ZooMesh 看门狗** 负责：

```python
class InboxWatcher:
    """
    Inbox 看门狗
    
    监控 zoomexh/inbound/<agent_id>/queue/ 目录的文件变化。
    当一个新的 msg_<uuid>.json 被写入时：
      1. 检查 Agent 当前状态
      2. 如果 Agent 是 idle/sleeping → 通过 Panda 发起唤醒
      3. 唤醒后 Agent 自动读取 inbox
    
    不依赖 Agent 自身的任何心跳或定时器。
    """
    
    def __init__(self, mesh: ZooMesh):
        self.mesh = mesh
        self._observer = Observer()
        self._handlers: Dict[str, InboxHandler] = {}
        
        for agent_id in REGISTRY:
            inbox_dir = f"zoomesh/inbound/{agent_id}/queue/"
            handler = InboxHandler(agent_id, mesh)
            self._handlers[agent_id] = handler
            self._observer.schedule(handler, inbox_dir, event_filter=IN_CREATE)
        
        self._observer.start()

class InboxHandler(FileSystemEventHandler):
    """当新消息到达 inbox 时：唤醒 Agent"""
    
    def __init__(self, agent_id: str, mesh: ZooMesh):
        self.agent_id = agent_id
        self.mesh = mesh
    
    def on_created(self, event):
        if event.src_path.endswith(".json"):
            status = self.mesh.get_agent_status(self.agent_id)
            if status in ("sleeping", "idle"):
                # 通过 Panda 发送唤醒通知
                self.mesh.panda.notify(
                    f"{self.agent_id} 有新消息，请唤醒"
                )
```

---

## 2.14 复审响应汇总（最终版）

| 审核项 | 严重度 | 轮次 | 状态 | 对应补丁 |
|--------|--------|------|------|----------|
| P1-1: inbox 消息丢失 | 🔴 P1 | 第1轮 | ✅ 已通过 | §2.1 at-least-once 模型 |
| P1-2: 阻塞等待反模式 | 🔴 P1 | 第1轮 | ✅ 已通过 | §2.2 事件驱动 + 降级链 |
| P1-3: 状态机缺陷 | 🔴 P1 | 第1轮 | ✅ 已通过 | §2.3 完整 FSM |
| P1-4: Panda 权限模糊 | 🔴 P1 | 第1轮 | ✅ 已通过 | §2.4 权限清单 |
| P2-1: session 动态性 | 🟡 P2 | 第1轮 | ✅ 已通过 | §2.5 分阶段路由 |
| P2-2: Event Bus 写入冲突 | 🟡 P2 | 第1轮 | ✅ 已通过 | §2.6 flock 文件锁 |
| P2-3: 回退无限循环 | 🟡 P2 | 第1轮 | ✅ 已通过 | §2.7 回退计数器 |
| P2-4: 迁移缺映射 | 🟡 P2 | 第1轮 | ✅ 已通过 | §2.8 迁移矩阵 |
| P2-5: session 生命周期 | 🟡 P2 | 第1轮 | ✅ 已通过 | §2.9 状态机 |
| P2-N1: 事件单点依赖 | 🟡 P2 | 第2轮 | ✅ 已修复 | §2.10 双重检测 |
| P2-N2: Label 鸡生蛋 | 🟡 P2 | 第2轮 | ✅ 已修复 | §2.11 分阶段路由 |
| P2-N3: 回退计数重置 | 🟡 P2 | 第2轮 | ✅ 已修复 | §2.12 重置+全局保护 |
| P2-N4: idle 触发不明 | 🟡 P2 | 第2轮 | ✅ 已修复 | §2.13 watchdog 事件驱动 |

---

## 2.15 毒刺最终结论

> 🦂 **条件性通过。** 4 个 P1 的架构级缺陷已修复，核心设计可落地。4 个新 P2 不阻断实施，但建议在阶段 1 开发前明确处理方案（特别是 P2-N1 和 P2-N2，影响 Harness 基础运行的可靠性）。可以送园长终审了。

---

> **设计者签名**: 阿尔法（玄龟）🐢  
> **审核者签名**: 毒刺（蝎子）🦂  
> **版本**: v1.1-final  
> **状态**: ✅ 审核通过，已提交 → 园长终审  
> **文件位置**: `framework/shared/alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md`
