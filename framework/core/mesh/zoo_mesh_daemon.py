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
PHASES = ["request", "validate", "design", "ui_design", "review", "develop_wt", "review_test", "develop_code", "test", "audit", "final_check", "deliver"]

# 阶段 → 下一阶段映射
PHASE_TRANSITION_MAP = {
    "request":     "validate",
    "validate":    "design",
    "design":      "ui_design",
    "ui_design":   "review",
    "review":      "develop_wt",
    "develop_wt":  "review_test",
    "review_test": "develop_code",
    "develop":     "develop_wt",       # 旧数据兼容
    "develop_code":"test",
    "test":        "audit",
    "audit":       "final_check",
    "final_check": "deliver",
    "deliver":     "done",
}

# 阶段 → 默认执行 Agent 映射（未指定 assignee 时的 Fallback）
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


# ── Pipeline 辅助函数 ────────────────────────────────────────────────────────────

def _get_next_phase(current: str) -> str | None:
    """获取 pipeline 的下一个阶段。"""
    return PHASE_TRANSITION_MAP.get(current)


def _load_requirements() -> list:
    """加载 requirements.json 并自动执行旧数据迁移。"""
    reqs_file = Path(FRAMEWORK_DIR).parent / "dashboard" / "data" / "requirements.json"
    if not reqs_file.exists():
        return []
    try:
        with open(reqs_file) as f:
            reqs = json.load(f)
        # 自动迁移旧 develop 数据
        migrated = False
        for r in reqs:
            if r.get("status") == "develop":
                r["status"] = "develop_wt"
                r["phase"] = "develop_wt"
                migrated = True
        if migrated:
            _save_requirements(reqs)
        return reqs
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


# ── Pipeline V2: 新增函数 ──────────────────────────────────────────────────

PHASE_COMPLETE_SIGNALS = {"phase_complete:", "PI_DONE:", "pipeline_ack:"}


def _is_phase_complete_signal(body: str) -> bool:
    """检查 body 第一个 token 是否以 phase_complete 信号开头（避免匹配指令文本）。"""
    first_line = body.split("\n")[0] if "\n" in body else body
    first_token = first_line.split()[0] if first_line.strip() else ""
    for sig in PHASE_COMPLETE_SIGNALS:
        if first_token.startswith(sig):
            return True
    return False


_NOTIFY_LOG: set = set()





def _send_agent_notification(agent_id: str, body: str) -> None:
    """通过 openclaw agent 触发目标 Agent 会话，实现跨 Agent 通知。
    不走 QQ Bot API，使用会话路由（sessions_send 的 CLI 等价方式）。"""
    import hashlib
    notify_key = f"{agent_id}:{hashlib.md5(body.encode()).hexdigest()}"
    if notify_key in _NOTIFY_LOG:
        return

    pipeline_id = _extract_pipeline_id(body)
    phase = _extract_phase_from_body(body)

    # 异步通知所有 Agent（不阻塞 InboxWatcher）
    # 通过 openclaw agent 唤醒 Agent 会话，Agent 回复中的 phase_complete
    # 信号会被 _try_parse_agent_reply 捕获并写入 inbox。
    # 没有独立的超时限制——等 Agent 处理完自然会返回。

    # 精简通知文本
    msg_text = (
        f"📥 Pipeline通知: "
        f"[{phase or '?'}] {pipeline_id or ''}\n"
        f"{body[:250]}"
    )

    # 异步通知其他 Agent（不阻塞 InboxWatcher）
    def _notify_async():
        """后台线程通知 Agent。openclaw agent 唤醒会话，Agent 回复中的
        phase_complete 信号被自动解析写入 inbox，完成全自动推进。"""
        import subprocess as _sp
        oc_bin = "/opt/homebrew/bin/openclaw"
        try:
            result = _sp.run(
                [oc_bin, "agent", "--agent", agent_id, "-m", msg_text],
                capture_output=True, text=True
            )
            for out in (result.stdout, result.stderr):
                if not out:
                    continue
                for line in out.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    tok = line.split()[0]
                    if any(tok.startswith(s) for s in {"phase_complete:", "PI_DONE:", "pipeline_ack:"}):
                        import uuid as _uuid, json as _json
                        from pathlib import Path as _Path
                        sig = {"id": str(_uuid.uuid4()), "from": agent_id, "to": agent_id,
                            "body": line, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            "delivery_count": 0, "ttl": 3600}
                        qdir = _Path(MESH_DIR) / "inbound" / agent_id / "queue"
                        qdir.mkdir(parents=True, exist_ok=True)
                        with open(qdir / f"msg_{_uuid.uuid4()}.json", "w") as f:
                            _json.dump(sig, f)
                        logger.info(f"📨 Agent {agent_id} 已自动推进: {line[:60]}")
            logger.info(f"通知 {agent_id} 完成 (pipeline={pipeline_id})")
        except Exception as e:
            logger.warning(f"通知 {agent_id} 异常: {e}")

    t = threading.Thread(target=_notify_async, daemon=True)
    t.start()
    _NOTIFY_LOG.add(notify_key)
    logger.info(f"通知 {agent_id} 已通知（异步） (pipeline={pipeline_id})")


def _extract_pipeline_id(body: str) -> str | None:
    """从消息中提取 pipeline_id（pl_xxxxxxxx）。"""
    for token in body.split():
        if token.startswith("pl_"):
            return token
    m = re.search(r'(pl_[a-f0-9]+)', body)
    return m.group(1) if m else None


def _extract_phase_from_body(body: str) -> str | None:
    """从 Pipeline 指令中提取阶段名。"""
    m = re.search(r'Phase:\s*(\w+)', body)
    return m.group(1) if m else None


def _move_to_processed(msg_file) -> None:
    """处理完毕后将消息文件移入 processed 子目录。"""
    processed_dir = msg_file.parent / "processed"
    processed_dir.mkdir(exist_ok=True)
    msg_file.rename(processed_dir / msg_file.name)


def _agent_available(agent_id: str) -> bool:
    """检查 agent 是否有未完成的活跃任务（不限阶段）。"""
    reqs = _load_requirements()
    active = [r for r in reqs
              if r.get("assignee") == agent_id
              and r.get("status") not in ("done", "cancelled")]
    return len(active) == 0


def _load_pending_queue() -> list:
    """加载 pending 队列。"""
    pending_file = Path(MESH_DIR) / "pipeline" / "pending.json"
    if not pending_file.exists():
        return []
    try:
        with open(pending_file) as f:
            return json.load(f)
    except Exception:
        return []


def _save_pending_queue(queue: list) -> None:
    """写入 pending 队列。"""
    pending_file = Path(MESH_DIR) / "pipeline" / "pending.json"
    temp = pending_file.with_suffix(".tmp")
    with open(temp, "w") as f:
        json.dump(queue, f, indent=2)
    os.rename(str(temp), str(pending_file))


def _enqueue_pending(pipeline_id: str, phase: str, assignee: str, priority: str, title: str) -> None:
    """任务入 pending 队列。"""
    queue = _load_pending_queue()
    queue.append({
        "pipeline_id": pipeline_id,
        "phase": phase,
        "assignee": assignee,
        "priority": priority or "P3",
        "title": title,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    _save_pending_queue(queue)


def _pop_next_pending(agent_id: str) -> dict | None:
    """从 pending 队列弹出指定 agent 的优先级最高任务（不限 phase）。"""
    queue = _load_pending_queue()
    candidates = [t for t in queue if t.get("assignee") == agent_id]
    if not candidates:
        return None
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 4}
    candidates.sort(key=lambda x: (priority_order.get(x.get("priority", ""), 4), x.get("created_at", "")))
    best = candidates[0]
    queue = [t for t in queue if t.get("pipeline_id") != best["pipeline_id"]]
    _save_pending_queue(queue)
    return best


def _create_review_file(pipeline_id: str, phase: str) -> None:
    """创建 review/review_test_pl_xxx.json（status: pending）。文件名含阶段前缀。"""
    review_file = Path(MESH_DIR) / "pipeline" / f"{phase}_{pipeline_id}.json"
    if not review_file.exists():
        with open(review_file, "w") as f:
            json.dump({
                "pipeline_id": pipeline_id,
                "phase": phase,
                "status": "pending",
                "result": None,
                "comments": [],
                "reviewer": None,
                "reviewed_at": None,
            }, f, indent=2)

def _read_review_result(pipeline_id: str, phase: str) -> dict | None:
    """读取审查结果（按阶段区分配置文件）。返回 None 如果文件不存在或未完成。"""
    review_file = Path(MESH_DIR) / "pipeline" / f"{phase}_{pipeline_id}.json"
    if not review_file.exists():
        return None
    try:
        with open(review_file) as f:
            data = json.load(f)
        if data.get("status") != "completed":
            return None
        return data
    except Exception:
        return None


def _get_phase_template(phase: str, pipeline_id: str = "") -> str:
    """根据阶段返回对应的指令模板（pipeline_id 为可选插值参数）。"""
    templates = {
        "validate": (
            "【设计产出要求】\n"
            "- What: 具体要做什么改动\n"
            "- Why: 为什么要这么做（背景、解决的问题）\n"
            "- Tradeoff: 放弃了什么方案，做了什么权衡\n"
            "- Open Questions: 有什么不确定的点、遗留问题\n"
            "- Next Action: 希望审计方重点审查什么\n"
        ),
        "design": (
            "\n【设计产出要求 - 五件套】\n"
            "- What: 具体要做什么改动\n"
            "- Why: 为什么要这么做（背景、解决的问题）\n"
            "- Tradeoff: 放弃了什么方案，做了什么权衡\n"
            "- Open Questions: 有什么不确定的点、遗留问题\n"
            "- Next Action: 希望审计方重点审查什么\n"
        ),
        "develop_wt": (
            "\n【TDD - 写测试用例】\n"
            "请为当前需求编写测试用例（单元测试 + 集成测试）\n"
            "完成后回复 phase_complete:{pipeline_id}\n"
            "\n注意：\n"
            "- 测试用例需覆盖所有验收标准\n"
            "- 下一步会由毒刺评审测试用例\n"
        ),
        "develop_code": (
            "\n【TDD - 写实现代码】\n"
            "测试用例已通过毒刺评审，请编写实现代码\n"
            "自测所有用例通过后回复 phase_complete:{pipeline_id}\n"
        ),
    }
    t = templates.get(phase, "")
    if pipeline_id:
        t = t.replace("{pipeline_id}", pipeline_id)
    return t


def _publish_phase_advancement(title: str, pipeline_id: str, from_phase: str, to_phase: str) -> None:
    """向 chat 频道发布阶段推进消息（dashboard SSE 可见）。"""
    emoji_map = {
        "request": "📥", "validate": "🔍", "design": "🎨", "ui_design": "🎨", "review": "📋",
        "develop_wt": "🧪", "review_test": "📋", "develop_code": "🔧",
        "develop": "🔧",
        "test": "🧪", "audit": "🔐", "final_check": "✅", "deliver": "🚀",
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
    """当 agent inbox 有新消息时触发（Pipeline V2）。

    处理所有未处理消息文件。
    - Panda inbox: pipeline_request + phase_complete
    - Alpha/Duci inbox: 不做自动推进，仅桥接通知
    """
    try:
        queue_dir = Path(MESH_DIR) / "inbound" / agent_id / "queue"
        files = sorted(queue_dir.glob("msg_*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return

        for msg_file in files:
            # 跳过可能存在的 processed 子目录
            if msg_file.parent.name == "processed":
                continue

            try:
                with open(msg_file) as f:
                    msg = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
                logger.warning(f"跳过无效消息文件: {msg_file.name} ({e})")
                # 坏文件也移走避免死循环
                _move_to_processed(msg_file)
                continue

            body = msg.get("body", "")
            msg_from = msg.get("from", "?")
            logger.info(f"📩 on_wakeup({agent_id}): 来自 {msg_from}, 内容: {body[:120]}")

            # 写入 chat 频道
            chat.append({
                "type": "chat_message",
                "from": agent_id,
                "content": f"📥 收到来自 {msg_from} 的消息: {body[:200]}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })

            # 类型 1：pipeline_request — 启动新 Pipeline（仅 Panda）
            is_pipeline_request = False
            if msg_from == "dashboard" and "pipeline_request" in body:
                is_pipeline_request = True
            elif msg_from == "dashboard" and "新Pipeline请求" in body:
                is_pipeline_request = True
            elif body.startswith("{") and '"type": "pipeline_request"' in body:
                is_pipeline_request = True

            if is_pipeline_request:
                if agent_id == "panda":
                    _handle_pipeline_request(body, agent_id)
                _move_to_processed(msg_file)
                continue

            # 类型 2：明确信号的 phase_complete（所有 agent 均可处理）
            if _is_phase_complete_signal(body):
                _handle_phase_complete(body, agent_id)
                _move_to_processed(msg_file)
                continue

            # 类型 3：已删除。所有推进必须有明确信号。
            # 其他消息 → 仅桥接通知（不自动推进），并移入 processed 避免死循环
            if agent_id != "panda":
                _send_agent_notification(agent_id, body)
            else:
                # Panda 的未分类消息 — 仅通知（类型 3 已从设计文档彻底移除）
                logger.info(f"Panda 未分类消息，仅通知: {body[:80]}")
                _send_agent_notification(agent_id, body)
            _move_to_processed(msg_file)

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
        # 补充缺失的 assignee
        if not cur_req.get("assignee"):
            cur_req["assignee"] = assignee
        logger.info(f"  需求当前状态: {current_status}, assignee={cur_req.get('assignee','')}")
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

    # 6. Agent 可用性检测（Pipeline V2 排队）
    phase_assignee = _pick_phase_agent("validate")
    priority = cur_req.get("priority", payload.get("priority", "P3"))

    if not _agent_available(phase_assignee):
        # Agent 忙 → 入 pending 队列
        _enqueue_pending(task_id, "validate", phase_assignee, priority, title)
        logger.info(f"⏳ {phase_assignee} 忙碌，{task_id} 入 pending 队列等待")
    else:
        # Agent 空闲 → 发指令
        phase_msg = (
            f"[Pipeline] Phase: validate\n"
            f"task_id: {task_id}\n"
            f"requirement_id: {cur_req['id']}\n"
            f"title: {title}\n"
            f"description: {cur_req.get('description', '')}\n"
            f"指令: 请执行 Validate 阶段，完成后回复 phase_complete:{task_id}\n"
            f"回复方式: 在本对话回复 phase_complete:{task_id}:pass/reject，\n"
            f"或 POST 至 http://127.0.0.1:18793/api/chat (from=你的id, content=phase_complete:{task_id}:pass)\n"
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
    # 提取 pipeline_id（格式: pl_xxxxxxxx、phase_complete:pl_xxxxxxxx 或 PI_DONE:pl_xxxxxxxx）
    pipeline_id = None
    for token in body.split():
        # 直接匹配 pl_ 前缀
        if token.startswith("pl_"):
            pipeline_id = token
            break
        # phase_complete:pl_xxxxxxxx → 提取 pl_xxxxxxxx
        m = re.search(r'phase_complete[:\s]+(pl_[a-f0-9]+)', token)
        if m:
            pipeline_id = m.group(1)
            break
        # PI_DONE:pl_xxxxxxxx → 提取 pl_xxxxxxxx
        if "PI_DONE:" in token:
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

    # 从 phase_complete 中提取审查结果（格式: phase_complete:pl_xxx:pass/reject）
    review_result = None
    result_match = re.search(r'phase_complete[:\s]+pl_[-a-zA-Z0-9]+[:\s]+(pass|reject)', body)
    if result_match:
        review_result = result_match.group(1)
        logger.info(f"📝 phase_complete 携带审查结果: {review_result}")

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

    current_status = cur_req.get("status", "request")
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

    # Pipeline V2: 检查审查结果（review/review_test/audit 阶段推进时）
    if current_status in ("review", "review_test", "test", "audit"):
        # 验证信号发送者：只接受该阶段的默认 Agent
        expected_agent = _pick_phase_agent(current_status)
        if agent_id != expected_agent:
            logger.warning(f"Pipeline {pipeline_id}: {current_status} 阶段拒绝来自 {agent_id} 的信号（期望 {expected_agent}）")
            return
        # 如果 phase_complete 携带了审查结果，直接写入审查文件
        if review_result:
            review_path = Path(MESH_DIR) / "pipeline" / f"{current_status}_{pipeline_id}.json"
            if review_path.exists():
                try:
                    with open(review_path) as f:
                        rdata = json.load(f)
                    rdata["status"] = "completed"
                    rdata["result"] = review_result
                    rdata["reviewer"] = agent_id
                    rdata["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    with open(review_path, "w") as f:
                        json.dump(rdata, f, indent=2)
                    logger.info(f"📝 phase_complete 内联审查结果已写入: {current_status}={review_result}")
                except Exception as e:
                    logger.warning(f"写入内联审查结果失败: {e}")
        review_data = _read_review_result(pipeline_id, current_status)
        if not review_data:
            # 审查文件不存在或 status 非 completed → 阻塞推进，不跳过
            logger.warning(f"Pipeline {pipeline_id}: {current_status} 审查结果未完成，拒绝推进")
            return
        result = review_data.get("result")
        if result == "reject":
            # 驳回：StateMachine 回退
            fallback_map = {"review": "design", "review_test": "develop_wt", "test": "develop_code", "audit": "develop_code"}
            fallback = fallback_map.get(current_status)
            if fallback:
                try:
                    StateMachine.transition(current_status, fallback)
                    cur_req["status"] = fallback
                    cur_req["phase"] = fallback
                    cur_req["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    _save_requirements(reqs)
                    _publish_phase_advancement(cur_req["title"], pipeline_id, current_status, fallback)
                    next_agent = cur_req.get("assignee") or _pick_phase_agent(fallback)
                    next_msg = (
                        f"[Pipeline] Phase: {fallback}\n"
                        f"task_id: {pipeline_id}\n"
                        f"requirement_id: {cur_req['id']}\n"
                        f"title: {cur_req['title']}\n"
                        f"指令: 审查驳回，请按 review 意见修改后重新提交，完成后回复 phase_complete:{pipeline_id}"
                    )
                    mesh.send(next_agent, "pipeline", next_msg)
                    mesh.set_pipeline_state(pipeline_id, fallback)
                    logger.info(f"🔄 Pipeline {pipeline_id}: 审查驳回，{current_status}→{fallback}")
                    return
                except Exception:
                    pass
        # result="pass" → 继续推进到下一阶段

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

    # Pipeline V2: 为 review/review_test/test/audit 阶段创建审查文件
    if next_phase in ("review", "review_test", "test", "audit"):
        _create_review_file(pipeline_id, next_phase)

    # 通知下一阶段的 Agent
    # review/review_test/test/audit 强制使用阶段默认 Agent（毒刺），不受需求 assignee 覆盖
    if next_phase in ("review", "review_test", "test", "audit"):
        next_agent = _pick_phase_agent(next_phase)
    else:
        next_agent = cur_req.get("assignee") or _pick_phase_agent(next_phase)
    template = _get_phase_template(next_phase, pipeline_id)
    next_msg = (
        f"[Pipeline] Phase: {next_phase}\n"
        f"task_id: {pipeline_id}\n"
        f"requirement_id: {cur_req['id']}\n"
        f"title: {cur_req['title']}\n"
        f"指令: 请执行 {next_phase} 阶段，完成后回复 phase_complete:{pipeline_id}\n"
        f"回复方式: 在本对话回复 phase_complete:{pipeline_id}:pass/reject\n"
        f"{template}"
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

    # Pipeline V2: 检查 pending 队列弹出下一任务
    try:
        pending = _pop_next_pending(next_agent)
        if pending:
            pid = pending["pipeline_id"]
            logger.info(f"📤 从 pending 队列弹出 {pid} 给 {next_agent} (phase={next_phase})")
            reqs2 = _load_requirements()
            for r in reqs2:
                if r.get("pipeline_id") == pid and r.get("status") == next_phase:
                    template2 = _get_phase_template(next_phase, pid)
                    msg = (
                        f"[Pipeline] Phase: {next_phase}\n"
                        f"task_id: {pid}\n"
                        f"requirement_id: {r['id']}\n"
                        f"title: {r.get('title', '')}\n"
                        f"指令: 请执行 {next_phase} 阶段，完成后回复 phase_complete:{pid}"
                        f"{template2}"
                    )
                    mesh.send(next_agent, "pipeline", msg)
                    logger.info(f"📤 pending 任务 {pid} 已派发")
                    break
    except Exception as e:
        logger.warning(f"Pending 队列弹出失败: {e}")


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

        # phase_complete 信号不需要 X-Zoo-Auth 鉴权（自动推进管线）
        first_token = content.strip().split()[0] if content.strip() else ""
        is_signal = any(first_token.startswith(s) for s in {"phase_complete:", "PI_DONE:", "pipeline_ack:"})
        if not is_signal and agent_id not in ("dashboard", "human"):
            token = self.headers.get("X-Zoo-Auth", "")
            if not verify_token(agent_id, token):
                self._json(403, {"error": "invalid token"})
                return

        # 处理 phase_complete 信号：写入发送者自己的 inbox，让 InboxWatcher 自动调度
        first_token = content.strip().split()[0] if content.strip() else ""
        if any(first_token.startswith(s) for s in {"phase_complete:", "PI_DONE:", "pipeline_ack:"}):
            import uuid, json
            from pathlib import Path
            sig_msg = {
                "id": str(uuid.uuid4()),
                "from": agent_id,
                "to": agent_id,
                "body": content,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "delivery_count": 0,
                "ttl": 3600,
            }
            queue_dir = Path(MESH_DIR) / "inbound" / agent_id / "queue"
            queue_dir.mkdir(parents=True, exist_ok=True)
            with open(queue_dir / f"msg_{uuid.uuid4()}.json", "w") as f:
                json.dump(sig_msg, f)
            logger.info(f"phase_complete 信号已写入 {agent_id} inbox: {content[:60]}")
        
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



def _dispatch_pending_agents():
    """主动推进 pending 队列中的任务，防止卡住。
    
    每 60s main loop 调用一次。遍历所有 agent，将 pending 队列中属于该 agent 的任务
    直接派发（pending 任务的 assignee 就是目标 agent，无需检查 _agent_available）。
    """
    queue = _load_pending_queue()
    if not queue:
        return

    # 从 registry 获取所有 agent
    registry_path = str(Path(FRAMEWORK_DIR) / "shared" / "zoo_registry.json")
    agent_ids = ["alpha", "duci", "panda", "weaver", "aeterna", "gulu"]
    try:
        if os.path.exists(registry_path):
            with open(registry_path) as f:
                reg = json.load(f)
                agent_ids = list(reg.get("agents", {}).keys())
    except Exception:
        pass

    reqs = _load_requirements()
    dispatched = 0

    for agent_id in agent_ids:
        item = _pop_next_pending(agent_id)
        if not item:
            continue

        pipeline_id = item["pipeline_id"]
        phase = item.get("phase", "validate")
        title = item.get("title", "")

        cur_req = None
        for r in reqs:
            if r.get("pipeline_id") == pipeline_id:
                cur_req = r
                break

        if not cur_req:
            logger.warning(f"pending 任务 {pipeline_id} 找不到对应 requirement，跳过")
            continue

        if cur_req.get("status") != phase:
            logger.info(f"pending 任务 {pipeline_id} 状态已变更 ({phase} → {cur_req.get('status')})，跳过派发")
            continue

        description = cur_req.get("description", "")
        template = _get_phase_template(phase, pipeline_id)
        msg = (
            f"[Pipeline] Phase: {phase}\n"
            f"task_id: {pipeline_id}\n"
            f"requirement_id: {cur_req.get('id', '')}\n"
            f"title: {title}\n"
            f"description: {description}\n"
            f"指令: 请执行 {phase} 阶段，完成后回复 phase_complete:{pipeline_id}\n"
            f"{template}"
        )

        try:
            mesh.send(agent_id, "pipeline", msg)
            logger.info(f"📤 pending 任务重新派发: {pipeline_id} → {agent_id} (phase={phase})")
            dispatched += 1
        except Exception as e:
            logger.warning(f"📤 pending 任务派发失败: {pipeline_id} → {agent_id}: {e}")

    if dispatched:
        logger.info(f"📤 本轮 pending 派发完成: {dispatched} 个任务")


def _scan_pending_requirements():
    """扫描 requirements.json 中未启动的 Pipeline 请求，自动写入 Panda inbox。
    解决 Dashboard HTTP POST 到 ZooMesh 可能因重启丢失的问题。"""
    import glob as _glob
    reqs_path = str(Path(FRAMEWORK_DIR).parent / "dashboard" / "data" / "requirements.json")
    logger.info(f"📋 扫描未启动的 Pipeline 请求: {reqs_path}")
    if not os.path.exists(reqs_path):
        logger.warning("requirements.json 不存在")
        return
    try:
        with open(reqs_path) as f:
            reqs = json.load(f)
    except Exception as e:
        logger.warning(f"读取 requirements.json 失败: {e}")
        return

    existing = set()
    for f in _glob.glob(str(Path(MESH_DIR) / "pipeline" / "state_pl_*.json")):
        pid = Path(f).stem.replace("state_", "")
        existing.add(pid)

    import uuid as _uuid
    for req in reqs:
        pid = req.get("pipeline_id", "")
        req_status = req.get("status", "request")
        if pid and pid not in existing and req_status in ("request", ""):
            req_data = json.dumps({
                "type": "pipeline_request", "task_id": pid,
                "requirement_id": req.get("id", ""),
                "title": req.get("title", ""),
                "description": req.get("description", ""),
                "assignee": req.get("assignee", ""),
                "source": "dashboard",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })
            # 写入 Panda inbox
            panda_queue = Path(MESH_DIR) / "inbound" / "panda" / "queue"
            panda_queue.mkdir(parents=True, exist_ok=True)
            msg = {
                "id": str(_uuid.uuid4()), "from": "dashboard", "to": "panda",
                "body": f"@panda 新Pipeline请求: {req_data}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "delivery_count": 0, "ttl": 3600,
            }
            with open(panda_queue / f"msg_{_uuid.uuid4()}.json", "w") as f:
                json.dump(msg, f)
            logger.info(f"📋 自动启动未处理的 Pipeline: {pid} ({req.get('title','')[:30]})")


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    global mesh
    global mesh
    logger.info("🚀 ZooMesh 守护进程启动中...")

    mesh = ZooMesh()
    mesh.init(MESH_DIR)

    # 启动时扫描未启动的 Pipeline 请求
    _scan_pending_requirements()

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
            _scan_pending_requirements()
            _dispatch_pending_agents()
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号")


if __name__ == "__main__":
    main()
