"""Develop 阶段执行器。

负责开发阶段：代码实现、单元测试、集成测试。
直接调用 Claude Code 执行实际开发任务。
"""

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

# ---- Project paths ----
FEIDA_ZOO_ROOT = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo"))
FRAMEWORK_DIR = FEIDA_ZOO_ROOT / "framework"
DASHBOARD_DATA_DIR = FEIDA_ZOO_ROOT / "dashboard" / "data"

# ---- Claude Code binary ----
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/opt/homebrew/bin/claude")

# ---- ZooMesh (lazy init to avoid import order issues) ----
_zoo_mesh_instance = None


def _get_zoo_mesh():
    """延迟加载 ZooMesh 单例。"""
    global _zoo_mesh_instance
    if _zoo_mesh_instance is None:
        from core.mesh.zoo_mesh import ZooMesh
        ZooMesh._reset_instance()
        _zoo_mesh_instance = ZooMesh()
        mesh_dir = os.environ.get("ZOO_MESH_DIR", str(Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")).parent / "panda" / "zoo_mesh"))
        _zoo_mesh_instance.init(str(mesh_dir))
    return _zoo_mesh_instance


def _load_requirement(pipeline_id: str) -> Optional[dict]:
    """根据 pipeline_id 查找对应的 requirement。"""
    reqs_file = DASHBOARD_DATA_DIR / "requirements.json"
    if not reqs_file.exists():
        return None
    try:
        with open(reqs_file, encoding="utf-8") as f:
            reqs = json.load(f)
        for req in reqs:
            if req.get("pipeline_id") == pipeline_id:
                return req
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _send_completion_to_alpha(task_id: str, success: bool, output: str) -> None:
    """通知 Alpha（自身）开发阶段完成。"""
    mesh = _get_zoo_mesh()
    status = "success" if success else "failed"
    body = (
        f"PI_DONE:{task_id}\n"
        f"Phase: develop\n"
        f"status: {status}\n"
        f"output: {output[:500]}"
    )
    mesh.send("alpha", "develop_executor", body)


# ---- Claude Code 任务描述构建 ----

def _build_claude_task(requirement: dict, task_id: str) -> str:
    """根据 requirement 构建 Claude Code 指令。"""
    title = requirement.get("title", "")
    description = requirement.get("description", "")
    req_id = requirement.get("id", "")

    # 从 task_id 提取有意义的项目目录
    # pipeline_id 格式: pl_<8hex>
    project_hint = ""
    # 尝试从 description 或 title 推断项目
    if "dashboard" in title.lower() or "仪表盘" in title:
        project_hint = "feida_zoo/dashboard"
    elif "framework" in title.lower():
        project_hint = "feida_zoo/framework"
    else:
        project_hint = "feida_zoo"

    return f"""🐢 开发任务 — {title}

## 任务标识
pipeline_id: {task_id}
requirement_id: {req_id}

## 需求描述
{description if description else '(无详细描述)'}

## 执行要求
1. 进入项目目录: ~/workspace/code/{project_hint}
2. 按照需求描述实现功能
3. 如需修改多个文件，确保一致性
4. 完成后输出总结

## 注意事项
- 不要创建无关文件
- 遵循项目现有代码风格
- 如遇问题记录到输出中
""".strip()


# ---- Claude Code 异步执行器 ----

def _run_claude_code_async(task_id: str, claude_task: str) -> None:
    """后台异步运行 Claude Code（不阻塞 Pipeline 推进）。"""
    thread = threading.Thread(
        target=_exec_claude_code,
        args=(task_id, claude_task),
        daemon=True,
    )
    thread.start()


def _exec_claude_code(task_id: str, task: str) -> None:
    """在后台线程中执行 Claude Code。"""
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("develop_executor")

    logger.info(f"[develop] 🤖 启动 Claude Code for {task_id}")

    # 构造 Claude Code 命令
    # 使用 --print 输出结果，--permission-mode bypassPermissions 跳过确认
    cmd = [
        CLAUDE_BIN,
        "--print",
        "--permission-mode", "bypassPermissions",
        "--verbose",
        task,  # 直接作为命令传入
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            cwd=str(FEIDA_ZOO_ROOT),
        )
        if result.returncode == 0:
            logger.info(f"[develop] ✅ Claude Code 完成: {task_id}")
            output = result.stdout if result.stdout else "(无输出)"
            _send_completion_to_alpha(task_id, True, output)
        else:
            logger.warning(f"[develop] ❌ Claude Code 失败 (exit {result.returncode}): {task_id}")
            output = result.stderr if result.stderr else "(无错误信息)"
            _send_completion_to_alpha(task_id, False, output)
    except subprocess.TimeoutExpired:
        logger.error(f"[develop] ⏰ Claude Code 超时: {task_id}")
        _send_completion_to_alpha(task_id, False, "TIMEOUT: 任务超过10分钟被强制终止")
    except Exception as e:
        logger.error(f"[develop] 💥 Claude Code 异常: {task_id} — {e}")
        _send_completion_to_alpha(task_id, False, f"EXCEPTION: {e}")


# ---- PhaseExecutor 实现 ----

from framework.core.harness.phase_executor import PhaseExecutor
from framework.core.harness.pipeline import ZooPipeline


class DevelopExecutor(PhaseExecutor):
    """开发阶段执行器 — 直连 Claude Code。"""

    def __init__(
        self,
        pipeline: ZooPipeline,
        zoo_mesh=None,
    ):
        super().__init__(pipeline, "develop", zoo_mesh)

    def execute(self) -> bool:
        """
        执行开发阶段。

        工作流程：
        1. 发布 phase_started 事件
        2. 根据 pipeline.task_id 查找 requirement
        3. 构造 Claude Code 指令并后台异步执行
        4. 立即返回 True（异步执行不阻塞 Pipeline）
           Pipeline 将在收到 PI_DONE 消息后推进到下一阶段

        Returns:
            True（表示已启动异步执行，Pipeline 继续）
        """
        import logging
        logger = logging.getLogger("develop_executor")

        task_id = self.pipeline.task_id
        logger.info(f"[develop] 🚀 start task_id={task_id}")

        # 1. 发布阶段开始事件
        self.zoo_mesh.publish_event(
            "phase_started",
            {
                "task_id": task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
            },
        )

        # 2. 查找 requirement 详情
        requirement = _load_requirement(task_id)
        if not requirement:
            logger.warning(f"[develop] 无法找到 requirement for {task_id}，使用默认任务")
            claude_task = f"开发任务 {task_id}（无详细描述）"
        else:
            claude_task = _build_claude_task(requirement, task_id)

        # 3. 后台异步启动 Claude Code
        _run_claude_code_async(task_id, claude_task)
        logger.info(f"[develop] 🐢 Claude Code 已后台启动，task_id={task_id}")

        # 4. 立即返回（异步执行不等待）
        # Pipeline 通过 _on_wakeup → _handle_phase_complete 接收 PI_DONE 消息推进
        return True

    def execute_sync(self) -> bool:
        """
        同步执行版本（仅用于测试/调试）。
        阻塞直到 Claude Code 执行完成。
        """
        import logging
        logger = logging.getLogger("develop_executor")
        logger.info(f"[develop][sync] 🚀 start task_id={self.pipeline.task_id}")

        task_id = self.pipeline.task_id
        requirement = _load_requirement(task_id)

        if requirement:
            claude_task = _build_claude_task(requirement, task_id)
        else:
            claude_task = f"开发任务 {task_id}"

        cmd = [
            CLAUDE_BIN,
            "--print",
            "--permission-mode", "bypassPermissions",
            claude_task,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(FEIDA_ZOO_ROOT),
        )

        success = result.returncode == 0
        output = result.stdout if success else (result.stderr or "(无输出)")
        _send_completion_to_alpha(task_id, success, output)

        # 发布阶段完成事件
        self.zoo_mesh.publish_event(
            "phase_completed",
            {
                "task_id": task_id,
                "phase": self.phase_name,
                "agent_id": self.pipeline.agent_id,
                "status": "success" if success else "failed",
            },
        )
        return success