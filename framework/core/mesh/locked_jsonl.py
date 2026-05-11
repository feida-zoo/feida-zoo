"""线程/进程安全的 JSONL 写入器。

使用 fcntl.flock 确保并发写入安全，自动处理行交错、半写等问题。
设计约束来自文档 §2.6。
"""

import fcntl
import json
import os
from typing import List


class LockedJsonlWriter:
    """线程/进程安全的 JSONL 写入器。

    写入时使用 fcntl.LOCK_EX 排他锁，读取时使用 fcntl.LOCK_SH 共享锁，
    写入后调用 os.fsync 强制刷盘，保证数据不丢失。
    """

    def __init__(self, path: str):
        self.path = path

    def append(self, event: dict) -> None:
        """追加一条事件到 JSONL 文件。"""
        with open(self.path, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_all(self) -> List[dict]:
        """读取所有事件，加共享锁防止读写冲突。"""
        if not os.path.exists(self.path):
            return []

        events = []
        with open(self.path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return events

    def read_recent(self, limit: int = 50) -> List[dict]:
        "Read last `limit` lines with shared lock."
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                lines = f.readlines()
                recent = [json.loads(l) for l in lines[-limit:] if l.strip()]
                return recent
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

