"""
task_tracker 持久化模块
基于 fcntl.flock 文件锁，支持多进程安全读写。

设计目标：
- 原子写入（temp file + os.rename）
- 文件锁防止并发损坏
- 支持任务状态原地更新
"""

import fcntl
import json
import os
import tempfile
from typing import Any, Dict

TRACKER_PATH = "docs/pipeline/task_tracker.json"


def save_task_tracker(data: Dict[str, Any]) -> None:
    """原子写入 task_tracker：temp file + os.rename。

    Args:
        data: task_tracker 数据字典
    """
    path = TRACKER_PATH
    dirname = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirname, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.rename(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_task_tracker() -> Dict[str, Any]:
    """带共享锁读取 task_tracker。

    Returns:
        task_tracker 数据字典
    """
    path = TRACKER_PATH
    with open(path) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return data


def update_task_status(task_id: str, status: str, notes: str = "") -> None:
    """更新指定任务的状态与备注。

    Args:
        task_id: 任务 ID（如 "3.2.2"）
        status: 新状态（如 "in_progress" / "completed"）
        notes: 备注信息（可选）
    """
    data = load_task_tracker()
    found = False
    for phase_key in ("P1", "P2", "P3"):
        phase = data.get("phases", {}).get(phase_key, {})
        for task in phase.get("tasks", []):
            if task.get("id") == task_id:
                task["status"] = status
                if notes:
                    task["notes"] = notes
                found = True
                break
        if found:
            break
    save_task_tracker(data)
