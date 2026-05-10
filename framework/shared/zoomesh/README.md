# ZooMesh 目录结构

飝龘动物园 V2 成员间通信收件箱/事件总线目录。

## 目录说明

```
zoomesh/
├── inbound/       ← 收件箱（每 Agent 一个子目录）
│   └── <agent_id>/
│       ├── queue/     ← 待消费消息（msg_<uuid>.json）
│       ├── dlq/       ← 死信队列
│       ├── checkpoint.json ← 消费偏移
│       └── config.json     ← 投递配置
├── events/        ← Event Bus 持久化事件日志
├── sessions/      ← Session 状态记录
└── pipeline/      ← Pipeline 状态快照
```

## 设计约束

- 每消息独立文件，原子写入（temp + rename）
- at-least-once 投递语义
- 消费方需自行处理幂等性（msg id 去重）
