#!/usr/bin/env python3
"""ZooMesh 守护进程 - HTTP API + ZooMesh 事件总线"""
import sys
import os
import time
import threading
import json
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

FRAMEWORK_DIR = os.environ.get("ZOO_FRAMEWORK_DIR", "/Users/zoo/workspace/code/feida_zoo/framework")
MESH_DIR = os.environ.get("ZOO_MESH_DIR", "/Users/zoo/workspace/members/panda/zoo_mesh")
HTTP_PORT = int(os.environ.get("ZOO_MESH_HTTP_PORT", "18793"))

sys.path.insert(0, str(Path(FRAMEWORK_DIR).parent))

from core.mesh.zoo_mesh import ZooMesh
from core.mesh.inbox_watcher import InboxWatcher
from core.mesh.delivery_watcher import AsyncDeliveryWatcher

logging.basicConfig(level=logging.INFO, format="[ZooMesh] %(asctime)s %(message)s")
logger = logging.getLogger("zoo_mesh")


class ChatWriter:
    """聊天消息持久化写入器"""

    def __init__(self, mesh_dir: str):
        chat_file = Path(mesh_dir) / "chat" / "messages.jsonl"
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        self._writer = None  # set below after LockedJsonlWriter import
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
    """True if allowed, False if rate limited"""
    now = time.time()
    timestamps = [t for t in RATE_LIMIT.get(source, []) if now - t < 60]
    if len(timestamps) >= 10:
        return False
    timestamps.append(now)
    RATE_LIMIT[source] = timestamps
    return True


# ── Token Cache (loaded once at startup) ──────────────────────────────────────
_ZOO_TOKENS: dict = {
    "alpha": os.environ.get("ZOO_TOKEN_ALPHA", ""),
    "weaver": os.environ.get("ZOO_TOKEN_WEAVER", ""),
    "duci": os.environ.get("ZOO_TOKEN_DUCI", ""),
    "gulu": os.environ.get("ZOO_TOKEN_GULU", ""),
    "aeterna": os.environ.get("ZOO_TOKEN_AETERNA", ""),
    "panda": os.environ.get("ZOO_TOKEN_PANDA", ""),
}


def verify_token(agent_id: str, token: str) -> bool:
    """Verify X-Zoo-Auth token against cached tokens (read once at startup)."""
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
        if mesh is not None:
            mesh.publish_event("chat_message", msg)
        self._json(200, msg)

    def _handle_sse(self):
        """Server-Sent Events stream for chat messages"""
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
        pass  # Silence default logging


# ── Module-level globals ─────────────────────────────────────────────────────────
chat = ChatWriter(MESH_DIR)
mesh = None  # ZooMesh instance set by main()


# ── Main (run as script) ────────────────────────────────────────────────────────
def main():
    global mesh
    logger.info("🚀 ZooMesh 守护进程启动中...")

    mesh = ZooMesh()
    mesh.init(MESH_DIR)

    # Daemon threads
    registry_path = str(Path(FRAMEWORK_DIR) / "shared" / "zoo_registry.json")
    iw = InboxWatcher(str(Path(MESH_DIR) / "inbound"), registry_path)
    threading.Thread(target=iw.start, daemon=True).start()
    logger.info("✅ InboxWatcher 已启动")

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
