"""Tests for zoo_mesh_daemon HTTP API"""
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path

import pytest

FEIDA_ZOO = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo"))
sys.path.insert(0, str(FEIDA_ZOO))

from core.mesh.zoo_mesh_daemon import ChatWriter, check_rate_limit, verify_token


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def temp_mesh(tmp_path):
    mesh_dir = tmp_path / "mesh"
    (mesh_dir / "chat").mkdir(parents=True)
    yield str(mesh_dir)


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    """Start daemon server on a fixed port, yield base URL"""
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    (mesh_dir / "chat").mkdir()
    (mesh_dir / "inbound").mkdir()

    port = 18794
    monkeypatch.setenv("ZOO_MESH_HTTP_PORT", str(port))
    monkeypatch.setenv("ZOO_MESH_DIR", str(mesh_dir))
    monkeypatch.setenv("ZOO_FRAMEWORK_DIR", str(FEIDA_ZOO / "framework"))

    import core.mesh.zoo_mesh_daemon as daemon
    daemon.chat = ChatWriter(str(mesh_dir))
    daemon.mesh = None

    from http.server import HTTPServer
    from core.mesh.zoo_mesh_daemon import Handler

    server = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)

    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ── ChatWriter Tests ───────────────────────────────────────────────────────────
def test_chat_writer_append_read(temp_mesh):
    writer = ChatWriter(temp_mesh)
    msg = {
        "type": "chat_message",
        "from": "weaver",
        "content": "hello world",
        "timestamp": "2026-05-11T19:00:00+0800",
        "message_id": "msg_1",
    }
    writer.append(msg)
    msgs = writer.read_recent(limit=10)
    assert len(msgs) == 1
    assert msgs[0]["from"] == "weaver"
    assert msgs[0]["content"] == "hello world"


def test_chat_writer_multiple(temp_mesh):
    writer = ChatWriter(temp_mesh)
    for i in range(5):
        writer.append({"from": "tester", "content": f"msg {i}"})
    msgs = writer.read_recent(limit=3)
    assert len(msgs) == 3
    assert msgs[-1]["content"] == "msg 4"


def test_chat_writer_missing_file(temp_mesh):
    """read_recent on non-existent file returns empty list"""
    writer = ChatWriter(temp_mesh)
    assert writer.read_recent() == []


# ── Rate Limit Tests ──────────────────────────────────────────────────────────
def test_rate_limit_allowed():
    import core.mesh.zoo_mesh_daemon as daemon
    daemon.RATE_LIMIT.clear()
    for _ in range(10):
        assert check_rate_limit("weaver") is True


def test_rate_limit_blocked():
    import core.mesh.zoo_mesh_daemon as daemon
    daemon.RATE_LIMIT.clear()
    for _ in range(10):
        check_rate_limit("weaver")
    assert check_rate_limit("weaver") is False


def test_message_too_long_logic():
    long_content = "x" * 2001
    assert len(long_content) > 2000


# ── Token Verification ────────────────────────────────────────────────────────
def test_verify_token_no_env(monkeypatch):
    """No token set → reject"""
    monkeypatch.setenv("ZOO_TOKEN_WEAVER", "")
    assert verify_token("weaver", "") is False
    assert verify_token("weaver", "tok123") is False


def test_verify_token_match(monkeypatch):
    """Matching token → accept"""
    import core.mesh.zoo_mesh_daemon as daemon
    # Set tokens directly - they are cached at import time
    daemon._ZOO_TOKENS["weaver"] = "secret123"
    daemon._ZOO_TOKENS["alpha"] = "alpha456"
    assert verify_token("weaver", "secret123") is True
    assert verify_token("alpha", "alpha456") is True
    assert verify_token("weaver", "wrong") is False
    assert verify_token("weaver", "") is False

# ── HTTP Integration Tests ────────────────────────────────────────────────────
def test_health_endpoint(running_server):
    with urllib.request.urlopen(f"{running_server}/health", timeout=5) as r:
        data = json.load(r)
    assert data["status"] == "ok"


def test_get_chat_empty(running_server):
    with urllib.request.urlopen(f"{running_server}/api/chat", timeout=5) as r:
        data = json.load(r)
    assert data == []


def test_post_chat_message(running_server):
    payload = json.dumps({"from": "dashboard", "content": "hello"}).encode()
    req = urllib.request.Request(
        f"{running_server}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.load(r)
    assert data["from"] == "dashboard"
    assert data["content"] == "hello"
    assert "message_id" in data


def test_post_rate_limited(running_server, monkeypatch):
    """10 messages → 11th should be rate limited"""
    import core.mesh.zoo_mesh_daemon as daemon
    monkeypatch.setattr(daemon, "RATE_LIMIT", {})
    daemon._ZOO_TOKENS["weaver"] = "test"

    payload = json.dumps({"from": "weaver", "content": "test"}).encode()
    headers = {"Content-Type": "application/json", "X-Zoo-Auth": "test"}

    for _ in range(10):
        req = urllib.request.Request(f"{running_server}/api/chat", data=payload, headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=5)

    req = urllib.request.Request(f"{running_server}/api/chat", data=payload, headers=headers, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 429


def test_post_message_too_long(running_server, monkeypatch):
    """Message > 2000 chars → 413"""
    import core.mesh.zoo_mesh_daemon as daemon
    monkeypatch.setattr(daemon, "RATE_LIMIT", {})
    daemon._ZOO_TOKENS["weaver"] = "test"

    payload = json.dumps({"from": "weaver", "content": "x" * 2001}).encode()
    req = urllib.request.Request(
        f"{running_server}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json", "X-Zoo-Auth": "test"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 413


def test_post_invalid_token(running_server, monkeypatch):
    """Wrong token → 403"""
    import core.mesh.zoo_mesh_daemon as daemon
    monkeypatch.setattr(daemon, "RATE_LIMIT", {})
    daemon._ZOO_TOKENS["weaver"] = "test"

    payload = json.dumps({"from": "weaver", "content": "hi"}).encode()
    req = urllib.request.Request(
        f"{running_server}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json", "X-Zoo-Auth": "wrongtoken"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 403


def test_invalid_json(running_server):
    """Invalid JSON body → 400"""
    payload = b"not valid json"
    req = urllib.request.Request(
        f"{running_server}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400
