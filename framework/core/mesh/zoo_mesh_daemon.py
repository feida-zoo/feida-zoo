#!/usr/bin/env python3
"""ZooMesh 守护进程 - HTTP API + ZooMesh 事件总线 + Pipeline 全自动驱动"""
import sys
import os
import time
import threading
import json
import logging
import re
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

FRAMEWORK_DIR = os.environ.get("ZOO_FRAMEWORK_DIR", "/Users/zoo/workspace/code/feida_zoo/framework")
MESH_DIR = os.environ.get("ZOO_MESH_DIR", "/Users/zoo/workspace/members/panda/zoo_mesh")
HTTP_PORT = int(os.environ.get("ZOO_MESH_HTTP_PORT", "18793"))

sys.path.insert(0, str(Path(FRAMEWORK_DIR)))
sys.path.insert(0, str(Path(FRAMEWORK_DIR).parent))

from core.mesh.zoo_mesh import ZooMesh
from core.mesh.inbox_watcher import InboxWatcher
from core.mesh.delivery_watcher import AsyncDeliveryWatcher
from core.harness.pipeline import ZooPipeline
from core.harness.state_machine import StateMachine

logging.basicConfig(level=logging.INFO, format="[ZooMesh] %(asctime)s %(message)s")
logger = logging.getLogger("zoo_mesh")


# ── Pipeline Phase 定义 ──────────────────────────────────────────────────────────
PHASES = ["request", "validate", "design", "ui_design", "review", "develop", "test", "audit", "final_check", "deliver"]

# 阶段 → 下一阶段映射
PHASE_TRANSITION_MAP = {
    "request": "validate",
    "validate": "design",
    "design": "ui_design",
    "ui_design": "review",
    "review": "develop",
    "develop": "test",
    "test": "audit",
    "audit": "final_check",
    "final_check": "deliver",
    "deliver": "done",
}

# 阶段 → 默认执行 Agent 映射（未指定 assignee 时的 Fallback）
PHASE_DEFAULT_AGENT = {
    "request": "panda",
    "validate": "alpha",       # 架构师评估需求边界与可行性
    "design": "alpha",
    "ui_design": "alpha",
    "review": "duci",
    "develop": "alpha",         # 阿尔法直连 Claude Code 执行开发
    "test": "duci",
    "audit": "duci",
    "final_check": "panda",
    "deliver": "panda",
    "done": "panda",
}


# ── Pipeline 辅助函数 ────────────────────────────────────────────────────────────

def _get_next_phase(current: str) -> str | None:
    """获取 pipeline 的下一个阶段。"""
    return PHASE_TRANSITION_MAP.get(current)


def _load_requirements() -> list:
    """加载 requirements.json。"""
    reqs_file = Path(FRAMEWORK_DIR).parent / "dashboard" / "data" / "requirements.json"
    if not reqs_file.exists():
        return []
    try:
        with open(reqs_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"读取 requirements.json 失败: {e}")
        return []


def _save_requirements(reqs: list) -> None:
    """原子写入 requirements.json。"""
    reqs_file = Path(FRAMEWORK_DIR).parent / "dashboard" / "data" / "requirements.json"
    temp = reqs_file.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(reqs, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.rename(str(temp), str(reqs_file))


def _publish_phase_advancement(title: str, pipeline_id: str, from_phase: str, to_phase: str) -> None:
    """向 chat 频道发布阶段推进消息（dashboard SSE 可见）。"""
    emoji_map = {
        "request": "📥", "validate": "🔍", "design": "🎨", "review": "📋",
        "develop": "🔧", "test": "🧪", "audit": "🔐", "final_check": "✅", "deliver": "🚀",
        "done": "🏁", "cancelled": "❌", "escalated": "⚠️",
    }
    from_emoji = emoji_map.get(from_phase, "📌")
    to_emoji = emoji_map.get(to_phase, "📌")
    content = (
        f"🏗️ Pipeline 推进: 「{title}」\n"
        f"  {from_emoji} {from_phase} → {to_emoji} {to_phase}\n"
        f"  pipeline_id: {pipeline_id}"
    )
    chat.append({
        "type": "chat_message",
        "from": "pipeline",
        "content": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pipeline_id": pipeline_id,
        "phase_event": "advancement",
    })
    if mesh is not None:
        mesh.publish_event("pipeline_advance", {
            "title": title,
            "pipeline_id": pipeline_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
        })
    logger.info(f"Pipeline 推进: {from_phase} → {to_phase} (pipeline_id={pipeline_id})")


# ── Phase-to-Agent 调度 ─────────────────────────────────────────────────────────

def _phase_assignee(phase: str, requirement: dict) -> str:
    """确定某个阶段应该由哪个 Agent 执行。

    优先使用 requirement.assignee，其次查询 phase_default_agent 映射，
    最后 fallback 到 panda。
    """
    assignee = requirement.get("assignee", "").strip()
    if assignee:
        return assignee
    return PHASE_DEFAULT_AGENT.get(phase, "panda")


def _pick_phase_agent(phase: str) -> str:
    """当不涉及特定 requirement 时，根据阶段选择默认 Agent。"""
    return PHASE_DEFAULT_AGENT.get(phase, "panda")


# ── 消息解析 & 路由（on_wakeup 主逻辑）───────────────────────────────────────────

def _on_wakeup_callback(agent_id: str):
    """当 agent inbox 有新消息时触发。

    处理两种消息类型：
    1. pipeline_request — 来自 dashboard 的新需求，启动流水线
    2. pipeline_ack / phase_complete — 来自 agent 的执行完毕回复，推进到下一阶段
    """
    try:
        queue_dir = Path(MESH_DIR) / "inbound" / agent_id / "queue"
        files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return
        msg_file = files[-1]
        with open(msg_file) as f:
            msg = json.load(f)

        body = msg.get("body", "")
        msg_from = msg.get("from", "?")
        logger.info(f"📩 on_wakeup({agent_id}): 来自 {msg_from}, 内容: {body[:120]}")

        # ---- 写入 chat 频道（前台聊天室可见） ----
        chat.append({
            "type": "chat_message",
            "from": agent_id,
            "content": f"📥 收到来自 {msg_from} 的消息: {body[:200]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })

        # ================================================================
        #  类型 1：pipeline_request — 启动新 Pipeline
        # ================================================================
        is_pipeline_request = False

        # 检查是否是来自 dashboard 的 pipeline_request（via @panda 消息格式）
        if msg_from == "dashboard" and "pipeline_request" in body:
            is_pipeline_request = True
        elif msg_from == "dashboard" and "新Pipeline请求" in body:
            is_pipeline_request = True
        elif body.startswith("{") and '"type": "pipeline_request"' in body:
            is_pipeline_request = True

        if is_pipeline_request:
            _handle_pipeline_request(body, agent_id)
            return

        # ================================================================
        #  类型 2：pipeline_ack / phase_complete — Agent 完成反馈
        # ================================================================
        if "pipeline_ack" in body or "phase_complete" in body or "PI_DONE" in body:
            _handle_phase_complete(body, agent_id)
            return

        # ================================================================
        #  类型 3：其它消息 — 尝试匹配 requirements.json 中的 pipeline_id
        #  用于 agent 回复包含 pipeline_id 的完成消息
        # ================================================================
        reqs = _load_requirements()
        for req in reqs:
            pipeline_id = req.get("pipeline_id", "")
            if pipeline_id and (pipeline_id in body or pipeline_id in msg_from):
                _handle_phase_complete(body, agent_id)
                return

    except Exception as e:
        logger.warning(f"on_wakeup({agent_id}) 处理失败: {e}")


def _parse_pipeline_payload(body: str) -> dict | None:
    """从消息 body 中提取 pipeline_request JSON payload。"""
    # 格式1: 直接是 JSON
    if body.startswith("{"):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            pass

    # 格式2: 包含 JSON 字符串的聊天消息
    json_match = re.search(r'({.*"type":\s*"pipeline_request".*})', body, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 格式3: @panda 新Pipeline请求: {json}
    colon_idx = body.find(":")
    if colon_idx > 0 and colon_idx < len(body) - 2:
        potential_json = body[colon_idx + 1:].strip()
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            pass

    return None


def _handle_pipeline_request(body: str, agent_id: str) -> None:
    """处理 pipeline_request — 启动 ZooPipeline 并推进到第一阶段。"""
    # 解析 payload
    payload = _parse_pipeline_payload(body)
    if not payload:
        logger.warning(f"无法解析 pipeline_request payload: {body[:150]}")
        chat.append({
            "type": "chat_message",
            "from": "pipeline",
            "content": f"⚠️ 无法解析 pipeline_request 消息: {body[:100]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        return

    task_id = payload.get("task_id", "") or payload.get("pipeline_id", "")
    title = payload.get("title", "未命名需求")
    req_id = payload.get("requirement_id", "")
    assignee = payload.get("assignee") or _pick_phase_agent("validate")

    if not task_id:
        logger.warning("pipeline_request 缺少 task_id")
        return

    logger.info(f"🏗️ 启动 Pipeline: task_id={task_id}, title={title}")

    # 1. 创建 ZooPipeline 实例
    pipeline = ZooPipeline(task_id=task_id, agent_id=agent_id, zoo_mesh=mesh)

    # 2. 加载 requirement 并检查当前状态
    reqs = _load_requirements()
    cur_req = None
    for req in reqs:
        if req.get("id") == req_id or req.get("pipeline_id") == task_id:
            cur_req = req
            break

    if cur_req:
        current_status = cur_req.get("status", "request")
        logger.info(f"  需求当前状态: {current_status}")
    else:
        # 尚未创建对应 requirement（dashboard 创建消息转发至此）
        logger.info("  未找到对应 requirement，创建中")
        import uuid
        cur_req = {
            "id": req_id or str(uuid.uuid4()),
            "title": title,
            "description": payload.get("description", ""),
            "assignee": assignee,
            "status": "request",
            "phase": "request",
            "pipeline_id": task_id,
            "created_at": payload.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "source": "pipeline_auto",
        }
        reqs.append(cur_req)
        _save_requirements(reqs)

    # 3. 推进 StateMachine（request → validate）
    try:
        StateMachine.transition("request", "validate")
    except Exception as e:
        logger.warning(f"StateMachine transition failed: {e}")

    # 4. 更新 requirements.json
    cur_req["status"] = "validate"
    cur_req["phase"] = "validate"
    cur_req["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_requirements(reqs)

    # 5. 发布推进事件
    _publish_phase_advancement(title, task_id, "request", "validate")

    # 6. 写入第一阶段 Agent 的 inbox
    phase_assignee = cur_req.get("assignee") or _pick_phase_agent("validate")
    phase_msg = (
        f"[Pipeline] Phase: validate\n"
        f"task_id: {task_id}\n"
        f"requirement_id: {cur_req['id']}\n"
        f"title: {title}\n"
        f"description: {cur_req.get('description', '')}\n"
        f"指令: 请执行 Validate 阶段，完成后回复 phase_complete:{task_id}"
    )
    try:
        mesh.send(phase_assignee, "pipeline", phase_msg)
        logger.info(f"已通知 {phase_assignee} 执行 validate 阶段")
    except Exception as e:
        logger.warning(f"通知 {phase_assignee} 失败: {e}")

    # 7. 设置 Pipeline 状态
    pipeline.advance_to("validate")
    mesh.set_pipeline_state(task_id, "validate")
    logger.info(f"✅ Pipeline {task_id} 已启动，第一阶段: validate → {phase_assignee}")


def _handle_phase_complete(body: str, agent_id: str) -> None:
    """处理 Agent 的 phase_complete/pipeline_ack 回复，推进到下一阶段。"""
    # 提取 pipeline_id（格式: pl_xxxxxxxx 或 PI_DONE:pl_xxxxxxxx）
    pipeline_id = None
    for token in body.split():
        if token.startswith("pl_"):
            pipeline_id = token
            break
        if "PI_DONE:" in token:
            # PI_DONE:pl_xxxxxxxx → 提取 pl_xxxxxxxx
            m = re.search(r'(pl_[a-f0-9]+)', token)
            if m:
                pipeline_id = m.group(1)
                break

    # 从 requirements 中查找
    if not pipeline_id:
        reqs = _load_requirements()
        for req in reqs:
            pid = req.get("pipeline_id", "")
            if pid and (pid in body or agent_id in body):
                pipeline_id = pid
                break

    if not pipeline_id:
        logger.warning(f"_handle_phase_complete: 无法提取 pipeline_id, body={body[:100]}")
        return

    # 提取阶段名称
    completed_phase = "unknown"
    phase_match = re.search(r'Phase:\s*(\w+)', body)
    if phase_match:
        completed_phase = phase_match.group(1)
    elif "phase_complete" in body:
        phase_match = re.search(r'phase_complete[:\s]*(\w+)', body)
        if phase_match:
            completed_phase = phase_match.group(1)

    logger.info(f"🎯 阶段完成: agent={agent_id}, phase={completed_phase}, pipeline_id={pipeline_id}")

    # 载入 requirements
    reqs = _load_requirements()
    cur_req = None
    for req in reqs:
        if req.get("pipeline_id") == pipeline_id:
            cur_req = req
            break

    if not cur_req:
        logger.warning(f"找不到 pipeline_id={pipeline_id} 对应的 requirement")
        return

    # ⚠️ 阶段完成 Agent 身份校验：只有当前阶段指定的 Agent 才能推进
    current_status = cur_req.get("status", "request")
    expected_agent = cur_req.get("assignee") or _pick_phase_agent(current_status)
    if agent_id != expected_agent:
        logger.warning(
            f"⛔ 身份校验失败: agent={agent_id} 尝试完成 {current_status} 阶段，"
            f"但该阶段只能由 {expected_agent} 完成"
        )
        chat.append({
            "type": "chat_message",
            "from": "pipeline",
            "content": (
                f"⛔ 阶段推进被拒绝: {agent_id} 无法完成 {current_status} 阶段，"
                f"需要 {expected_agent} 来执行"
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        return
    next_phase = _get_next_phase(current_status)

    if not next_phase:
        logger.info(f"Pipeline {pipeline_id} 已到达终态: {current_status}")
        return

    if next_phase == "done":
        # Pipeline 完成
        cur_req["status"] = "done"
        cur_req["phase"] = "done"
        cur_req["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        cur_req["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_requirements(reqs)

        # 通过 StateMachine 完成
        try:
            pipeline = ZooPipeline(task_id=pipeline_id, agent_id=agent_id, zoo_mesh=mesh)
            pipeline.advance_to("deliver")
            pipeline.mark_done()
        except Exception:
            pass

        _publish_phase_advancement(cur_req["title"], pipeline_id, current_status, "done")
        mesh.set_pipeline_state(pipeline_id, "done")
        logger.info(f"🏁 Pipeline {pipeline_id} 已完成！")
        return

    # 正常推进到下一阶段
    try:
        StateMachine.transition(current_status, next_phase)
    except Exception as e:
        logger.warning(f"StateMachine transition {current_status}→{next_phase} 失败: {e}")
        return

    cur_req["status"] = next_phase
    cur_req["phase"] = next_phase
    cur_req["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_requirements(reqs)

    _publish_phase_advancement(cur_req["title"], pipeline_id, current_status, next_phase)

    # 通知下一阶段的 Agent
    next_agent = cur_req.get("assignee") or _pick_phase_agent(next_phase)
    next_msg = (
        f"[Pipeline] Phase: {next_phase}\n"
        f"task_id: {pipeline_id}\n"
        f"requirement_id: {cur_req['id']}\n"
        f"title: {cur_req['title']}\n"
        f"指令: 请执行 {next_phase} 阶段，完成后回复 phase_complete:{pipeline_id}"
    )

    try:
        mesh.send(next_agent, "pipeline", next_msg)
        logger.info(f"已通知 {next_agent} 执行 {next_phase} 阶段")
    except Exception as e:
        logger.warning(f"通知 {next_agent} 失败: {e}")

    # 更新 Pipeline 状态
    try:
        pipeline = ZooPipeline(task_id=pipeline_id, agent_id=agent_id, zoo_mesh=mesh)
        pipeline.advance_to(next_phase)
    except Exception as e:
        logger.warning(f"Pipeline advance_to 失败: {e}")

    mesh.set_pipeline_state(pipeline_id, next_phase)
    logger.info(f"✅ Pipeline {pipeline_id}: {current_status} → {next_phase}")


# ── ChatWriter ───────────────────────────────────────────────────────────────────

class ChatWriter:
    """聊天消息持久化写入器"""

    def __init__(self, mesh_dir: str):
        chat_file = Path(mesh_dir) / "chat" / "messages.jsonl"
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        self._writer = None
        self._chat_file = chat_file
        self._init_writer()

    def _init_writer(self):
        from core.mesh.locked_jsonl import LockedJsonlWriter
        self._writer = LockedJsonlWriter(str(self._chat_file))

    def append(self, msg: dict) -> None:
        if self._writer is None:
            self._init_writer()
        self._writer.append(msg)

    def read_recent(self, limit: int = 50) -> list:
        if self._writer is None:
            self._init_writer()
        return self._writer.read_recent(limit)


# ── Rate Limiting ──────────────────────────────────────────────────────────────
RATE_LIMIT: dict[str, list] = {}


def check_rate_limit(source: str) -> bool:
    now = time.time()
    timestamps = [t for t in RATE_LIMIT.get(source, []) if now - t < 60]
    if len(timestamps) >= 10:
        return False
    timestamps.append(now)
    RATE_LIMIT[source] = timestamps
    return True


# ── Token Cache ────────────────────────────────────────────────────────────────
_ZOO_TOKENS: dict = {
    "alpha": os.environ.get("ZOO_TOKEN_ALPHA", ""),
    "duci": os.environ.get("ZOO_TOKEN_DUCI", ""),
    "panda": os.environ.get("ZOO_TOKEN_PANDA", ""),
}


def verify_token(agent_id: str, token: str) -> bool:
    expected = _ZOO_TOKENS.get(agent_id, "")
    return bool(expected and token == expected)


# ── HTTP Handler ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            self._json(200, {"status": "ok"})
        elif path == "/api/chat":
            limit = int(params.get("limit", ["50"])[0])
            self._json(200, chat.read_recent(limit))
        elif path == "/api/chat/events":
            self._handle_sse()
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/chat":
            self._json(404, {"error": "not found"})
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body)
        except Exception:
            self._json(400, {"error": "invalid json"})
            return

        agent_id = data.get("from", "")
        content = data.get("content", "")

        if not check_rate_limit(agent_id):
            self._json(429, {"error": "rate limit exceeded"})
            return

        if len(content) > 2000:
            self._json(413, {"error": "message too long (max 2000 chars)"})
            return

        if agent_id not in ("dashboard", "human"):
            token = self.headers.get("X-Zoo-Auth", "")
            if not verify_token(agent_id, token):
                self._json(403, {"error": "invalid token"})
                return

        msg = {
            "type": "chat_message",
            "from": agent_id,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "message_id": f"msg_{int(time.time() * 1000)}",
        }
        chat.append(msg)

        # Check if message targets a specific agent (@agent_id)
        mentioned = None
        mention_match = re.match(r'^@(\w+)\s+(.*)', content)
        if mention_match:
            target_agent = mention_match.group(1)
            actual_content = mention_match.group(2)
            if mesh is not None:
                registry_agents = mesh._registry.list_agents() if hasattr(mesh, '_registry') else []
                if not registry_agents:
                    registry_agents = ["alpha", "duci", "panda"]
                if target_agent in registry_agents:
                    mentioned = target_agent
                    msg['mentioned'] = mentioned
                    try:
                        if mesh is not None:
                            inbox_msg = f"[仪表盘消息] {agent_id} 提到你: {actual_content}"
                            mesh.send(mentioned, "dashboard", inbox_msg)
                            logger.info(f"已转发消息到 {mentioned} 的收件箱")
                    except Exception as e:
                        logger.warning(f"转发消息到 {mentioned} 收件箱失败: {e}")

        if mentioned:
            msg['mentioned'] = mentioned

        if mesh is not None:
            mesh.publish_event("chat_message", msg)
        self._json(200, msg)

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last_count = len(chat.read_recent())
        try:
            while True:
                current = len(chat.read_recent())
                if current > last_count:
                    for m in chat.read_recent()[-(current - last_count):]:
                        self.wfile.write(
                            f"event: chat_message\ndata: {json.dumps(m, ensure_ascii=False)}\n\n".encode()
                        )
                        self.wfile.flush()
                    last_count = current
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, *args):
        pass


# ── Module-level globals ─────────────────────────────────────────────────────────
chat = ChatWriter(MESH_DIR)
mesh = None


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    global mesh
    logger.info("🚀 ZooMesh 守护进程启动中...")

    mesh = ZooMesh()
    mesh.init(MESH_DIR)

    # Daemon threads
    registry_path = str(Path(FRAMEWORK_DIR) / "shared" / "zoo_registry.json")

    # ── InboxWatcher (含 Pipeline 全自动驱动回调) ──
    # InboxWatcher 内部拼接 <mesh_dir>/<agent_id>/queue
    # 传入 MESH_DIR/inbound 确保路径正确
    iw = InboxWatcher(str(Path(MESH_DIR) / "inbound"), registry_path, on_wakeup=_on_wakeup_callback)
    threading.Thread(target=iw.start, daemon=True).start()
    logger.info("✅ InboxWatcher (含 Pipeline 驱动) 已启动")

    dw = AsyncDeliveryWatcher(MESH_DIR)
    threading.Thread(target=dw.start_filesystem_watch, daemon=True).start()
    logger.info("✅ DeliveryWatcher 已启动")

    # HTTP server - threaded
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"✅ HTTP API 已启动: http://127.0.0.1:{HTTP_PORT}")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号")


if __name__ == "__main__":
    main()
