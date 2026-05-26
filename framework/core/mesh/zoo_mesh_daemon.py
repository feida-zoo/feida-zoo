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

# 阶段 → 默认执行 Agent（从 zoo_members.yaml 的 responsible_phases 推导）
# 参见 ZooRegistry.get_phase_agent()


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
    """检查 body 是否包含 phase_complete 信号（兼容 markdown bold / plain 等格式）。"""
    if not body:
        return False
    # 去掉 markdown bold/italic 标记再检查
    body_clean = body.strip().strip("*_").split()[0] if body.strip() else ""
    for sig in PHASE_COMPLETE_SIGNALS:
        if body_clean.startswith(sig):
            return True
    # 备选：只要包含 phase_complete:pl_ 就通过（信号本身格式正确）
    if "phase_complete:" in body and "pl_" in body:
        return True
    return False


_NOTIFY_LOG: set = set()





# 派发记录：pipeline_id → (next_phase, last_dispatched_ts)，用于卡死检测
_DISPATCH_LOG: dict = {}


def _panda_relay_post(next_agent: str, pipeline_id: str, phase: str,
                           next_phase: str, cur_req: dict) -> None:
    """通知下一阶段 Agent 的 main session。

    Agent 完成任务后必须用 HTTP POST 回 daemon /phase_complete 端点，
    不再依赖 CLI stdout 抓取（fire-and-forget 拿不到异步回复）。
    """
    import subprocess as _sp

    project_key = cur_req.get("project", "feida_zoo")

    # 使用统一的 _build_phase_message 生成完整 prompt（含项目路径/I/O 约定 + curl 示例）
    next_msg = _build_phase_message(next_phase, pipeline_id, cur_req, project_key)

    oc_bin = "/opt/homebrew/bin/openclaw"
    try:
        result = _sp.run(
            [oc_bin, "agent", "--agent", next_agent, "-m", next_msg],
            capture_output=True, text=True, timeout=30
        )
        logger.info(f"✅ relay → {next_agent} (phase={next_phase}): dispatched")
        # 记录派发时间，供 _check_stuck_pipelines 判断是否需要重发
        _DISPATCH_LOG[pipeline_id] = (next_phase, time.time())
    except _sp.TimeoutExpired:
        logger.warning(f"⚠️ relay → {next_agent} CLI 超时（任务可能已下发，依赖 Agent POST 回信号）")
        _DISPATCH_LOG[pipeline_id] = (next_phase, time.time())
    except Exception as e:
        logger.warning(f"⚠️ relay → {next_agent} 失败: {e}")



def _extract_pipeline_id(body: str) -> str | None:
    """从消息中提取 pipeline_id（pl_xxxxxxxx）。"""
    for token in body.split():
        if token.startswith("pl_"):
            return token
    m = re.search(r'(pl_[a-f0-9]+)', body)
    return m.group(1) if m else None


def _capture_phase_complete_from_output(stdout: str, agent_id: str) -> None:
    """已废弃（保留函数名避免外部调用报错）。

    原意是从 relay CLI stdout 里拓 phase_complete，但 fire-and-forget 调用拿不到异步回复。
    改为依赖 Agent 主动 POST /phase_complete。
    """
    pass


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


def _clear_pending_for_pipeline(pipeline_id: str) -> int:
    """清理 pending 队列中指定 pipeline_id 的所有条目。返回清理数量。"""
    queue = _load_pending_queue()
    before = len(queue)
    queue = [t for t in queue if t.get("pipeline_id") != pipeline_id]
    removed = before - len(queue)
    if removed > 0:
        _save_pending_queue(queue)
        logger.info(f"🧹 已清理 pending 队列中 {pipeline_id} 的 {removed} 条残留")
    return removed


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


# ── Pipeline 辅助函数 ────────────────────────────────────────────────────────────

# 项目路径映射（按 project_key 索引，可在创建需求时指定 project 字段）
PROJECTS = {
    "feida_zoo": {
        "path": str(Path(FRAMEWORK_DIR).parent),
        "artifacts_dir": "framework/shared",
    },
    "panda": {
        "path": "/Users/zoo/workspace/members/panda",
        "artifacts_dir": "memory",
    },
}


def _get_project_info(project_key: str = "feida_zoo") -> dict:
    """返回项目的路径配置。"""
    return PROJECTS.get(project_key, PROJECTS["feida_zoo"])



def _get_artifact_paths(pipeline_id: str, phase: str, project_key: str = "feida_zoo", prev_phase: str = "") -> dict:
    """根据阶段和执行轮次返回 I/O 路径。
    
    prev_phase: 驳回场景下传入被驳回的审查阶段，用于确定正确的输入文件。
    执行轮次通过实际存在的文件动态计算（v2/v3/...）。
    """
    project = _get_project_info(project_key)
    base = f"{project['path']}/{project['artifacts_dir']}"
    pid = pipeline_id

    # 动态计算执行轮次（检查已存在的 artifact 文件）
    def _version_suffix(phase_name: str) -> str:
        base_name = f"{base}/{pid}_{phase_name}"
        if os.path.exists(f"{base_name}.md"):
            return ""  # 第一版无后缀
        for v in range(2, 20):
            if os.path.exists(f"{base_name}_v{v}.md"):
                return f"_v{v}"
        return ""

    # 确定输入文件：驳回场景用 prev_phase 的输出，正常流程用 phase 自身的 version
    if prev_phase:
        in_suffix = _version_suffix(prev_phase)
        in_file = f"{base}/{pid}_{prev_phase}{in_suffix}.md"
    else:
        in_suffix = _version_suffix(phase)
        # 正常流程：输入是上一道工序的输出（根据标准链路）
        normal_input_map = {
            "design":        f"{base}/{pid}_validate{in_suffix}.md",
            "ui_design":     f"{base}/{pid}_design{in_suffix}.md",
            "review":        f"{base}/{pid}_design{in_suffix}.md",
            "develop_wt":    f"{base}/{pid}_design{in_suffix}.md",
            "review_test":   f"{base}/{pid}_design{in_suffix}.md",
            "develop_code":  f"{base}/{pid}_design{in_suffix}.md",
            "test":          f"{base}/{pid}_develop_code{in_suffix}.md",
            "audit":         f"{base}/{pid}_develop_code{in_suffix}.md",
            "final_check":   f"{base}/{pid}_audit{in_suffix}.md",
        }
        in_file = normal_input_map.get(phase, None)

    # 输出文件
    out_suffix = _version_suffix(phase)
    output_none_phases = {"develop_wt", "review_test", "develop_code"}

    table = {
        "validate":      {"input": None,                              "output": f"{base}/{pid}_validate{_version_suffix('validate')}.md"},
        "design":        {"input": in_file,                           "output": f"{base}/{pid}_design{out_suffix}.md"},
        "ui_design":     {"input": in_file,                           "output": f"{base}/{pid}_ui_design{out_suffix}.md"},
        "review":        {"input": in_file,                           "output": f"{base}/{pid}_review{out_suffix}.md"},
        "develop_wt":    {"input": in_file,                           "output": None},
        "review_test":   {"input": in_file,                           "output": None},
        "develop_code":  {"input": in_file,                           "output": None},
        "test":          {"input": in_file,                           "output": f"{base}/{pid}_test{out_suffix}.md"},
        "audit":         {"input": in_file,                           "output": f"{base}/{pid}_audit{out_suffix}.md"},
        "final_check":   {"input": in_file,                           "output": f"{base}/{pid}_final_check{out_suffix}.md"},
    }
    return table.get(phase, {"input": None, "output": None})



def _build_io_block(pipeline_id: str, phase: str, project_key: str = "feida_zoo", prev_phase: str = "") -> str:
    """生成项目中 I/O 路径信息块，供模板使用。"""
    project = _get_project_info(project_key)
    paths = _get_artifact_paths(pipeline_id, phase, project_key, prev_phase=prev_phase)
    project_dir = project["path"]

    lines = [f"项目路径: {project_dir}"]
    if paths["input"]:
        lines.append(f"输入文件: {paths['input']}")
    if paths["output"]:
        lines.append(f"输出文件: {paths['output']}（必须写入此文件，源码除外）")
    else:
        lines.append("输出: 直接写入源码目录（见项目路径下的具体文件）")
    return "\n".join(lines) + "\n"


def _build_phase_message(phase: str, pipeline_id: str, requirement: dict, project_key: str = "feida_zoo", extra_context: str = "", prev_phase: str = "") -> str:
    """构建发给 Agent 的完整阶段消息（统一入口）。"""
    template = _get_phase_template(phase, pipeline_id, project_key, prev_phase=prev_phase)
    curl_example = (
        f"curl -X POST http://127.0.0.1:{HTTP_PORT}/phase_complete "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"pipeline_id\":\"{pipeline_id}\",\"result\":\"pass\",\"agent_id\":\"<your_agent_id>\"}}'"
    )
    # 全局幂等约束：防止 Agent 看到输出文件已存在就跳过内容核对
    idempotency_warning = (
        "⚠️ 幂等约束：即使输出文件已存在，也必须读取并确认内容符合当前阶段要求。"
        "如果内容匹配则可复用，否则必须覆盖重写。禁止仅凭文件存在就跳过工作直接上报。\n"
    )
    return (
        f"[Pipeline] Phase: {phase}\n"
        f"task_id: {pipeline_id}\n"
        f"requirement_id: {requirement.get('id', '')}\n"
        f"title: {requirement.get('title', '')}\n"
        f"description: {requirement.get('description', '')}\n"
        f"指令: 请执行 {phase} 阶段，完成后必须用 curl POST 上报 daemon（禁止用对话回复）\n"
            f"上报命令（复制后把 result 改为 pass 或 reject，agent_id 填你的短名如 alpha/duci/panda/weaver/aeterna/gulu，不是 session key）：\n"
        f"  {curl_example}\n"
        f"{idempotency_warning}"
        f"{template}"
        f"{extra_context}"
    )


def _get_phase_template(phase: str, pipeline_id: str = "", project_key: str = "feida_zoo", prev_phase: str = "") -> str:
    """根据阶段返回对应的指令模板（动态注入项目路径和 I/O）。"""
    io = _build_io_block(pipeline_id, phase, project_key, prev_phase=prev_phase)

    templates = {
        "validate": (
            f"{io}"
            "【Validate 阶段 - 需求评审】\n"
            "- 可行性：需求是否可实现，有无技术障碍\n"
            "- 依赖项：需要哪些前置条件\n"
            "- 风险点：可能踩坑的地方\n"
            "- 建议优先级：P0 / P1 / P2 / P3\n"
        ),
        "design": (
            f"{io}"
            "【Design 阶段 - 架构设计】\n"
            "- What: 具体要做什么改动\n"
            "- Why: 为什么要这么做（背景、解决的问题）\n"
            "- Tradeoff: 放弃了什么方案，做了什么权衡\n"
            "- 接口定义: 新增/修改的函数、类、API\n"
            "- 文件清单: 需要新增/修改的文件及路径\n"
            "- Open Questions: 不确定点和遗留问题\n"
            "- Next Action: 希望审计方重点审查什么\n"
        ),
        "ui_design": (
            f"{io}"
            "【UI Design 阶段 - 界面设计】\n"
            "- 页面布局: 组件结构和位置\n"
            "- 交互逻辑: 用户操作流程\n"
            "- 状态定义: 各状态下的 UI 表现\n"
            "- 视觉说明: 风格、颜色等\n"
        ),
        "review": (
            f"{io}"
            "【Review 阶段 - 设计评审】\n"
            "请阅读输入文件，产出审查报告：\n"
            "- 架构合理性\n"
            "- 安全风险\n"
            "- 遗漏检查\n"
            "- 改进建议\n"
            "- 结论: pass / reject（reject 需说明原因）\n"
        ),
        "develop_wt": (
            f"{io}"
            "【Develop WT 阶段 - 编写测试用例】\n"
            "请根据设计文档编写测试用例：\n"
            "- 覆盖所有验收标准\n"
            "- 含单元测试 + 集成测试\n"
            "- 测试代码写入项目 tests/ 目录\n"
        ),
        "review_test": (
            f"{io}"
            "【Review Test 阶段 - 测试评审】\n"
            "请评审测试用例质量：\n"
            "- 覆盖度\n"
            "- 边界用例\n"
            "- 结论: pass / reject\n"
        ),
        "develop_code": (
            f"{io}"
            "【Develop Code 阶段 - 编写实现代码】\n"
            "请根据设计文档编写实现代码，写入源码目录：\n"
            "- 测试用例全部通过\n"
            "- 不破坏现有功能\n"
        ),
        "test": (
            f"{io}"
            "【Test 阶段 - 测试执行】\n"
            "请执行所有测试用例，产出测试报告：\n"
            "- 通过率\n"
            "- 失败用例分析\n"
        ),
        "audit": (
            f"{io}"
            "【Audit 阶段 - 代码审计】\n"
            "请审计实现代码：\n"
            "- 安全漏洞（SQL注入、XSS、硬编码密钥等）\n"
            "- 代码质量（命名、结构、可维护性）\n"
            "- 性能风险\n"
            "- 结论: pass / reject\n"
        ),
        "final_check": (
            f"{io}"
            "【Final Check 阶段 - 最终验收】\n"
            "请做最终检查：\n"
            "- 所有 phase 是否完成\n"
            "- 代码是否干净可交付\n"
            "- git commit 是否包含所有产出（包括审查文档）\n"
            "- 修改的服务/进程是否需要重启才能生效？如果是，必须重启并验证\n"
            "- 端到端验证：curl 或其他方式确认修复确实生效\n"
            "- 如果修改了 daemon 代码，必须按技能文件正确重载：\n"
            "  `skills/zoo-daemon-reload.md`（网关重启不够，必须 kill 旧 daemon 进程）\n"
            "- 结论: pass / reject\n"
        ),
        "deliver": (
            f"{io}"
            "【Deliver 阶段 - 交付】\n"
            "交付前必须完成以下检查，缺一不可：\n"
            "1. git commit：确保所有产出已提交（代码+测试+所有 pipeline 文档，包括审查方写的 audit/test/review 文件）\n"
            "2. 重启服务：如果修改了运行中的服务代码（如 dashboard、daemon），必须重启该进程使修改生效\n"
            "   ⚠️ 特别注意：修改 daemon 代码时，网关重启不够，必须 kill 旧 daemon 进程让 plugin 重新拉起。\n"
            "   详见技能文件：`skills/zoo-daemon-reload.md`\n"
            "3. 端到端验证：重启后用 curl 或实际操作确认修复生效\n"
            "4. 在输出文件中记录：commit hash、重启的进程、端到端验证结果\n"
            "完成后上报 phase_complete\n"
        ),
    }

    if phase in templates:
        t = templates[phase]
        if pipeline_id:
            t = t.replace("{pipeline_id}", pipeline_id)
        return t

    # 未知阶段 fallback
    fallback = f"{io}【{phase.title()} 阶段】\n请执行 {phase} 阶段，完成后回复 phase_complete:{pipeline_id}\n"
    return fallback


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
    from framework.core.mesh.zoo_registry import ZooRegistry
    return ZooRegistry().get_phase_agent(phase)


def _pick_phase_agent(phase: str) -> str:
    """当不涉及特定 requirement 时，根据阶段选择默认 Agent。
    
    从 zoo_members.yaml 的 responsible_phases 反向推导。
    未匹配阶段 → 返回 'panda'（全局 fallback）。
    """
    from framework.core.mesh.zoo_registry import ZooRegistry
    return ZooRegistry().get_phase_agent(phase)


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
                # _send_agent_notification 已移除，改由 Panda relay 处理
                pass
            else:
                # Panda 的未分类消息 — 仅通知（类型 3 已从设计文档彻底移除）
                logger.info(f"Panda 未分类消息，仅通知: {body[:80]}")
                pass
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
        project_key = cur_req.get("project", "feida_zoo")
        phase_msg = _build_phase_message("validate", task_id, cur_req, project_key)
        try:
            _panda_relay_post(phase_assignee, task_id, "request", "validate", cur_req)
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

    # ── 并发安全：二次检查 state 文件，防止竞态覆盖 ──
    state_now = mesh.get_pipeline_state(pipeline_id)
    if state_now == "done":
        logger.info(f"Pipeline {pipeline_id} state 文件已 done，跳过重复处理")
        return

    current_status = cur_req.get("status", "request")
    # ── 幂等校验：已 done 的 pipeline 拒绝重复上报 ──
    if current_status == "done":
        logger.info(f"Pipeline {pipeline_id} 已终态 done，忽略来自 {agent_id} 的重复 phase_complete")
        return  # 调用方（HTTP handler）单独处理响应

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

        # 清理 pending 队列中该 pipeline 的所有残留条目
        _clear_pending_for_pipeline(pipeline_id)

        logger.info(f"🏁 Pipeline {pipeline_id} 已完成！")
        return

    # Pipeline V2: 检查审查结果（review/review_test/audit 阶段推进时）
    if current_status in ("review", "review_test", "test", "audit"):
        # 验证信号发送者：只接受该阶段的默认 Agent
        # 宽松匹配：session key 格式如 'agent:duci:main' 自动剥离为 'duci'
        expected_agent = _pick_phase_agent(current_status)
        normalized_agent = agent_id
        if ":" in agent_id:
            # 提取 agent:<name>:... 中间部分
            parts = agent_id.split(":")
            if len(parts) >= 2 and parts[0] == "agent":
                normalized_agent = parts[1]
        if normalized_agent != expected_agent:
            logger.warning(f"Pipeline {pipeline_id}: {current_status} 阶段拒绝来自 {agent_id} 的信号（期望 {expected_agent}）")
            return
        # 后续逻辑统一使用 normalized_agent
        agent_id = normalized_agent
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
        rejection_context = ""
        if result == "reject":
            # 驳回：注入审查反馈，让下一阶段知道为什么被驳回
            rejection_context = (
                f"\n\n⚠️ 【审查驳回原因】（请在下一阶段重点关注）\n"
                f"审查阶段：{current_status}\n"
                f"审查结论：reject\n"
                f"{review_data.get('comments', []) if isinstance(review_data.get('comments'), str) else ''}\n"
                f"完整审查报告见：{MESH_DIR}/pipeline/{current_status}_{pipeline_id}.json\n"
            )
            fallback_map = {
                "review": "design",
                "review_test": "develop_wt",
                "test": "develop_code",
                "audit": "develop_code",
            }
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
                    next_msg = _build_phase_message(fallback, pipeline_id, cur_req, cur_req.get("project", "feida_zoo"), extra_context=rejection_context, prev_phase=current_status)
                    _panda_relay_post(next_agent, pipeline_id, current_status, fallback, cur_req)
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
    project_key = cur_req.get("project", "feida_zoo")
    next_msg = _build_phase_message(next_phase, pipeline_id, cur_req, project_key, prev_phase=current_status if current_status in ("review", "review_test", "test", "audit") else "")

    try:
        _panda_relay_post(next_agent, pipeline_id, current_status, next_phase, cur_req)
        logger.info(f"已通知 {next_agent} 执行 {next_phase} 阶段")
    except Exception as e:
        logger.warning(f"通知 {next_agent} 失败: {e}")

    try:
        _panda_relay_post(next_agent, pipeline_id, current_status, next_phase, cur_req)
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
                    msg = _build_phase_message(next_phase, pid, r, r.get("project", "feida_zoo"))
                    _panda_relay_post(next_agent, pid, next_phase, next_phase, r)
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

        # /relay: ZooMesh daemon relay 端点，通过 sessions_send CLI 直接联系 Alpha/Duci 的 main session
        if parsed.path == "/relay":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
            except Exception as e:
                logger.warning(f"/relay JSON parse error: {e}, body={body!r}")
                self._json(400, {"error": "invalid json", "detail": str(e)})
                return

            to_agent = data.get("to", "")
            pipeline_id = data.get("pipeline_id", "")
            phase = data.get("phase", "")
            msg = data.get("message", "")

            if not to_agent or not msg:
                self._json(400, {"error": "missing to or message"})
                return

            # 通过 openclaw agent 直接联系 to_agent 的 main session
            # Alpha/Duci 后续工作走 main session，绕开 QQ Bot
            import subprocess as _sp
            oc_bin = "/opt/homebrew/bin/openclaw"
            try:
                result = _sp.run(
                    [oc_bin, "agent", "--agent", to_agent, "-m", msg],
                    capture_output=True, text=True, timeout=30
                )
                logger.info(f"✅ relay → {to_agent} (phase={phase}): stdout={len(result.stdout)}chars")

                # 从 stdout 中捕获 phase_complete 信号并触发推进
                if result.stdout:
                    _capture_phase_complete_from_output(result.stdout, to_agent)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                resp_data = json.dumps({
                    "status": "ok",
                    "agent": to_agent,
                    "pipeline_id": pipeline_id,
                    "phase": phase,
                    "stdout": result.stdout[:500] if result.stdout else "",
                }, ensure_ascii=False).encode()
                self.wfile.write(resp_data)
            except _sp.TimeoutExpired:
                logger.warning(f"⚠️ relay → {to_agent} 超时")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "timeout", "agent": to_agent}).encode())
            except Exception as e:
                logger.warning(f"⚠️ relay → {to_agent} 失败: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        # /phase_complete: Agent 任务完成后直接通知 daemon 推进 pipeline
        if parsed.path == "/phase_complete":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
            except Exception as e:
                logger.warning(f"/phase_complete JSON parse error: {e}")
                self._json(400, {"error": "invalid json"})
                return

            pipeline_id = data.get("pipeline_id", "")
            result = data.get("result", "pass")  # pass or reject
            agent_id = data.get("agent_id", "unknown")

            if not pipeline_id:
                self._json(400, {"error": "missing pipeline_id"})
                return

            # Agent 主动通知 daemon 推进，直接构造信号触发 _handle_phase_complete
            signal_body = f"phase_complete:{pipeline_id}:{result}"
            logger.info(f"📡 Agent {agent_id} 直接通知 phase_complete: {signal_body}")

            # 幂等校验：已 done 的 pipeline 不接受重复上报
            reqs_check = _load_requirements()
            already_done = False
            for r in reqs_check:
                if r.get("pipeline_id") == pipeline_id and r.get("status") == "done":
                    already_done = True
                    break
            if already_done:
                self._json(200, {"status": "already_done", "pipeline_id": pipeline_id, "hint": "pipeline 已终态，phase_complete 被忽略"})
                return

            try:
                _handle_phase_complete(signal_body, agent_id)
                self._json(200, {"status": "ok", "pipeline_id": pipeline_id, "result": result})
            except Exception as e:
                logger.warning(f"/phase_complete 处理失败: {e}")
                self._json(500, {"error": str(e)})
            return

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
    from framework.core.mesh.zoo_registry import ZooRegistry
    try:
        agent_ids = ZooRegistry().list_agents()
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
            _panda_relay_post(agent_id, pipeline_id, phase, phase, cur_req)
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
def _check_stuck_pipelines() -> None:
    """检测卡住的 pipeline，重新派发。

    判定为卡住的条件：
    1. requirement.status 非 done/cancelled
    2. 超过 30 分钟未更新 (updated_at)
    3. 负责人不在 pending 队列里（避免打扰正在排队的任务）
    4. 本轮 _DISPATCH_LOG 里记录的上次派发超过 30 分钟前

    命中后调用 _panda_relay_post 重新发送当前阶段指令。
    """
    from datetime import datetime
    STUCK_THRESHOLD_SEC = 30 * 60  # 30 分钟

    reqs = _load_requirements()
    if not reqs:
        return

    pending_assignees = {item.get("assignee") for item in _load_pending_queue() if item.get("assignee")}
    now = time.time()
    stuck_count = 0

    for req in reqs:
        status = req.get("status", "")
        if status in ("done", "cancelled", "request", ""):
            continue
        pipeline_id = req.get("pipeline_id", "")
        if not pipeline_id:
            continue
        # 当前阶段的负责人（不是需求原始 assignee）
        # 例如：review/audit/test 阶段负责人是 duci，而不是需求的 owner
        phase_agent = _pick_phase_agent(status)
        assignee = phase_agent or req.get("assignee", "")
        if not assignee:
            continue
        # 负责人有其他 pending 任务 → 在忙，跳过
        if assignee in pending_assignees:
            logger.info(f"⏭️ stuck 检测：{pipeline_id} 负责人 {assignee} 在忙，跳过")
            continue

        # 检查 updated_at
        updated_at = req.get("updated_at", "")
        try:
            # 兼容 "2026-05-20T20:04:33" / "2026-05-20T20:04:33+0000" 等格式
            updated_str = updated_at.split("+")[0].split("Z")[0]
            updated_ts = datetime.fromisoformat(updated_str).timestamp()
        except Exception:
            updated_ts = 0

        age_sec = now - updated_ts
        if age_sec < STUCK_THRESHOLD_SEC:
            continue

        # 检查本进程 _DISPATCH_LOG 是否最近派过
        last_dispatch = _DISPATCH_LOG.get(pipeline_id)
        if last_dispatch:
            last_phase, last_ts = last_dispatch
            if last_phase == status and (now - last_ts) < STUCK_THRESHOLD_SEC:
                continue

        # 命中卡死 → 重新派发
        logger.warning(
            f"🚨 stuck pipeline：{pipeline_id} status={status} assignee={assignee} "
            f"age={int(age_sec/60)}min，重新派发"
        )
        try:
            _panda_relay_post(assignee, pipeline_id, status, status, req)
            stuck_count += 1
        except Exception as e:
            logger.warning(f"stuck 重发失败 {pipeline_id}: {e}")

    if stuck_count > 0:
        logger.info(f"🔄 本轮 stuck 检测重发 {stuck_count} 个任务")


# 上次 stuck 扫描时间
_LAST_STUCK_CHECK_TS = 0.0


def main():
    global mesh
    global mesh
    logger.info("🚀 ZooMesh 守护进程启动中...")

    mesh = ZooMesh()
    mesh.init(MESH_DIR)

    # 启动时扫描未启动的 Pipeline 请求
    _scan_pending_requirements()

    # Daemon threads
    # ── InboxWatcher (含 Pipeline 全自动驱动回调) ──
    # InboxWatcher 内部拼接 <mesh_dir>/<agent_id>/queue
    # 传入 MESH_DIR/inbound 确保路径正确
    iw = InboxWatcher(str(Path(MESH_DIR) / "inbound"), on_wakeup=_on_wakeup_callback)
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

    # 启动时立即检测一次卡死 pipeline（0min）
    global _LAST_STUCK_CHECK_TS
    try:
        _check_stuck_pipelines()
    except Exception as e:
        logger.warning(f"启动时 _check_stuck_pipelines 失败: {e}")
    _LAST_STUCK_CHECK_TS = time.time()

    try:
        while True:
            time.sleep(60)
            _scan_pending_requirements()
            _dispatch_pending_agents()
            # 每 30 分钟检测一次卡死 pipeline（30min, 60min, ...）
            if time.time() - _LAST_STUCK_CHECK_TS >= 30 * 60:
                try:
                    _check_stuck_pipelines()
                except Exception as e:
                    logger.warning(f"_check_stuck_pipelines 失败: {e}")
                _LAST_STUCK_CHECK_TS = time.time()
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号")


if __name__ == "__main__":
    main()
