# Pipeline V2 演进设计方案

## What — 要做什么

基于当前 Pipeline V1（ZooMesh + InboxWatcher + StateMachine），解决三个核心问题：

1. **Agent 唤醒断点**：Pipeline 发 inbox 指令后，没有桥接机制通知 OpenClaw Agent 去干活
2. **类型 3 误推进**：InboxWatcher 把 pipeline 指令误当作 phase_complete，自动推进流水线
3. **多位并发乱序**：无 agent 忙碌检测，多个需求同时到达时同一个人会堆满 inbox

同时将 feida-zoo SKILL 中定义的元规则（五件套、P1/P2/P3 审计分级、明确放行信号、TDD）固化为 Pipeline 的标准约束。

---

## Why — 为什么要做

| 问题 | 当前表现 |
|------|---------|
| 通知断点 | 问题状态变"设计中"了但不触发干活，需要人工发现 |
| 假性推进 | Pipeline 走到 design 就停住了（被 StateMachine 拦住），没拦住就一路推进到底 |
| 缺乏排队 | 两个需求同时进来，第二个悄无声息丢掉了 |
| 审查无标准 | 审计结果走聊天消息，Pipeline 读不懂 |

---

## Tradeoff — 做过的权衡

| 权衡 | 选型 | 理由 |
|------|------|------|
| 桥接方式 | Daemon HTTP POST → Plugin HTTP (18794) | OpenClaw gateway 18789 路由不可扩展 |
| 审查传递 | `review_pl_xxx.json` 结构化文件 | 持久、程序化可读、文件名+内容双锁隔离 |
| 并发策略 | 排队（串行派单） | 避免 agent 上下文切换，保证单任务完成效率 |
| TDD 实现 | 状态机拆阶段（develop_wt/review_test/develop_code） | 优于 sessions_send 子流程，不依赖记忆 |

---

## 讨论确认（审计前已确认）

1. **桥接端口**：Pipeline plugin 在 18794 起 HTTP server，ZooMesh daemon POST 至此
2. **毒刺明确给结果**：review_pl_xxx.json 的 result 毒刺手动填 pass/reject
3. **优先级插队不断当前**：pending 队列按优先级排序，当前任务不中断

---

## 详细设计

### 1. 完整 Pipeline 阶段定义

#### PHASES

```python
PHASES = [
    "request",         # 📥 请求接收（ZooMesh 自动）
    "validate",        # 🔍 需求验证（Alpha）
    "design",          # 🎨 设计方案（Alpha）
    "ui_design",       # 🎨 界面方案（Alpha）
    "review",          # 📋 设计审查（Duci）
    "develop_wt",      # 🧪 写测试用例（Alpha）
    "review_test",     # 📋 测试用例审查（Duci）
    "develop_code",    # 🔧 写代码+自测（Alpha）
    "test",            # 🧪 第二轮测试（Duci）
    "audit",           # 🔐 安全审计（Duci）
    "final_check",     # ✅ 最终验收（Panda 自动）
    "deliver",         # 🚀 发布（Panda 自动）
    "done",            # 🏁 完成
    "cancelled",       # ❌ 取消
]
```

#### PHASE_TRANSITION_MAP（完整版）

```python
PHASE_TRANSITION_MAP = {
    "request":     "validate",
    "validate":    "design",
    "design":      "ui_design",
    "ui_design":   "review",
    "review":      "develop_wt",     # 设计通过 → 写测试用例
    "develop_wt":  "review_test",     # 写完用例 → 毒刺审用例
    "review_test": "develop_code",    # 用例通过 → 写代码
    "develop":     "develop_wt",      # 旧数据兼容（见 5.6）
    "develop_code":"test",            # 代码通过 → 毒刺第二轮测试
    "test":        "audit",
    "audit":       "final_check",
    "final_check": "deliver",
    "deliver":     "done",
}
```

#### PHASE_DEFAULT_AGENT（完整版）

```python
PHASE_DEFAULT_AGENT = {
    "request":     "panda",
    "validate":    "alpha",
    "design":      "alpha",
    "ui_design":   "alpha",
    "review":      "duci",
    "develop_wt":  "alpha",
    "review_test": "duci",
    "develop_code":"alpha",
    "test":        "duci",
    "audit":       "duci",
    "final_check": "panda",
    "deliver":     "panda",
}
```

#### StateMachine 新增转换

```python
TRANSITIONS = {
    # ...原有映射保持不变，新增：
    "develop_wt":   ["review_test", "cancelled", "timed_out", "escalated"],
    "review_test":  ["develop_code", "develop_wt", "cancelled", "timed_out", "escalated"],
    "develop_code": ["test", "cancelled", "timed_out", "escalated"],
    "review":       ["develop_wt", "design", "cancelled", "timed_out", "escalated"],  # 已支持回退
    "test":         ["audit", "develop_code", "cancelled", "timed_out", "escalated"],  # 已支持回退
}
```

#### emoji_map

```python
emoji_map = {
    "request": "📥", "validate": "🔍", "design": "🎨", "ui_design": "🎨",
    "review": "📋", "develop_wt": "🧪", "review_test": "📋", "develop_code": "🔧",
    "test": "🧪", "audit": "🔐", "final_check": "✅", "deliver": "🚀",
    "done": "🏁", "cancelled": "❌",
}
```

---

### 2. Types 1/2/3 消息路由重写

#### 当前问题（审计 P1-1 指出）

当前类型 3 用 `pipeline_id in body` 模糊匹配，把 Pipeline 指令误当作 phase_complete 自动推进。设计方案草稿用 `agent_id != "panda"` 判断，仍然不够精确。

#### 修复：白名单信号匹配

```python
# 明确的推进信号——只有这些词出现才算 phase_complete
PHASE_COMPLETE_SIGNALS = {"phase_complete:", "PI_DONE:", "pipeline_ack:"}

def _on_wakeup_callback(agent_id: str):
    files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        return

    for msg_file in files:
        # 静态检查：跳过已处理文件（mtime <= last_checked 的已在 InboxWatcher 层过滤）
        with open(msg_file) as f:
            msg = json.load(f)
        body = msg.get("body", "")

        # 类型 1：pipeline_request — 仅 Panda 处理
        if _is_pipeline_request(body, msg.get("from", "")):
            _handle_pipeline_request(body, agent_id)
            _move_to_processed(msg_file)
            continue

        # 类型 2：明确的 phase_complete 信号
        if any(sig in body for sig in PHASE_COMPLETE_SIGNALS):
            _handle_phase_complete(body, agent_id)
            _move_to_processed(msg_file)
            continue

        # 类型 3：删掉。所有推进必须有明确信号。
        # 非推进消息 → 仅做桥接通知
        _send_agent_notification(agent_id, body)
        # 注意：通知类消息不移入 processed，留作重试/回溯
```

#### 消息处理确认（审计 P1-2 指出）

处理后移入 `processed/` 子目录：

```python
def _move_to_processed(msg_file: Path):
    """处理完毕后移入 processed 子目录"""
    processed_dir = msg_file.parent / "processed"
    processed_dir.mkdir(exist_ok=True)
    msg_file.rename(processed_dir / msg_file.name)
```

这样不会有消息丢失，即使 daemon 重启也能从 queue/ 里重放未处理消息。

---

### 3. ZooMesh → OpenClaw 桥接

#### Daemon 出站 HTTP POST

消息类型为非 phase_complete 时，向 plugin HTTP 端口发通知：

```python
_NOTIFY_LOG = set()  # 去重索引

def _send_agent_notification(agent_id: str, body: str):
    """向 OpenClaw 发送 agent 通知"""
    notify_key = f"{agent_id}:{hash(body)}"
    if notify_key in _NOTIFY_LOG:
        return  # 已通知过，幂等

    pipeline_id = _extract_pipeline_id(body)
    phase = _extract_phase(body)
    payload = {
        "agent": agent_id,
        "pipeline_id": pipeline_id,
        "phase": phase,
        "message": body[:500],
    }

    notify_url = os.environ.get("ZOO_NOTIFY_URL",
        "http://127.0.0.1:18794/api/zoo-notify")

    for attempt in range(3):
        try:
            resp = requests.post(notify_url, json=payload, timeout=3)
            if resp.status_code == 200:
                _NOTIFY_LOG.add(notify_key)
                return
        except requests.RequestException:
            time.sleep(2 ** attempt)  # 指数退避：1s → 2s → 4s

    # 3 次都失败，打日志，消息留在 inbox 等心跳补拉
    logger.warning(f"通知 {agent_id} 失败（3次重试），消息保留 inbox")
```

#### Pipeline Plugin HTTP (18794)

Pipeline plugin（TypeScript）在 `gateway_start` 钩子中另起 HTTP server：

```
POST /api/zoo-notify
{
  "agent": "alpha",
  "pipeline_id": "pl_bb50c26a",
  "phase": "design",
  "message": "[Pipeline] Phase: design..."
}
```

Plugin 收到后用 `sessions_send` 通知对应的 agent session。

#### 配置项

```python
ZOO_NOTIFY_PORT = os.environ.get("ZOO_NOTIFY_PORT", "18794")  # 审计 P3-1
ZOO_NOTIFY_RETRIES = 3
ZOO_NOTIFY_TIMEOUT = 3
```

---

### 4. 排队机制

#### Agent 忙碌检测

```python
def _agent_available(agent_id: str, phase: str) -> bool:
    reqs = _load_requirements()
    active = [r for r in reqs
              if r.get("assignee") == agent_id
              and r.get("status") == phase
              and r.get("status") not in ("done", "cancelled")]
    return len(active) == 0
```

#### Pending 队列结构（审计 P2-2）

```json
// zoomesh/pipeline/pending.json
[
  {
    "pipeline_id": "pl_xxx",
    "phase": "design",
    "assignee": "alpha",
    "priority": "P1",
    "title": "需求标题",
    "created_at": "2026-05-16T12:00:00"
  }
]
```

优先级排序规则：`P0 > P1 > P2 > P3 > 无`，同级按 `created_at` 升序。

#### 状态机联动

```
request → validate（自动）
   → 下一阶段的 agent 忙碌？→ 是 → 入 pending 队列
                         → 否 → 发指令

phase_complete 回复后
   → 推进到下一阶段
   → 检查 pending 队列中该 agent 是否有同阶段任务
   → 有 → 弹出优先级最高的 → 发指令
   → 无 → 空闲等待
```

#### 驳回重做时的排队行为

review → reject → 回退 design 或 develop_wt：
- 驳回任务插到该 agent pending 队列**队首**（优先级+1）
- 不中断当前正在进行的任务

---

### 5. 审查结果标准化

#### review_pl_xxx.json 生命周期（审计 P2-3）

```
推进到 review/audit/review_test 阶段时
  → daemon 自动创建 review/review_test_pl_xxx.json
  → 初始状态：{ "status": "pending" }

Agent（毒刺）审查完毕后填写 result
  → 写入 { "status": "completed", "result": "pass/reject", "comments": [...] }

daemon 收到 phase_complete 时读取 review 文件
  → result == "pass" → 正常推进
  → result == "reject" → StateMachine 回退
```

```json
// zoomesh/pipeline/review_pl_bb50c26a.json
{
  "pipeline_id": "pl_bb50c26a",
  "phase": "review",
  "status": "completed",
  "result": "pass",
  "comments": [
    {"severity": "P1", "text": "阻断: 功能错误/安全问题"},
    {"severity": "P2", "text": "重要: 测试覆盖不足"},
    {"severity": "P3", "text": "建议: 命名优化"}
  ],
  "reviewer": "duci",
  "reviewed_at": "2026-05-16T12:00:00"
}
```

#### Auto decision table

| result | StateMachine transition | 行为 |
|--------|------------------------|------|
| `pass` | 正常推进到下一阶段 | 发 pending 队列检查 |
| `reject` | 按阶段回退 | `review→design`, `review_test→develop_wt`, `test→develop_code` |

> result 由毒刺手动判定，系统不根据 P 级自动推定。

---

### 6. 并发修复

| 修复 | 等级 | 做法 |
|------|------|------|
| InboxWatcher 只读最新文件 | P1 | callback 循环处理所有未处理消息文件 → processed 目录 |
| Dashboard issues.json 写锁 | P2 | `threading.RLock` 保护 `_save_issues()` |
| requirements.json 写安全 | P2 | 已在单线程中，保持现状 |
| Pipeline state 文件 | P1 | 每个任务独立文件，不需修复 |
| mesh.send() 写 inbox | P1 | 每条消息不同 UUID，不需修复 |

---

### 7. 旧数据兼容（审计 P3-2）

`requirements.json` 中可能存在 `status: "develop"` 的旧任务。迁移逻辑：

```python
def _migrate_legacy_develop(req: dict) -> dict:
    """旧 develop 阶段 → 映射为 develop_wt"""
    if req.get("status") == "develop":
        req["status"] = "develop_wt"
        req["phase"] = "develop_wt"
    return req
```

在 `_load_requirements()` 调用 `_save_requirements()` 之前自动执行此迁移。

---

### 8. 各阶段指令模板

**设计阶段（design/validate）附五件套模板**

```text
【设计产出要求】
- What: 具体要做什么改动
- Why: 为什么要这么做（背景、解决的问题）
- Tradeoff: 放弃了什么方案，做了什么权衡
- Open Questions: 有什么不确定的点、遗留问题
- Next Action: 希望审计方重点审查什么
```

**develop_wt 指令**

```text
【TDD - 写测试用例】
请为当前需求编写测试用例（单元测试 + 集成测试）
完成后回复 phase_complete:pl_xxx

【注意】
- 测试用例需覆盖所有验收标准
- 下一步会由毒刺评审用例
```

**develop_code 指令**

```text
【TDD - 写实现代码】
测试用例已通过毒刺评审，请编写实现代码
自测所有用例通过后回复 phase_complete:pl_xxx
```

---

## 完整工作流示意

```
你在仪表盘创建问题
  ↓
📥 request     ZooMesh 自动 → 写 requirements.json
🔍 validate    Alpha 验证需求 → 五件套输出
🎨 design      Alpha 设计方案 → 五件套输出
🎨 ui_design   Alpha 界面方案
📋 review      毒刺审查设计  → review_pl_xxx.json
                    ├─ pass ──→ 下一阶段
                    └─ reject ─→ 回退 design
🧪 develop_wt  Alpha 写测试用例
📋 review_test 毒刺审测试用例 → review_test_pl_xxx.json
                    ├─ pass ──→ 下一阶段
                    └─ reject ─→ 回退 develop_wt
🔧 develop_code Alpha 写代码 + 自测
🧪 test        毒刺第二轮测试 → test_pl_xxx.json
                    ├─ pass ──→ 下一阶段
                    └─ reject ─→ 回退 develop_code
🔐 audit       毒刺安全审计
✅ final_check  Panda 自动
🚀 deliver     Panda 自动
🏁 done
```

---

## 交付物清单

| # | 交付物 | 涉及文件 | 负责人 |
|---|--------|---------|--------|
| 1 | PHASES + PHASE_TRANSITION_MAP + PHASE_DEFAULT_AGENT + emoji_map 更新 | zoo_mesh_daemon.py, state_machine.py | Alpha |
| 2 | Types 1/2/3 消息路由重写（白名单信号） | zoo_mesh_daemon.py | Alpha |
| 3 | InboxWatcher 全文件循环 + processed 目录 | inbox_watcher.py, zoo_mesh_daemon.py | Alpha |
| 4 | Daemon 出站 HTTP 通知（含重试+去重） | zoo_mesh_daemon.py | Alpha |
| 5 | Pipeline Plugin HTTP (18794) 接收端 | pipeline plugin (TS) | Alpha |
| 6 | 排队机制（_agent_available + pending.json） | zoo_mesh_daemon.py | Alpha |
| 7 | review_pl_xxx.json 生命周期 | zoo_mesh_daemon.py | Alpha |
| 8 | 五件套/TDD 指令模板固化 | zoo_mesh_daemon.py | Alpha |
| 9 | 旧 develop 数据迁移兼容 | zoo_mesh_daemon.py | Alpha |
| 10 | Dashboard 写锁 | app_enhanced.py | Alpha |
