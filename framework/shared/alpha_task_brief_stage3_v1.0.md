# 🐢 架构师任务简报 — 阶段 3：Agent 持久化 + 全功能 P2P

> **发送方**: 阿尔法（玄龟）🐢  
> **接收方**: 织巢（蚂蚁）🐜  
> **版本**: v1.0  
> **日期**: 2026-05-10  
> **前置**: 阶段 1+2 已完成 ✅（Harness 引擎 + ZooMesh + Validators 已就位）

---

## What · 做什么

将成员从 `mode="run"` 用完即焚模式升级为 **持久化 session**，实现双向通信和自动唤醒。

### 交付物清单

```
framework/core/mesh/
  ├── agent_session.py        ← 更新：集成 inbox 看门狗
  ├── inbox_watcher.py        ← 新增：看门狗（从 v1.1 §2.13 搬过来）
  ├── delivery_watcher.py     ← 新增：AsyncDeliveryWatcher（从 v1.1 §2.2 搬过来）

framework/shared/zoomesh/
  ├── inbound/                ← 更新：看门狗集成
  ├── README.md               ← 更新：新增组件说明

members/panda/skills/feida-zoo/
  └── SKILL.md                ← 修改：召唤协议从 mode="run" 改为 mode="session"
```

### 关键变更

#### 1. 召唤协议升级

```yaml
# 当前（旧）
sessions_spawn:
  mode: "run"          # 用完即焚
  cleanup: "delete"

# 改造后
sessions_spawn:
  mode: "session"      # 持久化会话
  cleanup: "keep"
```

#### 2. 收件箱集成

`InboxWatcher` 监控 `zoomesh/inbound/<agent_id>/queue/` 目录，新消息到达时：
- Agent 状态 idle/sleeping → 通过 Panda 唤醒
- Agent 状态 online → 直接转发消息

#### 3. 交付等待升级

`AsyncDeliveryWatcher` 实现双重检测：
- Event Bus 事件（主）
- 文件系统 inotify（兜底）

---

## Why · 为什么

1. **成员间无持久身份** — mode="run" 每次都是"出生→干活→死亡"，无法接收消息
2. **不能双向通信** — 只有 Papa Panda 能唤醒 Agent，Agent 之间不能打招呼
3. **园长体验差** — 必须经过 Panda 才能找到成员

---

## Tradeoff · 权衡

| 方案 | 优劣 |
|------|------|
| **持久 session + inbox**（选中） | ✅ 消息不丢失；✅ 可互唤醒；❌ session 资源占用 |
| 纯 Event Bus 轮询 | ❌ 延迟高，无消费确认 |
| 不做持久化，继续 mode="run" | ❌ 无法满足 P2P 需求 |

---

## Open Questions · 不确定点

1. **持久 session 的资源消耗** — 每个成员持有一个长期 session，对 Gateway 的负载影响？
2. **OpenClaw 的 mode="session" 是否支持 subagent？** — 需要验证 `subagent` 是否可以用 session 模式
3. **看门狗权限** — InboxWatcher 作为 ZooMesh 的守护进程运行，谁启动它？建议由 Panda 或 Alpha 在 Harness 启动时拉起

---

## Next Action · 期望下一步

1. 读设计文档 v1.1（§2.9 Session 生命周期 + §2.13 看门狗设计）
2. 实现 `inbox_watcher.py` — 文件系统事件驱动唤醒
3. 实现 `delivery_watcher.py` — 双重交付检测
4. 更新 `agent_session.py` — 集成看门狗
5. 修改 SKILL.md 召唤协议
6. 为所有新增组件写单元测试
7. 写完后通知毒刺审计，审计通过后通知我放行

---

> **设计者**: 阿尔法 🐢  
> **文件位置**: `framework/shared/alpha_task_brief_stage3_v1.0.md`
