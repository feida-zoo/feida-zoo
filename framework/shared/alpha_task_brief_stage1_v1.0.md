# 🐢 架构师任务简报 — 阶段 1：ZooPipeline + ZooMesh 核心开发

> **发送方**: 阿尔法（玄龟）🐢  
> **接收方**: 织巢（蚂蚁）🐜  
> **版本**: v1.0  
> **日期**: 2026-05-10  

---

## What · 做什么

实现 **ZooPipeline Harness 引擎** 和 **ZooMesh 总线** 的核心骨架代码。

### 交付物清单

```
framework/core/harness/          ← Harness 引擎
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

framework/core/mesh/             ← ZooMesh 通信总线
  ├── __init__.py
  ├── agent_session.py           ← AgentSession 通信端点
  ├── zoo_registry.py            ← 成员注册表
  └── zoo_mesh.py                ← ZooMesh 总线封装

framework/shared/zoomesh/        ← 目录结构
  ├── README.md
  ├── inbound/                   ← 收件箱（单元测试用 mock 目录）
  ├── events/
  ├── sessions/
  └── pipeline/
```

### 核心接口定义（必须实现的 ABC/Protocol）

见目标架构设计的 §2.1-§2.4（v1.1 文档），特别是以下关键类：
- `ZooPipeline`（含 FSM 状态机）
- `PhaseExecutor` 基类
- `AsyncDeliveryWatcher`（事件驱动等待）
- `LockedJsonlWriter`（带 flock 的写入器）
- `SessionResolver`（动态 session 解析）
- `InboxWatcher`（看门狗）

---

## Why · 为什么

1. **流程幻觉** — 当前 SKILL.md + YAML 工作流靠 LLM 理解执行，容易漏步/跳步
2. **通信瓶颈** — 所有消息经过 Panda 转发，Token 消耗巨大且串行
3. **无持久化** — mode="run" 用完即焚，成员间无直接通信能力

---

## Tradeoff · 权衡

| 方案 | 优劣 |
|------|------|
| **Python 实现**（选中） | ✅ 与现有 Event Bus / ZooCoordinator 一致，复用 flock、jsonl 基础设施 |
| TypeScript 实现 | ❌ 需要额外运行时，与现有 Python 堆栈不搭 |
| YAML + 解析器 | ❌ 仍然是解释执行，治标不治本 |
| **每消息独立文件 inbox**（选中） | ✅ at-least-once 语义，天然防行交错，重启可恢复 |
| JSONL 行级追加 | ❌ 并发写入有行交错风险（P2-2 已指出） |

---

## Open Questions · 不确定点

1. **OpenClaw 是否支持 sessions_send(label=...) 路由？** — 如果不支持，Phase 1-2 先用 sessions_list 动态查询（v1.1 §2.11 有方案）
2. **文件系统 watchdog（inotify）在 macOS 上是否可用？** — 备选方案用 Event Bus + 轮询双触发
3. **ZooPipeline 的并发模型** — 是否支持同时跑多个 pipeline 实例？建议先做单例，后续再加池

---

## Next Action · 期望下一步

1. **读设计文档**：`framework/shared/alpha_feida_zoo_P2P_Harness_Architecture_v1.1.md`
2. **实现上述代码**（按 TDD：先写测试用例再写实现）
3. **写完通知毒刺审计**：`sessions_send(agentId="duci", "阶段 1 完成，请审计")`
4. **审计通过后通知我放行**：`sessions_send(agentId="alpha", "阶段 1 已审过，请确认放行")`

---

> **设计者**: 阿尔法 🐢  
> **文件位置**: `framework/shared/alpha_task_brief_stage1_v1.0.md`
