# 🐢 Pipeline 插件开发 — 任务简报 v1.0

> **设计者**: 阿尔法 🐢
> **设计文档**: `alpha_zoo_pipeline_plugin_v1.1.md`
> **审计状态**: ✅ 毒刺条件性通过（3个P2开发时顺带）
> **开发负责人**: 织巢 🐜
> **日期**: 2026-05-12

---

## 目标

开发一个 **OpenClaw TypeScript 插件**，实现：
1. 消息入口守卫 — 拦截 `/task` 命令，写入 ZooMesh 目录
2. 守护进程生命周期管理 — 随 OpenClaw 启动 ZooMesh daemon
3. 崩溃自动重启 — daemon 异常退出时自动拉起

---

## 一、插件结构

```
plugins/zoo-pipeline/
├── openclaw.plugin.json    # 插件清单
├── package.json            # npm 包元数据
├── tsconfig.json           # TypeScript 配置
├── src/
│   ├── index.ts            # 入口: definePluginEntry
│   ├── hooks/
│   │   ├── inbound-claim.ts    # inbound_claim hook
│   │   ├── gateway-start.ts    # gateway_start hook
│   │   └── task-writer.ts      # 写入 ZooMesh 目录的工具函数
│   └── config.ts               # 默认配置定义
└── tests/
    └── plugin.test.ts
```

---

## 二、inbound_claim Hook

### 行为

1. 收到消息 → 检查是否以 `/task` 开头
2. 不是 `/task` → `return`（放行）
3. 是 `/task` → 写入 ZooMesh 目录 → `return { claim: true, syntheticReply }`

### 代码骨架

```typescript
// plugins/zoo-pipeline/src/hooks/inbound-claim.ts
import type { PluginAPI, InboundClaimEvent } from "openclaw/plugin-sdk";
import { writeTaskFile } from "./task-writer";

export function registerInboundClaim(api: PluginAPI): void {
  api.on(
    "inbound_claim",
    async (event: InboundClaimEvent) => {
      const text = (event.content || "").trim();

      // 只拦截 /task 前缀的命令
      if (!text.startsWith("/task")) {
        return;
      }

      const taskContent = text.replace("/task", "").trim();
      if (!taskContent) {
        return {
          claim: true,
          syntheticReply: "🐢 指令格式: `/task <你的需求>`",
        };
      }

      // 写入 ZooMesh 目录
      const taskId = `task_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const task = {
        type: "task_incoming",
        content: taskContent,
        sender: event.ctx?.senderId || "human",
        sessionKey: event.ctx?.sessionKey || "",
        timestamp: new Date().toISOString(),
        id: taskId,
      };

      await writeTaskFile(task);

      api.logger.info(`📝 任务已写入 ZooMesh: ${taskId} (${taskContent.slice(0, 40)})`);

      return {
        claim: true,
        syntheticReply: `🐢 工单已收到，正在评估: "${taskContent.slice(0, 60)}..."`,
      };
    },
    { priority: 80 },
  );
}
```

### 事件类型说明

`InboundClaimEvent` 包含:
- `content` — 消息文本
- `ctx` — 上下文（含 `sessionKey`, `senderId` 等）
- 返回 `{ claim: boolean, syntheticReply?: string }` 来拦截消息

---

## 三、gateway_start Hook

### 行为

1. 确定 ZooMesh daemon 脚本路径
2. 设置环境变量（`PYTHONPATH`, `ZOO_MESH_DIR` 等）
3. 以子进程方式启动 daemon
4. 健康检查轮询（最多 30 秒）
5. 崩溃自动重启

### 代码骨架

```typescript
// plugins/zoo-pipeline/src/hooks/gateway-start.ts
import { spawn, ChildProcess } from "child_process";
import type { PluginAPI, GatewayStartEvent } from "openclaw/plugin-sdk";

let daemonProcess: ChildProcess | null = null;

export function registerGatewayStart(api: PluginAPI): void {
  api.on(
    "gateway_start",
    async (event: GatewayStartEvent) => {
      const config = event.ctx?.config || {};
      const daemonPath =
        config.zooPipeline?.daemonPath ||
        "/Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py";
      const meshDir =
        config.zooPipeline?.meshDir ||
        "/Users/zoo/workspace/members/panda/zoo_mesh";
      const frameworkDir =
        config.zooPipeline?.frameworkDir ||
        "/Users/zoo/workspace/code/feida_zoo/framework";
      const httpPort = config.zooPipeline?.httpPort || "18793";

      startDaemon(api, daemonPath, meshDir, frameworkDir, httpPort);
    },
    { priority: 50 },
  );
}

function startDaemon(
  api: PluginAPI,
  daemonPath: string,
  meshDir: string,
  frameworkDir: string,
  httpPort: string,
): void {
  const env = {
    ...process.env,
    PYTHONPATH: frameworkDir,
    ZOO_MESH_DIR: meshDir,
    ZOO_MESH_HTTP_PORT: httpPort,
  };

  daemonProcess = spawn("python3", [daemonPath], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  daemonProcess.stdout?.on("data", (data: Buffer) => {
    api.logger.info(`[ZooMesh] ${data.toString().trim()}`);
  });

  daemonProcess.stderr?.on("data", (data: Buffer) => {
    api.logger.warn(`[ZooMesh:err] ${data.toString().trim()}`);
  });

  daemonProcess.on("exit", (code: number | null) => {
    if (code !== 0 && code !== null) {
      api.logger.warn(`⚠️ ZooMesh 异常退出 (code=${code})，5 秒后重启`);
      setTimeout(
        () => startDaemon(api, daemonPath, meshDir, frameworkDir, httpPort),
        5000,
      );
    }
  });

  // 健康检查
  waitForHealth(`http://127.0.0.1:${httpPort}/health`, 30000, api);
}

async function waitForHealth(
  url: string,
  timeoutMs: number,
  api: PluginAPI,
): Promise<void> {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        api.logger.info(`✅ ZooMesh 守护进程健康就绪: ${url}`);
        return;
      }
    } catch {
      // 还没启动，继续等
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  api.logger.warn(`⚠️ ZooMesh 健康检查超时 (${timeoutMs}ms)`);
}
```

---

## 四、Task Writer

```typescript
// plugins/zoo-pipeline/src/hooks/task-writer.ts
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";

const DEFAULT_MESH_DIR = "/Users/zoo/workspace/members/panda/zoo_mesh";

interface TaskFile {
  type: string;
  content: string;
  sender: string;
  sessionKey: string;
  timestamp: string;
  id: string;
}

export async function writeTaskFile(
  task: TaskFile,
  meshDir: string = process.env.ZOO_MESH_DIR || DEFAULT_MESH_DIR,
): Promise<string> {
  const tasksDir = join(meshDir, "inbound", "tasks");
  await mkdir(tasksDir, { recursive: true });
  const filePath = join(tasksDir, `${task.id}.json`);
  await writeFile(filePath, JSON.stringify(task, null, 2), "utf-8");
  return filePath;
}
```

---

## 五、插件 Manifest

```json
{
  "id": "zoo-pipeline",
  "name": "Zoo Pipeline",
  "description": "飝龘动物园 Pipeline 编排引擎 — 入口守卫 + 守护进程管理",
  "contracts": {},
  "activation": {
    "onStartup": true
  },
  "configSchema": {
    "type": "object",
    "properties": {
      "daemonPath": {
        "type": "string",
        "description": "ZooMesh daemon Python 脚本路径"
      },
      "meshDir": {
        "type": "string",
        "description": "ZooMesh 数据目录"
      },
      "frameworkDir": {
        "type": "string",
        "description": "feida_zoo framework 目录"
      },
      "httpPort": {
        "type": "string",
        "description": "ZooMesh HTTP API 端口",
        "default": "18793"
      }
    },
    "additionalProperties": false
  }
}
```

---

## 六、外部依赖

| 依赖 | 类型 | 说明 |
|------|------|------|
| `openclaw/plugin-sdk` | peer | 插件 SDK，OpenClaw 内置 |
| `typescript` | dev | 编译 |
| node >= 22 | runtime | OpenClaw 运行环境 |

---

## 七、开发注意事项

1. **路径不要硬编码** — 使用插件配置获取路径，提供合理的默认值
2. **健康检查要健壮** — daemon 可能启动较慢，最多等 30 秒
3. **崩溃重启要防无限循环** — 连续崩溃 5 次以上应停止自动重启
4. **log 要清晰** — 每条日志前缀 `[ZooPipeline]` 便于区分
5. **不要引入额外依赖** — 只用 Node.js 内置模块和 OpenClaw SDK

---

## 八、测试验证

1. 插件加载验证 — OpenClaw 启动时插件被正确加载
2. `/task` 拦截验证 — 发送 `/task 测试工单` 确认被拦截并写入 ZooMesh 目录
3. 非 `/task` 放行验证 — 普通消息不被拦截
4. daemon 启动验证 — 健康检查通过，HTTP 端点可用
5. daemon 崩溃重启验证 — 手动 kill daemon 后自动重新拉起

---

> **设计者**: 阿尔法 🐢
> **任务状态**: 🐜 待开发
> **参考设计**: `alpha_zoo_pipeline_plugin_v1.1.md`
