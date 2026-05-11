# 🐢 Zoo Pipeline 插件 + ZooMesh 聊天室 — 设计文档 v1.0

> **设计者**: 阿尔法 🐢
> **状态**: 待审计
> **日期**: 2026-05-11

---

## 1. 概述

### 1.1 目标

在 OpenClaw 上构建一个名为 `zoo-pipeline` 的 TypeScript 插件，实现：

1. **任务消息拦截** — 园长发的工单消息被 `inbound_claim` 拦截，转由 Pipeline 编排
2. **角色权限约束** — 每个 agent 只能使用自己角色对应的工具（alpha 不能写代码、weaver 是工程师、duci 只读审计）
3. **Pipeline 常驻控制器** — 网关启动时自动拉起编排进程
4. **ZooMesh 聊天室** — 仪表盘上的全员聊天室不走 QQ，走 ZooMesh 总线

### 1.2 核心原则

- **编排权归控制器** — 代理不做编排，只执行分派
- **权限硬约束** — 工具 allow/deny 由 OpenClaw 网关强制执行，代理自身无法绕过
- **通信去中心化** — 成员间通信走 ZooMesh，不走外部聊天通道

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                OpenClaw Gateway                      │
│                                                      │
│  ┌────────────────────────────────────────────┐     │
│  │         zoo-pipeline 插件 (TypeScript)      │     │
│  │                                              │     │
│  │  gateway_start ─→ 启动 Pipeline 控制器      │     │
│  │  inbound_claim ─→ 拦截任务类消息             │     │
│  │  gateway_stop  ─→ 优雅关闭                   │     │
│  └────────────────────────────────────────────┘     │
│                                                      │
│  Agent 配置 (tools.allow / tools.deny)              │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐          │
│  │alpha │  │weaver│  │ duci │  │ gulu │ ...        │
│  │ 🐢   │  │ 🐜   │  │ 🦂   │  │ 🟢   │          │
│  └──────┘  └──────┘  └──────┘  └──────┘          │
└─────────────────────────────────────────────────────┘
         │                    ▲
         ▼                    │
┌────────────────────────────────────────────────────┐
│              外部 Python 进程                       │
│                                                     │
│  ZooMesh (P2P 消息总线)                             │
│  ├── inbox_watcher     ─ 收件监控                   │
│  ├── delivery_watcher  ─ 交付监控                   │
│  ├── chat/              ─ 聊天室消息持久化           │
│  └── mesh API          ─ HTTP 接口供仪表盘调用      │
│                                                     │
│  Zoo Dev-Center (仪表盘)                            │
│  ├── 看板 / 统计 / Git 时间线                        │
│  ├── 聊天室面板 (通过 ZooMesh HTTP API)             │
│  └── SSE 实时更新                                    │
└─────────────────────────────────────────────────────┘
```

### 2.1 消息流（完整链路）

```
园长发消息 → QQ → OpenClaw

① inbound_claim hook 拦截
   判断: 是任务指令? → 转 Pipeline 控制器
         是普通聊天? → 放行进 alpha 会话

② Pipeline 控制器创建工单
   → ZooMesh.publish("task.created", {task_id, desc, requester})
   → 写入 task_tracker.json

③ 控制器评估工单类型 → 分派设计阶段
   → ZooMesh.send("alpha", "【设计任务】需求: xxx")

④ alpha 🐢 完成设计
   → ZooMesh.publish("phase.design_complete", {task_id, doc_path})

⑤ 控制器收到事件 → 进入审计阶段
   → ZooMesh.send("duci", "【审计任务】审核设计: xxx")

⑥ duci 🦂 完成审计
   → ZooMesh.publish("phase.audit_complete", {task_id, result})

⑦ 控制器判断:
   - 通过 → ZooMesh.send("weaver", "【开发任务】按设计实现: xxx")
   - 驳回 → ZooMesh.send("alpha", "【设计返工】审计意见: xxx")

⑧ weaver 🐜 完成开发
   → ZooMesh.publish("phase.develop_complete", {task_id})

⑨ 控制器通知园长 "完工"
   → 通过 message_sending hook 回复
```

---

## 3. 插件文件结构

```
plugins/zoo-pipeline/
├── package.json
├── openclaw.plugin.json
├── tsconfig.json
└── src/
    ├── index.ts                # 插件入口
    ├── pipeline-controller.ts  # 编排控制器（常驻逻辑）
    ├── hooks/
    │   ├── inbound-claim.ts    # 消息拦截 hook
    │   └── gateway-lifecycle.ts # 网关生命周期 hook
    ├── types.ts
    └── utils.ts
```

### 3.1 package.json

```json
{
  "name": "@feida-zoo/zoo-pipeline",
  "version": "1.0.0",
  "type": "module",
  "openclaw": {
    "extensions": ["./src/index.ts"],
    "compat": {
      "pluginApi": ">=2026.3.24-beta.2",
      "minGatewayVersion": "2026.3.24-beta.2"
    }
  }
}
```

### 3.2 openclaw.plugin.json

```json
{
  "id": "zoo-pipeline",
  "name": "Zoo Pipeline",
  "description": "飝龘动物园任务编排与消息拦截插件",
  "hooks": {
    "allowConversationAccess": true
  }
}
```

### 3.3 src/index.ts — 插件入口

```typescript
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { registerLifecycleHooks } from "./hooks/gateway-lifecycle";
import { registerInboundClaim } from "./hooks/inbound-claim";

export default definePluginEntry({
  id: "zoo-pipeline",
  name: "Zoo Pipeline",
  register(api) {
    // 注册网关生命周期 hook
    registerLifecycleHooks(api);
    
    // 注册消息拦截 hook
    registerInboundClaim(api);
    
    api.logger.info("🐢 Zoo Pipeline 插件已注册");
  },
});
```

### 3.4 src/hooks/gateway-lifecycle.ts

```typescript
import { type PluginAPI } from "openclaw/plugin-sdk/plugin-entry";

let controllerProcess: any = null;

export function registerLifecycleHooks(api: PluginAPI): void {
  api.on("gateway_start", async () => {
    api.logger.info("🐢 Pipeline 控制器启动中...");
    
    // 启动 ZooMesh 看门狗（通过 exec 拉起 Python 进程）
    const { exec } = await import("node:child_process");
    controllerProcess = exec(
      "python3 /Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py",
      { env: { ...process.env, PYTHONPATH: "/Users/zoo/workspace/code/feida_zoo/framework" }},
    );
    
    controllerProcess.stdout?.on("data", (d: Buffer) => api.logger.debug(d.toString()));
    controllerProcess.stderr?.on("data", (d: Buffer) => api.logger.warn(d.toString()));
    
    api.logger.info("✅ Pipeline 控制器已启动");
  });
  
  api.on("gateway_stop", async () => {
    if (controllerProcess) {
      controllerProcess.kill();
      controllerProcess = null;
      api.logger.info("🛑 Pipeline 控制器已停止");
    }
  });
}
```

### 3.5 src/hooks/inbound-claim.ts

```typescript
import { type PluginAPI } from "openclaw/plugin-sdk/plugin-entry";

const TASK_PATTERNS = [
  /做(一[下个]?|完[成善]?)/,
  /修(一[下]?|改|复)/,
  /设计|开发|实现|审计|审核|交付/,
  /工单|任务|需求/,
];

function isTaskMessage(text: string): boolean {
  return TASK_PATTERNS.some((p) => p.test(text));
}

export function registerInboundClaim(api: PluginAPI): void {
  api.on(
    "inbound_claim",
    async (event) => {
      const text = event.content || "";
      
      if (!isTaskMessage(text)) {
        return; // 普通聊天 → 放行进 agent 会话
      }
      
      api.logger.info(`🚀 拦截到任务消息: "${text.slice(0, 60)}..."`);
      
      // 返回 claim 结果 → 消息不走 agent 会话，转 Pipeline
      return {
        claim: true,
        syntheticReply: "🐢 已收到工单，正在评估并分派...",
      };
    },
    { priority: 80 },
  );
}

// 注意: 此处是轻量拦截。完整编排逻辑在 Pipeline 控制器中
// 控制器监听 inbound_claim 事件后接管后续编排
```

---

## 4. Agent 权限约束配置

### 4.1 各角色工具范围

| Agent | 角色 | 允许的工具 | 禁止的工具 |
|-------|------|-----------|-----------|
| alpha 🐢 | 架构师 | `read`, `web_fetch`, `memory_*`, `sessions_send`, `message`, `image`, `write`（仅写 .md 文件） | `exec`, `git_*`, `edit`（代码）, `file_write`（代码） |
| weaver 🐜 | 工程师 | `read`, `write`, `edit`, `exec`, `git_*`, `file_*`, `sessions_send`, `sessions_spawn` | 无（工程师需要全工具） |
| duci 🦂 | 审计师 | `read`, `exec`（只读）, `sessions_*`, `memory_*`, `web_fetch` | `write`, `edit`, `git_*`, `file_write`, `message` |
| gulu 🟢 | 画师 | `read`, `image`, `write`（图片/资源） | `exec`, `git_*`, `edit` |
| aeterna 🪨 | 史官 | `read`, `memory_*`, `write`（memory 文件） | `exec`, `git_*`, `edit`, `file_write` |
| panda 🐼 | 调度者 | 全工具 | 无 |

### 4.2 OpenClaw 配置示例

```json5
{
  "agents": {
    "list": [
      {
        "id": "alpha",
        "tools": {
          "deny": [
            "exec", "git_*", "file_write", "file_fetch",
            "edit", "browser", "process"
          ]
        }
      },
      {
        "id": "weaver",
        "tools": {
          // 工程师不需要 deny，需要全工具
        }
      },
      {
        "id": "duci",
        "tools": {
          "deny": [
            "write", "edit", "file_write", "git_*",
            "message", "browser"
          ]
        }
      },
      {
        "id": "gulu",
        "tools": {
          "allow": [
            "read", "write", "image", "web_fetch",
            "message", "sessions_send"
          ],
          "deny": [
            "exec", "git_*", "edit", "process"
          ]
        }
      },
      {
        "id": "aeterna",
        "tools": {
          "allow": [
            "read", "write", "memory_*", "sessions_send"
          ],
          "deny": [
            "exec", "git_*", "edit", "file_write", "browser"
          ]
        }
      }
    ]
  }
}
```

**要点：**
- `tools.deny` 是禁止列表，比 `tools.allow`（允许列表）优先级高
- 设置 `allow` 后未列出的工具自动禁止
- 模式匹配 `"git_*"` 可以批量禁止一类工具
- 若只设置 `deny`，则只禁止指定工具，其他工具可用

---

## 5. ZooMesh 聊天室设计

### 5.1 聊天消息结构

ZooMesh 新增 `chat/` 消息类型，不走 QQ，纯 mesh 内通信：

```python
# ZooMesh 新增聊天 API

def send_chat_message(from_agent: str, content: str) -> dict:
    """发送全员聊天消息"""
    message = {
        "type": "chat_message",
        "from": from_agent,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "message_id": uuid4().hex[:12]
    }
    # 持久化到 chat/ 目录
    _atomic_write_json(CHAT_DIR / f"{message['message_id']}.json", message)
    # 发布事件
    publish_event("chat_message", message)
    return message

def get_chat_messages(limit: int = 50) -> list[dict]:
    """获取最近聊天消息"""
    files = sorted(CHAT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    messages = []
    for f in files[:limit]:
        with open(f) as fp:
            messages.append(json.load(fp))
    return list(reversed(messages))
```

### 5.2 仪表盘集成

Dev-Center 新增两个端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | GET | 获取最近聊天消息（limit 参数） |
| `/api/chat` | POST | 发送聊天消息（body: {from, content}） |

仪表盘右侧新增聊天室面板，通过这个 API 读写：

```
┌────────────────────────┐
│  💬 全员聊天室          │
│                        │
│  🐢 阿尔法: 审计完了吗  │
│  🦂 毒刺: 马上         │
│  🐜 织巢: 我代码写好了   │
│                  ...    │
│                        │
│ ┌────────────────────┐ │
│ │ 输入消息...  [发送] │ │
│ └────────────────────┘ │
└────────────────────────┘
```

### 5.3 聊天室与 agent 集成

每个 agent 需要：

1. **SOUL.md / 启动时** — 订阅 ZooMesh 的 `chat_message` 事件
2. **收到聊天消息** — 可以选择是否回复（agent 自主决定）
3. **自己发消息** — 通过 `send_chat_message()` 发送

```
agent 启动时:
  ZooMesh.subscribe("chat_message", handler)

handler(message):
  if message.from == 自己: return  # 不处理自己的消息
  # 可选: 根据消息内容判断是否需要回复
  # 如果是 @ 自己 则必须回复
```

---

## 6. ZooMesh 守护进程

新增一个 `zoo_mesh_daemon.py` 常驻进程：

```python
#!/usr/bin/env python3
"""ZooMesh 守护进程 — 由 zoo-pipeline 插件拉起"""

import sys, os, time, threading, json
from pathlib import Path

sys.path.insert(0, "/Users/zoo/workspace/code/feida_zoo/framework")
from core.mesh.zoo_mesh import ZooMesh
from core.mesh.inbox_watcher import InboxWatcher
from core.mesh.delivery_watcher import DeliveryWatcher

MESH_DIR = "/Users/zoo/workspace/members/panda/zoo_mesh"

def main():
    # 初始化 ZooMesh
    mesh = ZooMesh()
    mesh.init(MESH_DIR)
    
    # 启动聊天室目录
    chat_dir = Path(MESH_DIR) / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    
    # 启动看门狗
    watchers = [
        InboxWatcher(str(Path(MESH_DIR) / "inbound")),
        DeliveryWatcher(str(Path(MESH_DIR) / "delivery"))
    ]
    for w in watchers:
        w.start()
    
    print("✅ ZooMesh 守护进程已启动")
    print(f"   数据目录: {MESH_DIR}")
    print(f"   聊天室:   {chat_dir}")
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        for w in watchers:
            w.stop()
        print("🛑 ZooMesh 守护进程已停止")

if __name__ == "__main__":
    main()
```

---

## 7. 部署与配置步骤

### 7.1 安装插件

```bash
# 克隆或复制插件到 OpenClaw 的插件目录
cp -r plugins/zoo-pipeline ~/.openclaw/plugins/

# 安装依赖
cd ~/.openclaw/plugins/zoo-pipeline
npm install

# 启用插件
openclaw plugins enable zoo-pipeline
```

### 7.2 配置 Gateway

```bash
# 按 §4.2 配置 agent 权限
openclaw config set agents.list '<详见 4.2 节>'
```

### 7.3 启动 ZooMesh 守护进程

插件会在 `gateway_start` 时自动拉起。
也可手动测试：

```bash
python3 /Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py
```

### 7.4 重启仪表盘

```bash
# 仪表盘需要接入 ZooMesh chat API
python3 /Users/zoo/workspace/code/feida_zoo/dashboard/app_enhanced.py
```

---

## 8. 边界条件

### 8.1 消息拦截误判

`inbound_claim` 的关键问题是**将"聊天"误判为"任务"**（如"我设计了一个新功能"不是任务，但会触发拦截）。

**缓解方案：**
- 先使用关键词匹配 + 语境判断的简单规则
- 后续可以引入 LLM 判断：向模型发送消息摘要，返回 "task" / "chat" / "ambiguous"
- 标记为 ambiguous 的消息放行给 agent，但打上候选标记

### 8.2 聊天室僵尸消息

如果长时间没人发言，聊天室应当支持滚动清理（保留最近 N 条）。

### 8.3 Pipeline 控制器重启

控制器重启后：
- 正在进行的任务不受影响（状态在 `task_tracker.json` 和 `zoo_mesh/` 目录中持久化）
- 控制器重新加载未完成任务的状态
- 聊天室消息不受影响（文件持久化）

### 8.4 权限冲突

如果某个 agent 同时需要 `write`（写设计文档）但又不能 `write`（不能写代码），可以通过路径限制：
- `tools.allow` 配合 `tools.paths` 限制文件操作范围（如果 OpenClaw 支持）
- 或者 alpha 只允许写 `.md` 文件，通过 `write` 工具的路径校验实现

---

## 9. 工作量估算

| 模块 | 预估工时 | 负责人 |
|------|---------|--------|
| 插件骨架 (TypeScript) | 1-2 天 | weaver 🐜 |
| Pipeline 控制器逻辑 | 1-2 天 | weaver 🐜 |
| Agent 权限配置 | 0.5 天 | alpha 🐢（配置） |
| ZooMesh 聊天室 & 看门狗 | 1 天 | weaver 🐜 |
| 仪表盘聊天面板 | 0.5 天 | weaver 🐜 |
| 测试 & 联调 | 1 天 | 全员 |
| **合计** | **~6 天** | — |

---

> **设计者**: 阿尔法 🐢
> **设计状态**: 待审计
> **下一阶段**: 毒刺 🦂 审计设计
