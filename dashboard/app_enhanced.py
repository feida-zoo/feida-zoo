#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Dev-Center - 飝龘动物园研发中心 v1.0
增强版后端，包含 SSE 机制和四象限看板 API
"""

import sys
import json
import os
import time
import threading
import fcntl
import requests
from pathlib import Path
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Set
import queue

# ZooMesh HTTP endpoint
ZOO_MESH_HTTP = os.environ.get("ZOO_MESH_HTTP_URL", "http://127.0.0.1:18793")

# 导入 Git 适配器
from git_adapter import get_git_adapter, get_git_watcher

# 配置
PORT = 18792  # 使用新端口避免冲突
PROJECT_ROOT = Path(os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo"))

# 确保项目根目录在 sys.path 中，以便导入 framework 包
_project_root = str(PROJECT_ROOT)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 导入 ZooRegistry
from framework.core.mesh.zoo_registry import ZooRegistry

_DEFAULT_HOME = Path.home()
ZOO_MESH_DIR = Path(os.environ.get("ZOO_MESH_DIR", os.path.join(str(_DEFAULT_HOME), "workspace", "members", "panda", "zoo_mesh")))
PROJECT_AGENTS_DIR = ZOO_MESH_DIR / "agents"
REGISTRY_PATH = PROJECT_ROOT / "framework" / "data" / "registry.json"
TASK_TRACKER_PATH = ZOO_MESH_DIR / "dashboard" / "task_tracker.json"
AGENTS_DIR = ZOO_MESH_DIR / "agents"
TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
VALID_PRIORITIES = {'P0', 'P1', 'P2', 'P3'}

DATA_DIR = ZOO_MESH_DIR / "dashboard"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===== 成员信息（已迁移至 zoo_members.yaml） =====
# MEMBERS_INFO 已删除，数据来源为 ZooRegistry.get_full_info()
# 保留空 dict 作为极端情况下的 fallback
MEMBERS_INFO = {}

# Pipeline 阶段 → 看板列映射（5列合并精简版）
# 内部 Pipeline 状态不变，仅合并对外展示列
PIPELINE_PHASE_TO_COLUMN = {
    "request":     "request",
    "design":      "design",
    "review":      "develop",
    "develop_wt":  "develop",
    "verify":      "develop",
    "develop_code":"develop",
    "audit":       "audit",
    "deliver":     "done",
    "done":        "done",
    "rejected":    "rejected",
    "cancelled":   "cancelled",
    "timed_out":   "rejected",
    "escalated":   "develop",
}

# Pipeline 阶段 → 中文显示名（卡片级展示）
PHASE_TO_CHINESE = {
    "request":      "待处理",
    "design":       "设计中",
    "review":       "审查中",
    "develop_wt":   "开发中(WT)",
    "verify":       "验证中",
    "develop_code": "编码中",
    "audit":        "验收中",
    "deliver":      "交付中",
    "done":         "已完成",
    "rejected":     "🚫 已驳回",
    "cancelled":    "🗑️ 已取消",
    "timed_out":    "⏰ 已超时",
}

# 看板列定义（精简版5列，无异常独立列）
# 内部 Pipeline 状态不变，仅在对外展示时合并
# 异常状态（cancelled/timed_out/escalated）归入对应主列，卡片红色标识
KANBAN_STATUS = {
    "request":   "📥 需求池",
    "design":    "🎨 设计阶段",
    "develop":   "🔧 开发阶段",
    "audit":     "🔍 验收阶段",
    "rejected":  "🚫 已驳回",
    "cancelled": "🗑️ 已取消",
    "done":      "✅ 已完成",
}

# SSE 客户端管理器
class SSEManager:
    """Server-Sent Events 管理器"""
    
    def __init__(self):
        self.clients: Set = set()
        self.lock = threading.RLock()
    
    def add_client(self, client):
        """添加 SSE 客户端"""
        with self.lock:
            self.clients.add(client)
    
    def remove_client(self, client):
        """移除 SSE 客户端"""
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)
    
    def broadcast(self, event_type: str, data: dict):
        """向所有客户端广播事件"""
        with self.lock:
            dead_clients = []
            
            # 准备消息，处理 JSON 序列化错误
            try:
                # 使用 default=str 处理不可序列化对象，处理循环引用等错误
                json_data = json.dumps(data, ensure_ascii=False, default=str)
                message = f"event: {event_type}\ndata: {json_data}\n\n"
                message_bytes = message.encode('utf-8')
            except Exception as e:
                print(f"SSE 消息序列化错误: {e}")
                # 如果无法序列化，使用错误消息替代
                error_data = {
                    "error": "Message serialization failed",
                    "original_event_type": event_type,
                    "details": str(e)
                }
                json_data = json.dumps(error_data, ensure_ascii=False, default=str)
                message = f"event: error\ndata: {json_data}\n\n"
                message_bytes = message.encode('utf-8')
            
            for client in self.clients:
                try:
                    client.wfile.write(message_bytes)
                    client.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, AttributeError):
                    dead_clients.append(client)
                except Exception as e:
                    print(f"SSE 客户端写入错误: {e}")
                    dead_clients.append(client)
            
            # 清理死掉的客户端
            for client in dead_clients:
                self.remove_client(client)


class MemberStatusManager:
    """成员运行状态管理器，负责实时监控成员状态"""
    
    def __init__(self, registry_path: Path, agents_dir: Path):
        self.registry_path = registry_path
        self.agents_dir = agents_dir
        self.status_cache = {}
        self.lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self._callbacks = []

    def start(self):
        """启动状态监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """停止状态监控"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)

    def register_callback(self, callback):
        """注册状态变更回调"""
        self._callbacks.append(callback)

    def get_all_status(self) -> Dict[str, str]:
        """获取所有成员状态"""
        with self.lock:
            if not self.status_cache:
                self._update_status()
            return self.status_cache.copy()

    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            old_status = self.status_cache.copy()
            new_status = self._update_status()
            
            # 检查是否有状态变更
            if old_status != new_status:
                for callback in self._callbacks:
                    callback(new_status)
            
            # 每 10 秒检查一次（模拟实时性）
            time.sleep(10)

    def _update_status(self) -> Dict[str, str]:
        """更新状态逻辑
        
        使用 ZooRegistry.list_agents() 遍历成员，而非 registry.json。
        """
        try:
            print("正在更新成员状态...") # 添加日志
            from framework.core.mesh.zoo_registry import ZooRegistry
            reg = ZooRegistry()
            agent_ids = reg.list_agents()
            
            new_status = {}
            for member_id in agent_ids:
                print(f"检测成员 {member_id} 状态...") # 添加日志
                new_status[member_id] = self._detect_member_active_status(member_id)
            
            with self.lock:
                self.status_cache = new_status
            print(f"状态更新完成: {new_status}") # 添加日志
            return new_status
        except Exception as e:
            print(f"更新成员状态失败: {e}")
            return self.status_cache

    def _detect_member_active_status(self, member_id: str) -> str:
        """检测单个成员的实际活跃状态（检查 openclaw 进程）"""
        try:
            import subprocess
            # 检查是否有该成员的 openclaw 进程在运行
            result = subprocess.run(
                ["pgrep", "-f", f"openclaw.*{member_id}"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        p = subprocess.run(["ps", "-p", pid, "-o", "state="],
                                          capture_output=True, text=True, timeout=2)
                        state = p.stdout.strip()
                        if state and state not in ('Z', 'T'):
                            return "executing"
                    except:
                        continue
            return "idle"
        except Exception as e:
            print(f"检测成员 {member_id} 状态失败: {e}")
            return "unknown"



class TaskTrackerManager:
    """任务跟踪器管理器，确保并发读取的稳定性"""
    
    def __init__(self, tracker_path: Path):
        self.tracker_path = tracker_path
        self.lock = threading.RLock()
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 5  # 缓存有效期（秒）
    
    def _read_with_lock(self) -> dict:
        """使用文件锁安全读取 JSON 文件"""
        with self.lock:
            current_time = time.time()
            
            # 检查缓存是否有效
            if self._cache and (current_time - self._cache_time) < self._cache_ttl:
                return self._cache.copy()
            
            try:
                # 使用文件锁确保并发安全
                with open(self.tracker_path, 'r', encoding='utf-8') as f:
                    # 获取文件锁（非阻塞）
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # 更新缓存
                self._cache = data.copy()
                self._cache_time = current_time
                return data
                
            except FileNotFoundError:
                return {"error": "任务跟踪器文件不存在"}
            except json.JSONDecodeError as e:
                return {"error": f"JSON 解析错误: {str(e)}"}
            except Exception as e:
                return {"error": f"读取文件失败: {str(e)}"}
    
    def get_kanban_tasks(self) -> Dict[str, List]:
        """获取四象限看板任务数据"""
        data = self._read_with_lock()
        
        if "error" in data:
            return {status: [] for status in KANBAN_STATUS}
        
        # 初始化四象限看板
        kanban_tasks = {status: [] for status in KANBAN_STATUS}
        
        try:
            # 处理每个阶段的任务
            phases = data.get("phases", {})
            current_phase = data.get("current_phase", "P1")
            
            for phase_key, phase_data in phases.items():
                phase_status = phase_data.get("status", "pending")
                tasks = phase_data.get("tasks", [])
                
                for task in tasks:
                    task_status = task.get("status", "pending")
                    task_id = task.get("id", "")
                    
                    # 创建标准化的任务对象
                    kanban_task = {
                        "id": task_id,
                        "name": task.get("name", "未命名任务"),
                        "description": task.get("description", ""),
                        "severity": task.get("severity", "P3"),
                        "phase": phase_key,
                        "phase_name": phase_data.get("name", phase_key),
                        "created_at": task.get("created_at", ""),
                        "completed_at": task.get("completed_at", ""),
                        "notes": task.get("notes", ""),
                        "verification": task.get("verification", []),
                        "is_current_phase": phase_key == current_phase
                    }
                    
                    # 根据任务状态分配到对应 Pipeline 看板列
                    status_to_col = {
                        "pending": "request",
                        "in_progress": "develop",
                        "in_review": "review",
                        "completed": "done"
                    }
                    col_key = status_to_col.get(task_status, "request")
                    if col_key in kanban_tasks:
                        kanban_tasks[col_key].append(kanban_task)
                    else:
                        kanban_tasks["request"].append(kanban_task)
            
            # 按优先级排序
            for status, tasks in kanban_tasks.items():
                if status == "request":
                    # 需求池按严重程度排序: P0 > P1 > P2 > P3
                    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
                    kanban_tasks[status] = sorted(
                        tasks, 
                        key=lambda x: severity_order.get(x.get("severity", "P3"), 3)
                    )
                elif status == "done":
                    # 已完成按完成时间倒序
                    kanban_tasks[status] = sorted(
                        tasks,
                        key=lambda x: x.get("completed_at", ""),
                        reverse=True
                    )
                else:
                    # 其他状态按创建时间排序
                    kanban_tasks[status] = sorted(
                        tasks,
                        key=lambda x: x.get("created_at", "")
                    )
            
            return kanban_tasks
            
        except Exception as e:
            print(f"处理看板任务时出错: {e}")
            return {status: [] for status in KANBAN_STATUS}
    
    def get_task_stats(self) -> Dict:
        """获取任务统计信息"""
        data = self._read_with_lock()
        
        if "error" in data:
            return {"error": data["error"]}
        
        total_tasks = 0
        completed_tasks = 0
        in_progress_tasks = 0
        pending_tasks = 0
        
        phases = data.get("phases", {})
        for phase_data in phases.values():
            tasks = phase_data.get("tasks", [])
            total_tasks += len(tasks)
            
            for task in tasks:
                status = task.get("status", "pending")
                if status == "completed":
                    completed_tasks += 1
                elif status in ["in_progress", "in_review"]:
                    in_progress_tasks += 1
                else:
                    pending_tasks += 1
        
        current_phase = data.get("current_phase", "P1")
        current_phase_data = phases.get(current_phase, {})
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "pending_tasks": pending_tasks,
            "completion_rate": round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
            "current_phase": current_phase,
            "current_phase_name": current_phase_data.get("name", current_phase),
            "current_phase_status": current_phase_data.get("status", "pending"),
            "last_updated": data.get("last_updated", ""),
            "tdd_enabled": data.get("metadata", {}).get("tdd_enabled", False)
        }


class ZooDevCenterHandler(BaseHTTPRequestHandler):
    """Zoo Dev-Center HTTP 请求处理器"""
    
    # 类变量共享 SSE 管理器
    sse_manager = SSEManager()
    task_manager = TaskTrackerManager(TASK_TRACKER_PATH)
    status_manager = MemberStatusManager(REGISTRY_PATH, AGENTS_DIR)
    git_adapter = get_git_adapter()
    git_watcher = get_git_watcher()
    _issues_write_lock = threading.RLock()
    
    def __init__(self, *args, **kwargs):
        # 初始化 ZooRegistry 注册表（单例，只初始化一次）
        # ZooRegistry 构造时自动加载 YAML，不再需要 register_defaults()
        ZooRegistry()
        
        # 启动 Git 时间线监视器
        if not hasattr(self.__class__, '_git_watcher_started'):
            self.git_watcher.start()
            # 注册回调，当有新提交时广播 SSE 事件
            self.git_watcher.register_callback(self._on_git_update)
            self.__class__._git_watcher_started = True
        
        # 启动成员状态监视器
        if not hasattr(self.__class__, '_status_monitor_started'):
            self.status_manager.start()
            self.status_manager.register_callback(self._on_status_update)
            self.__class__._status_monitor_started = True
        
        # 启动 Pipeline 状态监视器
        if not hasattr(self.__class__, '_pipeline_monitor_started'):
            self.__class__._pipeline_last_snapshot = {}
            self.__class__._pipeline_monitor_started = True
            self._start_pipeline_monitor()
        
        super().__init__(*args, **kwargs)
    
    def _start_pipeline_monitor(self):
        """启动 Pipeline 状态监控线程"""
        def monitor():
            while True:
                try:
                    current = self._get_active_pipelines()
                    snapshot = self.__class__._pipeline_last_snapshot
                    # 检测变化
                    if current != snapshot:
                        # 广播变更
                        self.sse_manager.broadcast("pipeline_status", {
                            "type": "pipeline_update",
                            "data": current,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.__class__._pipeline_last_snapshot = current
                except Exception as e:
                    print(f"Pipeline 监控错误: {e}")
                time.sleep(5)  # 每5秒检查一次
        t = threading.Thread(target=monitor, daemon=True)
        t.start()
    
    def _on_git_update(self, commits):
        """Git 更新回调函数"""
        # 广播 Git 时间线更新事件
        timeline_data = [commit.to_dict() for commit in commits[:10]]  # 只发送最近10条
        self.sse_manager.broadcast("git_timeline", {
            "type": "timeline_update",
            "data": timeline_data,
            "timestamp": datetime.now().isoformat()
        })
        
    def _on_status_update(self, status_data):
        """成员状态更新回调函数"""
        self.sse_manager.broadcast("member_status", {
            "type": "status_update",
            "data": status_data,
            "timestamp": datetime.now().isoformat()
        })
    
    def do_GET(self):
        """处理 GET 请求"""
        try:
            from urllib.parse import urlparse
            parsed_path = urlparse(self.path).path
            
            if parsed_path == '/':
                self._serve_dev_center()
            elif parsed_path == '/api/members':
                self._send_json(self._get_member_data())
            elif parsed_path == '/api/member-status':
                self._send_json(self.status_manager.get_all_status())
            elif parsed_path == '/api/kanban':
                self._send_json(self._get_kanban_data())
            elif parsed_path == '/api/requirements':
                self._send_json(self._get_requirements())
            elif parsed_path == '/api/issues':
                self._handle_issues_get()
            elif parsed_path.startswith('/api/issues/'):
                self._handle_issues_get_single(parsed_path)
            elif parsed_path == '/api/pipeline-status':
                self._send_json(self._get_active_pipelines())
            elif parsed_path == '/api/task-stats':
                self._send_json(self.task_manager.get_task_stats())
            elif parsed_path == '/api/projects':
                self._send_json(self.git_adapter.get_all_projects())
            elif parsed_path == '/api/git-timeline':
                self._send_json(self._get_git_timeline())
            elif parsed_path == '/api/git-stats':
                self._send_json(self.git_adapter.get_commit_stats())
            elif self.path == '/api/system-info':
                self._send_json(self._get_system_info())
            elif self.path.startswith('/api/chat'):
                self._handle_chat_get()
            elif self.path == '/events':
                self._handle_sse()
            elif parsed_path.startswith('/avatar/'):
                self._serve_avatar()
            elif parsed_path.startswith('/static/'):
                self._serve_static_file()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"处理请求 {self.path} 时出错: {e}")
            self.send_error(500, str(e))

    def do_POST(self):
        """处理 POST 请求"""
        try:
            from urllib.parse import urlparse
            parsed_path = urlparse(self.path).path

            if parsed_path == '/api/chat':
                self._handle_chat_post()
            elif parsed_path == '/api/chat/send':
                self._handle_chat_send()
            elif parsed_path == '/api/requirements':
                self._handle_requirements_post()
            elif parsed_path == '/api/kanban/move':
                self._handle_kanban_move()
            elif parsed_path == '/api/issues':
                self._handle_issues_post()
            elif parsed_path == '/api/validate-requirement':
                self._handle_validate_requirement()
            elif parsed_path == '/api/audit-callback':
                self._handle_audit_callback()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"处理 POST 请求 {self.path} 时出错: {e}")
            self.send_error(500, str(e))

    def _handle_chat_get(self):
        """Proxy GET chat history to ZooMesh daemon"""
        try:
            r = requests.get(f"{ZOO_MESH_HTTP}/api/chat", timeout=5)
            self._send_json(r.json())
        except Exception:
            self._send_json([])

    def _handle_chat_post(self):
        """Proxy POST chat message to ZooMesh daemon"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            content = (data.get('content') or '').strip()
            if not content:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "content required"}).encode())
                return

            data['from'] = 'dashboard'
            data['content'] = content
            r = requests.post(f"{ZOO_MESH_HTTP}/api/chat", json=data, timeout=5)
            self._send_json(r.json())
        except Exception:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "ZooMesh unavailable"}).encode())

    def _handle_chat_send(self):
        """Send message directly to a specific agent via ZooMesh"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            target = (data.get('target') or '').strip()
            content = (data.get('content') or '').strip()
            if not target or not content:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "target and content required"}).encode())
                return

            # First send as chat message to ZooMesh (for logging + inbox routing)
            chat_payload = {
                'from': 'dashboard',
                'content': f'@{target} {content}'
            }
            try:
                r = requests.post(f"{ZOO_MESH_HTTP}/api/chat", json=chat_payload, timeout=5)
                result = r.json()
            except Exception:
                result = {"status": "logged_locally"}

            self._send_json({
                "status": "sent",
                "target": target,
                "content": content,
                "result": result
            })
        except Exception as e:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_validate_requirement(self):
        """POST /api/validate-requirement — 只校验不创建（供 deliver E2E 验证使用）"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"valid": False, "error": "invalid json"})
                return

            title = (data.get('title') or '').strip()
            if not title:
                self._send_json({"valid": False, "error": "title required"})
                return

            priority = (data.get('priority') or 'P3').upper()
            if priority not in VALID_PRIORITIES:
                self._send_json({"valid": False, "error": f"invalid priority: {priority}"})
                return

            self._send_json({
                "valid": True,
                "title": title,
                "assignee": data.get('assignee', ''),
                "priority": priority,
                "message": "请求格式验证通过"
            })
        except Exception as e:
            self._send_json({"valid": False, "error": str(e)})

    def _handle_requirements_post(self):
        """Create a new requirement and dispatch to Harness Pipeline via Panda"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            title = (data.get('title') or '').strip()
            if not title:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "title required"}).encode())
                return

            dry_run = data.get('dry_run', False)
            if dry_run:
                self._send_json({
                    "valid": True,
                    "dry_run": True,
                    "title": title,
                    "message": "验证通过（未实际创建）"
                })
                return

            import uuid
            req_id = str(uuid.uuid4())
            priority = (data.get('priority') or 'P3').upper()
            if priority not in VALID_PRIORITIES:
                priority = 'P3'
            
            dry_run = data.get('dry_run', False)
            if dry_run:
                self._send_json({
                    "valid": True,
                    "dry_run": True,
                    "title": title,
                    "assignee": data.get('assignee', ''),
                    "message": "验证通过（未实际创建）"
                })
                return

            requirement = {
                "id": req_id,
                "title": title,
                "description": (data.get('description') or '').strip(),
                "status": "request",
                "phase": "request",
                "priority": priority,
                "created_at": datetime.now().isoformat(),
                "pipeline_id": f"pl_{req_id[:8]}",
                "source": "dashboard_requirement"
            }

            # Save to requirements.json
            reqs_path = DATA_DIR / "requirements.json"
            existing = []
            if reqs_path.exists():
                try:
                    with open(reqs_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, Exception):
                    existing = []
            existing.append(requirement)
            with open(reqs_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            # Dispatch to Panda via ZooMesh inbox (trigger ZooPipeline)
            try:
                pipeline_payload = {
                    "type": "pipeline_request",
                    "task_id": requirement['pipeline_id'],
                    "requirement_id": req_id,
                    "title": title,
                    "description": requirement['description'],
                    "source": "dashboard",
                    "timestamp": requirement['created_at']
                }
                # Send to Panda's inbox via ZooMesh HTTP API
                req = requests.post(
                    f"{ZOO_MESH_HTTP}/api/chat",
                    json={
                        'from': 'dashboard',
                        'content': f"@panda 新Pipeline请求: {json.dumps(pipeline_payload, ensure_ascii=False)}"
                    },
                    timeout=5
                )
                requirement['panda_notified'] = req.ok
            except Exception as e:
                print(f"Panda 通知失败: {e}")
                requirement['panda_notified'] = False

            # 由 Pipeline 自动路由，不再发送额外通知
            self._send_json(requirement)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_kanban_move(self):
        """Move a requirement to a different status"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            req_id = (data.get('id') or '').strip()
            new_status = (data.get('status') or '').strip()
            if not req_id or new_status not in KANBAN_STATUS:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "valid id and status required"}).encode())
                return

            reqs_path = DATA_DIR / "requirements.json"
            if not reqs_path.exists():
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no requirements"}).encode())
                return

            with open(reqs_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)

            found = False
            for req in existing:
                if req['id'] == req_id:
                    req['status'] = new_status
                    req['updated_at'] = datetime.now().isoformat()
                    if new_status == 'done':
                        req['completed_at'] = datetime.now().isoformat()
                    found = True
                    break

            if not found:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "requirement not found"}).encode())
                return

            with open(reqs_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            self._send_json({"status": "moved", "id": req_id, "new_status": new_status})
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_PUT(self):
        """处理 PUT 请求"""
        try:
            from urllib.parse import urlparse
            parsed_path = urlparse(self.path).path

            if parsed_path.startswith('/api/issues/'):
                self._handle_issues_put(parsed_path)
            elif parsed_path.startswith('/api/requirements/'):
                self._handle_requirements_put(parsed_path)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"处理 PUT 请求 {self.path} 时出错: {e}")
            self.send_error(500, str(e))

    def _handle_requirements_put(self, parsed_path):
        """PUT /api/requirements/:id — 更新需求状态（含驳回）"""
        try:
            req_id = parsed_path.split('/api/requirements/')[-1]
            if not req_id:
                self.send_error(404)
                return

            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            reqs_path = DATA_DIR / "requirements.json"
            if not reqs_path.exists():
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no requirements"}).encode())
                return

            with open(reqs_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)

            found = False
            now = datetime.now().isoformat()
            for req in existing:
                if req.get('id') == req_id:
                    if 'status' in data:
                        new_status = data['status']
                        if new_status == 'rejected':
                            reject_reason = (data.get('reject_reason') or '').strip()
                            if not reject_reason:
                                self.send_response(400)
                                self.send_header('Content-Type', 'application/json')
                                self.end_headers()
                                self.wfile.write(json.dumps({"error": "驳回原因不能为空"}).encode())
                                return
                            # 驳回 → 进入 audit 阶段，由毒刺审计驳回原因
                            req['previous_status'] = req.get('status', 'done')
                            req['status'] = 'audit'
                            req['reject_reason'] = reject_reason
                            req['rejected_by'] = 'dashboard_user'
                            req['rejected_at'] = now
                            req['audit_status'] = 'pending'
                            req['audit_comment'] = ''
                            req['audit_agent'] = 'duci'
                            # 通知 Duci 审计（用 pipeline_id 而非 uuid）
                            pid = req.get('pipeline_id', '') or req.get('id', '')
                            self._notify_duci_audit('requirement', pid, req.get('title', ''), reject_reason)
                        else:
                            req['status'] = new_status
                            if new_status == 'done':
                                req['completed_at'] = now
                    if 'title' in data:
                        req['title'] = data['title']
                    if 'description' in data:
                        req['description'] = data['description']
                    if 'priority' in data:
                        p = data['priority'].upper()
                        req['priority'] = p if p in VALID_PRIORITIES else 'P3'
                    req['updated_at'] = now
                    found = True
                    break

            if not found:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "requirement not found"}).encode())
                return

            with open(reqs_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            self._send_json({"status": "updated", "id": req_id})
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _dispatch_pipeline(self, target: dict, target_type: str, source: str) -> dict:
        """为 issue/requirement 创建 Pipeline 并推送到 Panda。
        
        不负责持久化，调用方负责将返回的 pipeline_id/pipeline_status 写入数据。
        
        Args:
            target: issue 或 requirement 字典
            target_type: 'issue' 或 'requirement'
            source: payload 中 source 的值（如 'issue_reject', 'issue'）
            
        Returns:
            dict: {"pipeline_id": "...", "pipeline_status": "..."}
        """
        import uuid
        now = datetime.now().isoformat()
        
        # 重复防护：已有 reject_pipeline_id 时不重复创建
        if target.get('reject_pipeline_id'):
            return {"pipeline_id": target['reject_pipeline_id'], "pipeline_status": "skip_duplicate"}
        
        pipeline_id = f"pl_{uuid.uuid4().hex[:8]}"
        reject_reason = target.get('reject_reason', '')
        title_prefix = f"[驳回重开] " if target.get('audit_status') == 'approved' or source in ('issue_reject', 'requirement_reject') else ""
        
        pipeline_payload = {
            "type": "pipeline_request",
            "task_id": pipeline_id,
            "requirement_id": target['id'],
            "title": f"{title_prefix}{target.get('title', '')}",
            "description": f"驳回原因: {reject_reason}\n\n{target.get('description', '')}" if reject_reason else target.get('description', ''),
            "source": source,
            "timestamp": now,
        }
        
        try:
            resp = requests.post(
                f"{ZOO_MESH_HTTP}/api/chat",
                json={
                    'from': 'dashboard',
                    'content': f"@panda 新Pipeline请求: {json.dumps(pipeline_payload, ensure_ascii=False)}"
                },
                timeout=5
            )
            if resp.status_code == 200:
                return {"pipeline_id": pipeline_id, "pipeline_status": "pushed"}
            else:
                print(f"pipeline push 返回非200: {resp.status_code}")
                return {"pipeline_id": pipeline_id, "pipeline_status": "push_failed"}
        except requests.exceptions.Timeout:
            print(f"pipeline push 超时（5s）")
            return {"pipeline_id": pipeline_id, "pipeline_status": "push_failed"}
        except Exception as e:
            print(f"pipeline push 异常: {e}")
            return {"pipeline_id": pipeline_id, "pipeline_status": "push_failed"}

    def _handle_audit_callback(self):
        """POST /api/audit-callback — 毒刺审计回调（仅接受 127.0.0.1）"""
        try:
            # IP 鉴权：仅允许本地回环地址
            client_ip = self.client_address[0]
            if client_ip not in ('127.0.0.1', '::1', 'localhost'):
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "回调仅支持本地请求"}).encode())
                return

            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            target_id = (data.get('target_id') or '').strip()
            target_type = (data.get('target_type') or '').strip()
            audit_result = (data.get('audit_result') or '').strip()
            audit_comment = (data.get('audit_comment') or '').strip()

            if not target_id or not target_type or audit_result not in ('audit_approved', 'audit_declined'):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "缺少必要参数或 audit_result 无效"}).encode())
                return

            now = datetime.now().isoformat()

            if target_type == 'issue':
                issues = self._load_issues()
                found = False
                for issue in issues:
                    if issue.get('id') == target_id:
                        if issue.get('audit_status') != 'pending':
                            self.send_response(409)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "审计状态非 pending，不可重复处理"}).encode())
                            return
                        issue['audit_comment'] = audit_comment
                        issue['audit_updated_at'] = now
                        if audit_result == 'audit_approved':
                            issue['status'] = 'in_progress'
                            issue['audit_status'] = 'approved'
                            # 不再自动创建 Pipeline，避免测试残留被批量复活
                            # Pipeline 的驳回重走由 daemon 的 _handle_phase_complete 处理
                        else:  # audit_declined
                            issue['status'] = issue.get('previous_status', 'resolved')
                            issue['audit_status'] = 'declined'
                        found = True
                        break
                if not found:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "target_id 不存在"}).encode())
                    return
                self._save_issues(issues)

            elif target_type == 'requirement':
                reqs_path = DATA_DIR / "requirements.json"
                if not reqs_path.exists():
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "no requirements"}).encode())
                    return
                with open(reqs_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                found = False
                for req in existing:
                    if req.get('id') == target_id:
                        if req.get('audit_status') != 'pending':
                            self.send_response(409)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "审计状态非 pending"}).encode())
                            return
                        req['audit_comment'] = audit_comment
                        req['audit_updated_at'] = now
                        if audit_result == 'audit_approved':
                            req['status'] = 'develop_code'
                            req['audit_status'] = 'approved'
                            # 不再自动创建 Pipeline，避免测试残留被批量复活
                            # Pipeline 的驳回重走由 daemon 的 _handle_phase_complete 处理
                        else:
                            req['status'] = req.get('previous_status', 'done')
                            req['audit_status'] = 'declined'
                        found = True
                        break
                if not found:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "target_id 不存在"}).encode())
                    return
                with open(reqs_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "target_type 必须是 issue 或 requirement"}).encode())
                return

            # 通过 SSE 推送审计结果
            self.__class__.sse_manager.broadcast("audit_result", {
                "target_id": target_id,
                "target_type": target_type,
                "audit_result": audit_result,
                "new_status": "in_progress" if (audit_result == 'audit_approved' and target_type == 'issue') else ("develop_code" if audit_result == 'audit_approved' else "restored"),
            })

            self._send_json({"status": "ok", "message": "审计结果已处理"})
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _notify_duci_audit(self, target_type: str, target_id: str, title: str, reason: str):
        """"通知 Duci 进行驳回审计（通过 ZooNotify bridge sessions_send）"""
        try:
            import json as _json
            import urllib.request
            # 改为与其他阶段一致的格式，明确 PASS/REJECT 标准
            msg = (
                f"[Pipeline] Phase: audit\n"
                f"task_id: {target_id}\n"
                f"title: {title}\n"
                f"description: 驳回原因：{reason}\n"
                f"指令: 请执行 audit 阶段，判定驳回原因是否成立\n"
                f"- 驳回原因属实，需要修改 → reject（退回 develop_code）\n"
                f"- 驳回原因不成立，无需修改 → pass（直接放行）\n"
                f"完成后：1) git commit   2) 执行上报命令\n"
                f"./zoo-phase-complete {target_id} audit <pass|reject> <commit_id> duci\n"
            )
            payload = _json.dumps({
                "agent": "duci",
                "message": msg
            }).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:18794/api/sessions-send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"Duci 审计通知已发送（sessions_send）: {target_type}/{target_id}")
        except Exception as e:
            print(f"Duci 审计通知发送失败（降级）: {e}")

    def do_DELETE(self):
        """处理 DELETE 请求"""
        try:
            from urllib.parse import urlparse
            parsed_path = urlparse(self.path).path

            if parsed_path.startswith('/api/issues/'):
                self._handle_issues_delete(parsed_path)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"处理 DELETE 请求 {self.path} 时出错: {e}")
            self.send_error(500, str(e))

    # ===== Issues CRUD Helpers =====

    def _get_issues_path(self):
        """获取 issues 数据文件路径"""
        return DATA_DIR / "issues.json"

    def _load_issues(self) -> List[Dict]:
        """加载所有 issues"""
        path = self._get_issues_path()
        if not path.exists():
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []

    def _save_issues(self, issues: List[Dict]):
        """保存 issues 到文件（带并发写锁）"""
        with self.__class__._issues_write_lock:
            path = self._get_issues_path()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)

    def _handle_issues_get(self):
        """GET /api/issues — 返回所有问题（支持过滤）"""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            issues = self._load_issues()

            status_filter = (params.get('status') or [None])[0]
            priority_filter = (params.get('priority') or [None])[0]
            search_query = (params.get('search') or [None])[0]

            if status_filter and status_filter != 'all':
                issues = [i for i in issues if i.get('status') == status_filter]
            if priority_filter and priority_filter != 'all':
                issues = [i for i in issues if i.get('priority') == priority_filter]
            if search_query:
                q = search_query.lower()
                issues = [i for i in issues if q in (i.get('title', '') + i.get('description', '')).lower()]

            # 排序已由前端统一处理（分组+优先级/时间排序），后端不排序
            self._send_json(issues)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_issues_get_single(self, parsed_path):
        """GET /api/issues/:id"""
        try:
            issue_id = parsed_path.split('/api/issues/')[-1]
            if not issue_id:
                self.send_error(404)
                return
            issues = self._load_issues()
            for issue in issues:
                if issue.get('id') == issue_id:
                    self._send_json(issue)
                    return
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "issue not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_issues_post(self):
        """POST /api/issues — 创建新问题"""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            title = (data.get('title') or '').strip()
            if not title:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "title required"}).encode())
                return

            dry_run = data.get('dry_run', False)
            if dry_run:
                self._send_json({
                    "valid": True,
                    "dry_run": True,
                    "title": title,
                    "message": "验证通过（未实际创建）"
                })
                return

            import uuid
            now = datetime.now().isoformat()
            issue_priority = (data.get('priority') or 'P3').upper()
            if issue_priority not in VALID_PRIORITIES:
                issue_priority = 'P3'
            # 由 Pipeline 自动路由，不在新建时写入
            issue = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": (data.get('description') or '').strip(),
                "priority": issue_priority,
                "status": "open",
                "created_at": now,
                "updated_at": now,
                "resolved_at": None,
                "source": "dashboard"
            }

            issues = self._load_issues()
            issues.append(issue)
            self._save_issues(issues)

            # 推送到 ZooMesh 触发 Pipeline
            dispatch = self._dispatch_pipeline(issue, 'issue', 'issue')
            issue['pipeline_id'] = dispatch['pipeline_id']
            issue['pipeline_status'] = dispatch['pipeline_status']
            # 二次保存 pipeline 字段，失败降级（不影响 issue 已创建的事实）
            try:
                self._save_issues(issues)
            except Exception as e:
                print(f"保存 pipeline 字段失败（降级）: {e}")
                issue.pop('pipeline_id', None)
                issue.pop('pipeline_status', None)

            self._send_json(issue)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_issues_put(self, parsed_path):
        """PUT /api/issues/:id — 更新问题状态/字段"""
        try:
            issue_id = parsed_path.split('/api/issues/')[-1]
            if not issue_id:
                self.send_error(404)
                return

            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid json"}).encode())
                return

            issues = self._load_issues()
            found = False
            for issue in issues:
                if issue.get('id') == issue_id:
                    now = datetime.now().isoformat()
                    if 'status' in data:
                        new_status = data['status']
                        if new_status == 'rejected':
                            reject_reason = (data.get('reject_reason') or '').strip()
                            if not reject_reason:
                                self.send_response(400)
                                self.send_header('Content-Type', 'application/json')
                                self.end_headers()
                                self.wfile.write(json.dumps({"error": "驳回原因不能为空"}).encode())
                                return
                            # 驳回 → 进入 audit 阶段，由毒刺审计驳回原因
                            issue['previous_status'] = issue.get('status', 'resolved')
                            issue['status'] = 'audit'
                            issue['reject_reason'] = reject_reason
                            issue['rejected_by'] = 'dashboard_user'
                            issue['rejected_at'] = now
                            issue['audit_status'] = 'pending'
                            issue['audit_comment'] = ''
                            issue['audit_agent'] = 'duci'
                            # 通知 Duci 进行审计（用 pipeline_id 而非 uuid）
                            pid = issue.get('pipeline_id', '') or issue.get('id', '')
                            self._notify_duci_audit('issue', pid, issue.get('title', ''), reject_reason)
                            # 同步 requirement 状态到 audit
                            if issue.get('pipeline_id'):
                                reqs = self._get_requirements()
                                for r in reqs:
                                    if r.get('pipeline_id') == issue['pipeline_id']:
                                        r['status'] = 'audit'
                                        r['phase'] = 'audit'
                                        r['updated_at'] = now
                                        break
                                reqs_path = DATA_DIR / "requirements.json"
                                with open(reqs_path, 'w') as f:
                                    json.dump(reqs, f, indent=2, ensure_ascii=False)
                        else:
                            issue['status'] = new_status
                            if new_status == 'resolved':
                                issue['resolved_at'] = now
                    if 'title' in data:
                        issue['title'] = data['title']
                    if 'description' in data:
                        issue['description'] = data['description']
                    if 'priority' in data:
                        p = data['priority'].upper()
                        issue['priority'] = p if p in VALID_PRIORITIES else 'P3'
                    issue['updated_at'] = now
                    found = True
                    break

            if not found:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "issue not found"}).encode())
                return

            self._save_issues(issues)
            self._send_json({"status": "updated", "id": issue_id})
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_issues_delete(self, parsed_path):
        """DELETE /api/issues/:id — 删除问题"""
        try:
            issue_id = parsed_path.split('/api/issues/')[-1]
            if not issue_id:
                self.send_error(404)
                return

            issues = self._load_issues()
            new_issues = [i for i in issues if i.get('id') != issue_id]

            if len(new_issues) == len(issues):
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "issue not found"}).encode())
                return

            self._save_issues(new_issues)
            self._send_json({"status": "deleted", "id": issue_id})
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _serve_dev_center(self):
        """服务研发中心主页面"""
        dev_center_path = TEMPLATES_DIR / 'dev_center.html'
        if not dev_center_path.exists():
            dev_center_path = TEMPLATES_DIR / 'index.html'

        content = open(dev_center_path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)
    
    def _serve_avatar(self):
        """服务成员头像（路径遍历防护已启用）"""
        from urllib.parse import urlparse
        member_id = urlparse(self.path).path.split('/')[-1]
        
        # 安全检查：禁止路径遍历
        if '..' in member_id or member_id.startswith('/'):
            self.send_error(403)
            return
        
        # 优先从运行数据 agents/ 目录查找
        avatar_path = PROJECT_AGENTS_DIR / member_id / "avatar.png"
        try:
            if avatar_path.exists() and avatar_path.resolve().relative_to(PROJECT_AGENTS_DIR.resolve()):
                self._serve_file(avatar_path, 'image/png')
                return
        except ValueError:
            pass  # resolve 后不在 PROJECT_AGENTS_DIR 下，拒绝
        
        # fallback：旧项目 agents/ 目录（已迁移的文件可能仍在旧位置）
        legacy_path = PROJECT_ROOT / "agents" / member_id / "avatar.png"
        try:
            if legacy_path.exists() and legacy_path.resolve().relative_to((PROJECT_ROOT / "agents").resolve()):
                self._serve_file(legacy_path, 'image/png')
                return
        except ValueError:
            pass
        
        self.send_error(404)
    
    def _serve_static_file(self):
        """服务静态文件（路径遍历防护已启用）"""
        from urllib.parse import urlparse
        raw_suffix = urlparse(self.path).path.split('/static/')[-1]
        # 安全检查：禁止路径遍历
        if '..' in raw_suffix or raw_suffix.startswith('/'):
            self.send_error(403)
            return
        file_path = STATIC_DIR / raw_suffix
        try:
            resolved = file_path.resolve()
            resolved.relative_to(STATIC_DIR.resolve())
        except (ValueError, RuntimeError):
            self.send_error(403)
            return
        if file_path.exists() and file_path.is_file():
            # 根据文件扩展名确定 Content-Type
            if file_path.suffix == '.css':
                content_type = 'text/css'
            elif file_path.suffix == '.js':
                content_type = 'application/javascript'
            elif file_path.suffix in ['.png', '.jpg', '.jpeg', '.gif']:
                content_type = f'image/{file_path.suffix[1:]}'
            else:
                content_type = 'text/plain'
            
            self._serve_file(file_path, content_type)
        else:
            self.send_error(404)
    
    def _serve_file(self, path, content_type):
        """服务文件内容"""
        try:
            with open(path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', f'{content_type}; charset=utf-8' if 'text' in content_type else content_type)
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_error(404)
    
    def _send_json(self, data):
        """发送 JSON 响应"""
        content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)
    
    def _get_member_data(self):
        """获取成员数据
        
        从 ZooRegistry.get_full_info() 读取全部成员展示信息。
        ZooRegistry 数据源：zoo_members.yaml（单一权威源）。
        """
        try:
            registry = ZooRegistry()
            agent_ids = registry.list_agents()
            
            members = []
            for member_id in agent_ids:
                full = registry.get_full_info(member_id) or {}
                
                # 状态优先级：进程监控 > ZooRegistry > 默认离线
                live_status = self.status_manager.status_cache.get(member_id)
                zoo_status = registry.get_status(member_id) or "unknown"
                status = live_status if live_status else zoo_status
                
                # 模型展示（主 Agent 显示主用模型）
                model_display = registry.get_model_display(member_id) or "未知"
                
                meta = full.get("metadata", {}) or {}
                is_main = meta.get("is_main_agent", False) if isinstance(meta, dict) else False
                
                # 跳过非活跃成员（已退出/retired）
                member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
                if member_status != "active":
                    continue
                
                avatar_exists = (STATIC_DIR / "avatars" / f"{member_id}.png").exists()
                
                display_name = full.get("display_name", "")
                species_name = full.get("species", "未知")
                
                members.append({
                    "id": member_id,
                    "name": f"{full.get('name', member_id)} {full.get('code_name', '')}".strip(),
                    "code_name": full.get("code_name", member_id.capitalize()),
                    "role_display": display_name,
                    "species": species_name,
                    "avatar": f"/static/avatars/{member_id}.png" if avatar_exists else None,
                    "avatar_emoji": full.get("emoji", "🐾"),
                    "status": status,
                    "model": model_display,
                    "description": f"{display_name} · {species_name}",
                    "is_main_agent": is_main,
                })
            return members
        except Exception as e:
            print(f"获取成员数据失败 (ZooRegistry): {e}")
            # Fallback: 直接从 zoo_members.yaml 读取
            try:
                import yaml as _yaml
                yaml_path = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
                with open(yaml_path, "r", encoding="utf-8") as f:
                    yaml_data = _yaml.safe_load(f)
                members_data = yaml_data.get("members", {})
                fallback_members = []
                for member_id, info in members_data.items():
                    meta = info.get("metadata", {}) or {}
                    is_main = meta.get("is_main_agent", False) if isinstance(meta, dict) else False
                    # fallback 路径同样过滤非活跃成员
                    member_status = meta.get("status", "active") if isinstance(meta, dict) else "active"
                    if member_status != "active":
                        continue
                    avatar_exists = (STATIC_DIR / "avatars" / f"{member_id}.png").exists()
                    display_name = info.get("display_name", "")
                    species_name = info.get("species", "未知")
                    fallback_members.append({
                        "id": member_id,
                        "name": f"{info.get('name', member_id)} {info.get('code_name', '')}".strip(),
                        "code_name": info.get("code_name", member_id.capitalize()),
                        "role_display": display_name,
                        "species": species_name,
                        "avatar": f"/static/avatars/{member_id}.png" if avatar_exists else None,
                        "avatar_emoji": info.get("emoji", "🐾"),
                        "status": "unknown",
                        "model": info.get("model", "未知"),
                        "description": f"{display_name} · {species_name}",
                        "is_main_agent": is_main,
                    })
                return fallback_members
            except Exception as e2:
                print(f"成员数据 fallback 也失败: {e2}")
                return []
    
    def _get_member_species(self, member_id):
        """获取成员种族信息（从 zoo_members.yaml 读取）"""
        try:
            import yaml as _yaml
            yaml_path = PROJECT_ROOT / "framework" / "data" / "zoo_members.yaml"
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = _yaml.safe_load(f)
            members = data.get("members", {})
            info = members.get(member_id, {})
            species = info.get("species", "未知")
            return {"species": species}
        except Exception as e:
            print(f"读取成员种族信息失败: {e}")
            return {"species": "未知"}
    
    def _get_requirements(self):
        """获取需求列表"""
        reqs_path = DATA_DIR / "requirements.json"
        if not reqs_path.exists():
            return []
        try:
            with open(reqs_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []

    def _get_active_pipelines(self) -> dict:
        """从 requirements.json 读取活跃 pipeline（不再依赖 state 文件）"""
        pipelines = {}
        reqs = self._get_requirements()
        try:
            for r in reqs:
                pid = r.get("pipeline_id", "")
                if not pid:
                    continue
                status = r.get("status", "unknown")
                if status in ("cancelled", "done"):
                    continue
                pipelines[pid] = {
                    "state": status,
                    "updated_at": r.get("updated_at", ""),
                    "priority": r.get("priority", "P3"),
                    "title": r.get("title", "")
                }
        except Exception:
            pass
        return pipelines

    def _get_kanban_data(self):
        """获取看板数据，对接完整 Harness Pipeline"""
        kanban_tasks = {status: [] for status in KANBAN_STATUS}
        
        # 1. （已弃用）task_tracker.json — 历史快照数据，2026-05-16起看板完全由 requirement + pipeline 驱动
        #    详见 Duci 审计: alpha_design_p2_kanban_sync.md
        
        # 2. 从 requirements.json 加载需求
        requirements = self._get_requirements()
        # 阶段 → 执行人映射（与子流程daemon PHASE_DEFAULT_AGENT 保持一致）
        PHASE_EXECUTOR = {
            "design": "alpha",
            "design": "alpha", "ui_design": "alpha", "review": "duci",
            "develop_wt": "alpha", "review_test": "duci",
            "develop_code": "alpha", "test": "duci",
            "audit": "duci", "deliver": "alpha",
        }

        seen_pipeline_ids = set()

        for req in requirements:
            # 确定需求在看板中的列：优先从 Pipeline 状态读取
            pipeline_id = req.get('pipeline_id', '')
            req_status = req.get('status', 'request')
            column_key = "request"  # 默认需求池
            pipeline_phase = req_status  # 当前管线的内部阶段
            current_executor = PHASE_EXECUTOR.get(req_status, '')
            
            if pipeline_id:
                active_pipelines = self._get_active_pipelines()
                if pipeline_id in active_pipelines:
                    pl_state = active_pipelines[pipeline_id].get("state", "request")
                    column_key = PIPELINE_PHASE_TO_COLUMN.get(pl_state, "request")
                    pipeline_phase = pl_state
                    current_executor = PHASE_EXECUTOR.get(pl_state, '')
                elif req_status != 'request':
                    # 使用 PIPELINE_PHASE_TO_COLUMN 单源映射（避免双维护漂移）
                    column_key = PIPELINE_PHASE_TO_COLUMN.get(req_status, column_key)
            elif req_status != 'request':
                    # 使用 PIPELINE_PHASE_TO_COLUMN 单源映射（避免双维护漂移）
                    column_key = PIPELINE_PHASE_TO_COLUMN.get(req_status, column_key)
            
            if column_key not in kanban_tasks:
                column_key = "request"
            
            # 记录已处理的 pipeline_id 用于去重
            if pipeline_id:
                seen_pipeline_ids.add(pipeline_id)
            
            # 获取内部阶段中文显示名
            pipeline_status_cn = PHASE_TO_CHINESE.get(pipeline_phase, pipeline_phase)
            
            kanban_tasks[column_key].append({
                'id': req.get('id', ''),
                'name': req.get('title', '未命名需求'),
                'description': req.get('description', ''),
                'priority': req.get('priority', 'P3'),
                'pipeline_id': pipeline_id,
                'phase': column_key,
                'phase_name': KANBAN_STATUS.get(column_key, column_key),
                'pipeline_status': pipeline_status_cn,
                'pipeline_status_raw': pipeline_phase,
                'current_executor': current_executor,
                'created_at': req.get('created_at', ''),
                'completed_at': req.get('completed_at', ''),
                'is_from_requirements': True
            })
        
        # 3. 从 Pipeline 状态文件读取活跃管道（补全无对应 requirement 的管道）
        active_pipelines = self._get_active_pipelines()
        for task_id, pl_info in active_pipelines.items():
            # 使用 seen_pipeline_ids 集合去重（比逐列搜索更高效）
            if task_id in seen_pipeline_ids:
                continue
            
            pl_state = pl_info.get("state", "request")
            column_key = PIPELINE_PHASE_TO_COLUMN.get(pl_state, "request")
            if column_key not in kanban_tasks:
                column_key = "request"
            
            pipeline_status_cn = PHASE_TO_CHINESE.get(pl_state, pl_state)
            
            kanban_tasks[column_key].append({
                'id': task_id,
                'name': f'管道任务 {task_id[:8]}',
                'description': f'Pipeline 状态: {pl_state}',
                'priority': 'P0' if pl_state in ('cancelled', 'escalated', 'timed_out') else 'P2',
                'pipeline_id': task_id,
                'phase': column_key,
                'phase_name': KANBAN_STATUS.get(column_key, column_key),
                'pipeline_status': pipeline_status_cn,
                'pipeline_status_raw': pl_state,
                'created_at': pl_info.get('updated_at', ''),
                'is_from_pipeline': True
            })
        
        # 排序：按创建时间从新到旧，同时间按优先级
        for col_key in kanban_tasks:
            kanban_tasks[col_key].sort(
                key=lambda x: (x.get('created_at', '') or ''),
                reverse=True
            )
        
        return {
            "statuses": KANBAN_STATUS,
            "columns": {
                status: {
                    "title": KANBAN_STATUS[status],
                    "tasks": tasks
                }
                for status, tasks in kanban_tasks.items()
            },
            "stats": self.task_manager.get_task_stats(),
            "requirements_count": len(requirements),
            "pipeline_count": len(active_pipelines),
            "last_updated": datetime.now().isoformat()
        }
    
    def _get_git_timeline(self):
        """获取 Git 时间线数据（支持项目筛选）"""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        project = (params.get('project') or ['feida_zoo'])[0]
        
        commits = self.git_adapter.get_recent_commits_for_project(project, limit=20)
        stats = self.git_adapter.get_commit_stats_for_project(project)
        return {
            "commits": [commit.to_dict() for commit in commits],
            "stats": stats,
            "projects": self.git_adapter.get_all_projects(),
            "current_project": project,
            "last_updated": datetime.now().isoformat()
        }
    
    def _get_system_info(self):
        """获取系统信息"""
        return {
            "name": "Zoo Dev-Center v1.0",
            "version": "1.0.0",
            "status": "running",
            "port": PORT,
            "start_time": datetime.now().isoformat(),
            "features": ["SSE", "Kanban", "Git Integration", "Real-time Updates"]
        }
    
    def _handle_sse(self):
        """处理 Server-Sent Events 连接"""
        # 设置 SSE 响应头
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # 将客户端添加到 SSE 管理器
        self.sse_manager.add_client(self)
        
        # 发送初始连接事件
        try:
            self.wfile.write(f"event: connected\ndata: {{\"timestamp\": \"{datetime.now().isoformat()}\"}}\n\n".encode('utf-8'))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端已经断开连接，静默处理
            pass
        except Exception as e:
            print(f"发送SSE初始连接事件失败: {e}")
            pass
        
        # 保持连接打开（客户端断开时会自动清理）
        try:
            # 发送心跳包保持连接
            while True:
                time.sleep(30)
                self.wfile.write(f"event: heartbeat\ndata: {{\"timestamp\": \"{datetime.now().isoformat()}\"}}\n\n".encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端断开连接
            pass
        finally:
            # 从 SSE 管理器移除客户端
            self.sse_manager.remove_client(self)


def run_server():
    """运行服务器"""
    server = ThreadingHTTPServer(('0.0.0.0', PORT), ZooDevCenterHandler)
    print(f"🚀 Zoo Dev-Center v1.0 启动成功!")
    print(f"📊 看板地址: http://localhost:{PORT}")
    print(f"📈 API 端点:")
    print(f"  - 看板数据: http://localhost:{PORT}/api/kanban")
    print(f"  - 任务统计: http://localhost:{PORT}/api/task-stats")
    print(f"  - Git时间线: http://localhost:{PORT}/api/git-timeline")
    print(f"  - 实时事件: http://localhost:{PORT}/events")
    print(f"🐜 由织巢蚁精心构建 | 飝龘动物园生态")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 服务器正在关闭...")
        ZooDevCenterHandler.git_watcher.stop()
        ZooDevCenterHandler.status_manager.stop()
        server.server_close()
        print("✅ 服务器已安全关闭")


if __name__ == '__main__':
    run_server()