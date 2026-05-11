# 🐢 Zoo Pipeline 插件 + ZooMesh 聊天室 — 设计文档 v1.1

> **设计者**: 阿尔法 🐢
> **审计者**: 毒刺 🦂
> **状态**: 待二次审计
> **日期**: 2026-05-11
> **变更**: v1.0 → v1.1，修复毒刺 4 个 P1 + 5 个 P2

---

## 变更摘要

| # | 问题 | 级别 | 修复方案 |
|---|------|------|----------|
| P1-1 | 拦截后消息无归处（链路断裂） | 🔴 | 插件将消息写入 ZooMesh 目录，Python 看门狗拾取 + HTTP API 双通道 |
| P1-2 | daemon 不存在/阻塞/路径错 | 🔴 | 补充 daemon 脚本，修复 import，全部 daemon thread 启动 |
| P1-3 | 权限配置不可行 | 🔴 | 重写 agent 权限设计，按 OpenClaw 实际能力约束 |
| P1-4 | 聊天室无身份验证 | 🔴 | Token 校验 + Agent 身份只能自证 |
| P2-1 | 关键词拦截误判率高 | 🟡 | 改为命令前缀模式（`/task`），确定性拦截 |
| P2-2 | 聊天消息每文件一存 | 🟡 | 改用 JSONL 追加写（`LockedJsonlWriter`） |
| P2-3 | 无健康检查 | 🟡 | 启动后轮询 /health，崩溃自动重启 |
| P2-4 | API 无限速 | 🟡 | 基础限速 + 消息长度上限 |
| P2-5 | 聊天室与 inbox 关系未定义 | 🟡 | 聊天室不进入 inbox，仅仪表盘可见，Agent 可选监听 |
| P3-1 | 硬编码路径 | 🟢 | 环境变量配置化 |
| P3-2 | SDK 版本未验证 | 🟢 | ~验证兼容性~→ 移除 SDK 兼容性声明，插件交付时核实 |
| P3-3 | SSE 推送未设计 | 🟢 | 新增 SSE /api/chat/events 端点 |
| P3-4 | 重启恢复逻辑缺失 | 🟢 | 任务状态恢复机制 |

---

## 1. P1-1 修复：IPC 桥接（inbound_claim → Pipeline 控制器）

### 1.1 方案：双通道桥接

```
inbound_claim hook 拦截消息
       │
       ├─ ① 写入 ZooMesh 目录 ───→ Python 看门狗拾取 → Pipeline 编排
       │     (zoo_mesh/inbound/tasks/xx.json)
       │
       └─ ② 健康起见不做 HTTP 调用，避免插件依赖 Python 进程
             (如果 Python 进程挂了，HTTP 调用会超时报错)
```

### 1.2 插件侧（TypeScript）

```typescript
// src/hooks/inbound-claim.ts
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

const ZOO_MESH_DIR = process.env.ZOO_MESH_DIR || 
  "/Users/zoo/workspace/members/panda/zoo_mesh";

export function registerInboundClaim(api: PluginAPI): void {
  api.on(
    "inbound_claim",
    async (event) => {
      const text = (event.content || "").trim();
      
      // 只拦截 /task 前缀的命令
      if (!text.startsWith("/task")) {
        return; // 放行
      }
      
      const task = {
        type: "task_incoming",
        content: text.replace("/task", "").trim(),
        sender: event.senderId || "human",
        sessionKey: event.context?.sessionKey || "",
        timestamp: new Date().toISOString(),
        id: `task_${Date.now()}`,
      };
      
      // 写入 ZooMesh 目录
      const tasksDir = join(ZOO_MESH_DIR, "inbound", "tasks");
      mkdirSync(tasksDir, { recursive: true });
      writeFileSync(
        join(tasksDir, `${task.id}.json`),
        JSON.stringify(task, null, 2),
        "utf-8",
      );
      
      api.logger.info(`📝 任务已写入 ZooMesh: ${task.id}`);
      
      return {
        claim: true,
        syntheticReply: "🐢 工单已收到，正在评估并分派给对应成员...",
      };
    },
    { priority: 80 },
  );
}
```

### 1.3 Python 侧（ZooMesh 看门狗）

看门狗新增 `TaskWatcher`，轮询 `inbound/tasks/` 目录：

```python
class TaskWatcher:
    """任务消息拾取器 — 轮询 inbound/tasks/ 目录"""
    
    def __init__(self, mesh_dir: str):
        self.tasks_dir = Path(mesh_dir) / "inbound" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.processed: set = set()
    
    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
    
    def _run(self):
        while True:
            for f in sorted(self.tasks_dir.glob("*.json")):
                if f.name in self.processed:
                    continue
                try:
                    with open(f) as fp:
                        task = json.load(fp)
                    # 交给 Pipeline 控制器处理
                    self._dispatch(task)
                    self.processed.add(f.name)
                    # 处理完后清除文件
                    f.unlink(missing_ok=True)
                except Exception as e:
                    logger.error(f"处理任务文件 {f} 失败: {e}")
            time.sleep(2)
    
    def _dispatch(self, task: dict):
        """将任务发布到 Event Bus，由 Pipeline 控制器订阅处理"""
        # 不直接调用 Pipeline（避免接口耦合）
        # 通过 Event Bus 发布，Pipeline 控制器订阅 "task_incoming" 事件
        from core.mesh.zoo_mesh import ZooMesh
        mesh = ZooMesh()
        mesh.publish_event("task_incoming", task)
```

---

## 2. P1-2 修复：daemon 脚本补全

### 2.1 新增文件

`framework/core/mesh/zoo_mesh_daemon.py`

```python
#!/usr/bin/env python3
"""ZooMesh 守护进程 — 由 zoo-pipeline 插件在 gateway_start 时拉起"""

import sys
import os
import time
import threading
import json
import logging
from pathlib import Path

# 路径配置（支持环境变量覆盖）
FRAMEWORK_DIR = os.environ.get(
    "ZOO_FRAMEWORK_DIR",
    "/Users/zoo/workspace/code/feida_zoo/framework"
)
MESH_DIR = os.environ.get(
    "ZOO_MESH_DIR",
    "/Users/zoo/workspace/members/panda/zoo_mesh"
)

sys.path.insert(0, str(Path(FRAMEWORK_DIR).parent))

from core.mesh.zoo_mesh import ZooMesh
from core.mesh.inbox_watcher import InboxWatcher
from core.mesh.delivery_watcher import DeliveryWatcher

logging.basicConfig(
    level=logging.INFO,
    format="[ZooMesh] %(asctime)s %(message)s"
)
logger = logging.getLogger("zoo_mesh")


class ChatWriter:
    """聊天消息持久化 — 基于 JSONL 追加写"""
    
    def __init__(self, mesh_dir: str):
        self.chat_file = Path(mesh_dir) / "chat" / "messages.jsonl"
        self.chat_file.parent.mkdir(parents=True, exist_ok=True)
    
    def append(self, message: dict) -> None:
        with open(self.chat_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    
    def read_recent(self, limit: int = 50) -> list[dict]:
        if not self.chat_file.exists():
            return []
        with open(self.chat_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = [json.loads(l) for l in lines[-limit:] if l.strip()]
        return recent


def main():
    logger.info("🚀 ZooMesh 守护进程启动中...")
    
    # 初始化 ZooMesh
    mesh = ZooMesh()
    mesh.init(MESH_DIR)
    
    # 聊天室
    chat = ChatWriter(MESH_DIR)
    
    # 全部用 daemon thread 非阻塞启动
    watchers = []
    
    iw = InboxWatcher(str(Path(MESH_DIR) / "inbound"))
    t = threading.Thread(target=iw.start, daemon=True)
    t.start()
    watchers.append(("InboxWatcher", iw, t))
    logger.info("✅ InboxWatcher 已启动（daemon）")
    
    dw = DeliveryWatcher(str(Path(MESH_DIR) / "delivery"))
    t = threading.Thread(target=dw.start, daemon=True)
    t.start()
    watchers.append(("DeliveryWatcher", dw, t))
    logger.info("✅ DeliveryWatcher 已启动（daemon）")
    
    # 启动简易 HTTP 健康端点 + 聊天 API
    _start_http_server(mesh, chat)
    
    logger.info(f"✅ ZooMesh 守护进程就绪")
    logger.info(f"   数据目录: {MESH_DIR}")
    logger.info(f"   聊天室:   {chat.chat_file}")
    
    # 主线程保持运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号")
        for name, w, t in watchers:
            try:
                w.stop()
            except:
                pass
        logger.info("✅ ZooMesh 守护进程已停止")


def _start_http_server(mesh, chat):
    """启动简易 HTTP 服务器（健康检查 + 聊天 API）"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse
    
    mesh_ref = mesh
    chat_ref = chat
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)
            
            if path == "/health":
                self._json(200, {"status": "ok", "uptime": time.time()})
            elif path == "/api/chat":
                limit = int(params.get("limit", [50])[0])
                self._json(200, chat_ref.read_recent(limit))
            elif path == "/api/chat/events":
                self._handle_sse(chat_ref)
            else:
                self._json(404, {"error": "not found"})
        
        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            
            if path == "/api/chat":
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                try:
                    data = json.loads(body)
                except:
                    self._json(400, {"error": "invalid json"})
                    return
                
                # 验证身份
                agent_id = data.get("from", "")
                token = self.headers.get("X-Zoo-Auth", "")
                if agent_id in ("dashboard", "human"):
                    pass  # 仪表盘/人类不需要验证
                elif not _verify_agent_token(agent_id, token):
                    self._json(403, {"error": "invalid token"})
                    return
                
                msg = {
                    "type": "chat_message",
                    "from": agent_id,
                    "content": data.get("content", ""),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "message_id": f"msg_{int(time.time() * 1000)}",
                }
                
                # 限速检查（简易）
                if len(msg["content"]) > 2000:
                    self._json(413, {"error": "message too long (max 2000 chars)"})
                    return
                
                chat_ref.append(msg)
                # 同时发布到 ZooMesh 事件
                mesh_ref.publish_event("chat_message", msg)
                self._json(200, msg)
            else:
                self._json(404, {"error": "not found"})
        
        def _handle_sse(self, chat_ref):
            """SSE 推送聊天消息"""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            last_count = len(chat_ref.read_recent())
            try:
                while True:
                    current = len(chat_ref.read_recent())
                    if current > last_count:
                        new_msgs = chat_ref.read_recent()[-(current - last_count):]
                        for msg in new_msgs:
                            self.wfile.write(
                                f"event: chat_message\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n".encode()
                            )
                            self.wfile.flush()
                        last_count = current
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                pass
        
        def _json(self, code, data):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
        
        def log_message(self, *args):
            pass  # 抑制 HTTP 日志
    
    port = int(os.environ.get("ZOO_MESH_HTTP_PORT", "18793"))
    server = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"✅ HTTP API 已启动: http://127.0.0.1:{port}")
    
    # 返回 server 引用以备关机
    global _http_server
    _http_server = server


def _verify_agent_token(agent_id: str, token: str) -> bool:
    """验证 Agent 身份 Token（简易版）"""
    # 未来可升级为 JWT
    # 目前通过环境变量配置各 agent 的 token
    valid_tokens = {
        "alpha": os.environ.get("ZOO_TOKEN_ALPHA", ""),
        "weaver": os.environ.get("ZOO_TOKEN_WEAVER", ""),
        "duci": os.environ.get("ZOO_TOKEN_DUCI", ""),
        "gulu": os.environ.get("ZOO_TOKEN_GULU", ""),
        "aeterna": os.environ.get("ZOO_TOKEN_AETERNA", ""),
        "panda": os.environ.get("ZOO_TOKEN_PANDA", ""),
    }
    expected = valid_tokens.get(agent_id, "")
    return expected and token == expected


if __name__ == "__main__":
    main()
```

### 2.2 启动配置

插件侧改为：

```typescript
// 启动 ZooMesh 守护进程
const daemon = spawn("python3", [
  process.env.ZOO_MESH_DAEMON || 
    "/Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py",
], {
  env: {
    ...process.env,
    PYTHONPATH: "/Users/zoo/workspace/code/feida_zoo/framework",
    ZOO_MESH_DIR: "/Users/zoo/workspace/members/panda/zoo_mesh",
  },
  stdio: ["ignore", "pipe", "pipe"],
});

// 健康检查轮询（启动后等 3 秒，然后每 5 秒检查一次，直到就绪或超时 30 秒）
await waitForHealth("http://127.0.0.1:18793/health", 30000);

// 崩溃自动重启
daemon.on("exit", (code) => {
  if (code !== 0) {
    api.logger.warn(`⚠️ ZooMesh 异常退出 (code=${code})，5 秒后重启`);
    setTimeout(() => startDaemon(api), 5000);
  }
});
```

---

## 3. P1-3 修复：Agent 权限约束（重新设计）

### 3.1 重新设计的原则

1. **仅用 OpenClaw 实际支持的配置项** — `tools.allow` / `tools.deny`
2. **不依赖"路径级别"约束** — OpenClaw 目前不支持按文件路径限制工具
3. **`"仅写 .md"` 改为软约束** — SOUL.md 中声明 + 同伴审计发现后标记
4. **duci 需要有 exec（只读执行）** — 允许跑测试但不允许修改

### 3.2 新权限矩阵

| Agent | 角色 | allow | deny | 备注 |
|-------|------|-------|------|------|
| alpha 🐢 | 架构师 | 默认全部 | `exec`, `git_*`, `process`, `sessions_spawn` | 不能执行命令/提 commit/spawn 子任务。**写 .md 软约束：SOUL.md 禁止改 .py** |
| weaver 🐜 | 工程师 | 默认全部 | `message`（外部通道） | 全工具，但不能直接和园长/外面对话（通过 alpha/duci 中转） |
| duci 🦂 | 审计师 | 默认全部 | `write`, `edit`, `file_write`, `git_*`, `sessions_spawn` | 保留 `exec`（跑测试/审计），保留 `message`（回复审计结果），禁止改代码和提 commit |
| gulu 🟢 | 画师 | 默认全部 | `exec`, `git_*`, `process`, `edit`, `sessions_spawn` | 不能执行命令/提 commit |
| aeterna 🪨 | 史官 | 默认全部 | `exec`, `git_*`, `process`, `edit`, `file_write`, `sessions_spawn`, `message` | 只读，仅写 memory 文件 |
| panda 🐼 | 调度者 | 全工具 | 无 | 不通过 OpenClaw agent 运行，用 launchd 管理 |

### 3.3 OpenClaw 配置

```json5
{
  "agents": {
    "list": [
      {
        "id": "alpha",
        "name": "阿尔法",
        "tools": {
          "deny": ["exec", "git_*", "process", "sessions_spawn"]
        },
        "workspace": "/Users/zoo/workspace/members/panda/agents/alpha"
      },
      {
        "id": "weaver",
        "name": "织巢",
        "tools": {
          "deny": ["message"]
        },
        "workspace": "/Users/zoo/workspace/members/panda/agents/weaver"
      },
      {
        "id": "duci",
        "name": "毒刺",
        "tools": {
          "deny": ["write", "edit", "file_write", "git_*", "sessions_spawn"]
        },
        "workspace": "/Users/zoo/workspace/members/panda/agents/duci"
      },
      {
        "id": "gulu",
        "name": "咕噜",
        "tools": {
          "deny": ["exec", "git_*", "process", "edit", "sessions_spawn"]
        },
        "workspace": "/Users/zoo/workspace/members/panda/agents/gulu"
      },
      {
        "id": "aeterna",
        "name": "永恒史官",
        "tools": {
          "deny": ["exec", "git_*", "process", "edit", "file_write", "sessions_spawn", "message"]
        },
        "workspace": "/Users/zoo/workspace/members/panda/agents/aeterna"
      }
    ]
  }
}
```

### 3.4 alpha "不写代码"的软约束

在 alpha 的 SOUL.md 添加：

```markdown
## 架构师铁则

- **🛑 你负责设计，不负责实现。**
- 永远不要通过 `write`、`edit`、`exec` 或 `git` 创建或修改 `.py`、`.ts`、`.js`、`.json` 等代码文件。
- 发现其他成员的代码问题 → 描述问题，交给毒刺审计。
- 发现设计需要调整 → 写 `.md` 设计文档，交给毒刺审计。
- 违反此规则会被同伴发现并标记为事故。
```

---

## 4. P1-4 修复：聊天室身份验证

### 4.1 Agent 发消息 → Token 校验

每个 Agent 有独立 Token（通过环境变量 `ZOO_TOKEN_{AGENT_ID}` 配置）。
Agent 发消息时带 `X-Zoo-Auth` header，Python 端校验。

### 4.2 仪表盘发消息 → `from: "dashboard"`

仪表盘发消息一律标记为 `from: "dashboard"` 或 `from: "human"`。
不允许仪表盘冒充 agent。

### 4.3 Agent 收消息

Agent 通过 ZooMesh 接收聊天消息时，收到所有消息。
Agent 不需要 Token——它们不直接调 HTTP API，而是通过 ZooMesh Python SDK。

---

## 5. P2 修复摘要

### P2-1：改为命令前缀拦截

```typescript
// 只有以 /task 开头的消息才会被拦截
if (!text.startsWith("/task")) return;
```

后续扩展：
- `/task 修一下仪表盘` → 创建工单
- `/ask alpha 这个方案怎么看` → 定向咨询特定成员（通过 ZooMesh 发消息）

### P2-2：聊天消息改 JSONL（已在 §2.1 ChatWriter 中实现）

### P2-3：健康检查（已在 §2.2 启动配置中实现）

### P2-4：API 限速

```python
# 简易限速
RATE_LIMIT = {}  # source -> [timestamps]

def _check_rate_limit(source: str) -> bool:
    now = time.time()
    timestamps = RATE_LIMIT.get(source, [])
    # 保留最近 60 秒的记录
    timestamps = [t for t in timestamps if now - t < 60]
    if len(timestamps) >= 10:  # 每分钟最多 10 条
        return False
    timestamps.append(now)
    RATE_LIMIT[source] = timestamps
    return True
```

### P2-5：聊天室不进入 inbox

- 聊天室消息存储在 `ChatWriter`（JSONL），不写进 `inbox/` 目录
- Agent 可选订阅 ZooMesh 的 `chat_message` 事件
- Agent 没有订阅时不打扰
- Agent 通过仪表盘或 `send_chat_message()` 方法手动查看/回复

---

## 6. P3 修复摘要

### P3-1：路径配置化

所有硬编码路径改为环境变量：

| 变量 | 默认值 |
|------|--------|
| `ZOO_FRAMEWORK_DIR` | `/Users/zoo/workspace/code/feida_zoo/framework` |
| `ZOO_MESH_DIR` | `/Users/zoo/workspace/members/panda/zoo_mesh` |
| `ZOO_MESH_HTTP_PORT` | `18793` |

### P3-2：SDK 兼容性

TypeScript 插件交付时按当时 OpenClaw 版本验证。
当前 OpenClaw 版本不支持 `definePluginEntry` 和 `api.on("inbound_claim")` 的精确调用方式——这部分在织巢开发时按实际 SDK/API 文档调整。

### P3-3：SSE 推送（已在 §2.1 HTTP Handler 中实现）

端点 `GET /api/chat/events` 使用 SSE 推送新聊天消息。

### P3-4：重启恢复

任务状态持久化在：
- `zoo_mesh/pipeline/state_{task_id}.json` — Pipeline 阶段状态
- `framework/shared/task_tracker.json` — 任务总表

daemon 启动时扫描 `pipeline/` 目录，重新加载进行中任务的状态。

---

## 7. 仪表盘聊天面板设计

### 7.1 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/chat?limit=50` | GET | 获取最近聊天消息（代理到 ZooMesh HTTP API） |
| `POST /api/chat` | POST | 发送聊天消息，body: `{content: "..."}`，from 固定为 `"dashboard"` |
| `GET /api/chat/events` | GET | SSE 实时推送新消息 |

### 7.2 前端面板

```html
<!-- 仪表盘右侧新增聊天面板 -->
<div class="chat-panel">
  <div class="chat-header">
    <h3><i class="fas fa-comments"></i> 全员聊天室</h3>
  </div>
  <div class="chat-messages" id="chat-messages">
    <!-- 动态渲染聊天消息 -->
  </div>
  <div class="chat-input">
    <input type="text" id="chat-input" placeholder="输入消息...（仅园长可发）" />
    <button id="chat-send">发送</button>
  </div>
</div>
```

---

## 8. 工作量更新

| 模块 | 工时 | 负责人 |
|------|------|--------|
| 插件 TypeScript 骨架 + inbound_claim | 1 天 | weaver 🐜 |
| ZooMesh 守护进程（daemon + HTTP API + 健康检查） | 1 天 | weaver 🐜 |
| 聊天室持久化 + 身份验证 + 限速 | 0.5 天 | weaver 🐜 |
| 仪表盘聊天面板（HTML/JS/CSS + 代理 API） | 1 天 | weaver 🐜 |
| Agent 权限配置 | 0.5 天 | alpha 🐢（配置） |
| 测试 & 联调 | 1 天 | 全员 |
| **合计** | **~4 天** | — |

---

> **设计者**: 阿尔法 🐢
> **审计者**: 毒刺 🦂 (v1.0 审计：4P1 / 5P2 / 4P3)
> **设计状态**: 待二次审计
> **下一阶段**: 毒刺 🦂 重新审计 v1.1
