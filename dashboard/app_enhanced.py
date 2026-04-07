#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Dev-Center - 飝龘动物园研发中心 v1.0
增强版后端，包含 SSE 机制和四象限看板 API
"""

import json
import os
import time
import threading
import fcntl
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Set
import queue

# 导入 Git 适配器
from git_adapter import get_git_adapter, get_git_watcher

# 配置
PORT = 18792  # 使用新端口避免冲突
PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")
PANDA_ROOT = Path("/home/afei/workspace/panda")
REGISTRY_PATH = PROJECT_ROOT / "framework" / "data" / "registry.json"
TASK_TRACKER_PATH = PROJECT_ROOT / "framework" / "shared" / "task_tracker.json"
AGENTS_DIR = PANDA_ROOT / "agents"
TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
DATA_DIR = PROJECT_ROOT / "dashboard" / "data"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 四象限看板状态定义
KANBAN_STATUS = {
    "backlog": "📥 需求池",
    "in_progress": "🚧 进行中", 
    "in_review": "🔍 待验收",
    "done": "✅ 已完成"
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
            
            for client in self.clients:
                try:
                    message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    client.wfile.write(message.encode('utf-8'))
                    client.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    dead_clients.append(client)
                except Exception as e:
                    print(f"SSE 广播错误: {e}")
                    dead_clients.append(client)
            
            # 清理死掉的客户端
            for client in dead_clients:
                self.remove_client(client)


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
                        "assignee": task.get("assignee", ""),
                        "severity": task.get("severity", "P3"),
                        "phase": phase_key,
                        "phase_name": phase_data.get("name", phase_key),
                        "created_at": task.get("created_at", ""),
                        "completed_at": task.get("completed_at", ""),
                        "notes": task.get("notes", ""),
                        "verification": task.get("verification", []),
                        "is_current_phase": phase_key == current_phase
                    }
                    
                    # 根据任务状态分配到对应看板列
                    if task_status == "completed":
                        kanban_tasks["done"].append(kanban_task)
                    elif task_status == "in_review":
                        kanban_tasks["in_review"].append(kanban_task)
                    elif task_status == "in_progress":
                        kanban_tasks["in_progress"].append(kanban_task)
                    else:  # pending 或其他状态
                        kanban_tasks["backlog"].append(kanban_task)
            
            # 按优先级排序（Backlog 按严重程度排序）
            for status, tasks in kanban_tasks.items():
                if status == "backlog":
                    # Backlog 按严重程度排序: P0 > P1 > P2 > P3
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
    git_adapter = get_git_adapter()
    git_watcher = get_git_watcher()
    
    def __init__(self, *args, **kwargs):
        # 启动 Git 时间线监视器
        if not hasattr(self.__class__, '_git_watcher_started'):
            self.git_watcher.start()
            # 注册回调，当有新提交时广播 SSE 事件
            self.git_watcher.register_callback(self._on_git_update)
            self.__class__._git_watcher_started = True
        
        super().__init__(*args, **kwargs)
    
    def _on_git_update(self, commits):
        """Git 更新回调函数"""
        # 广播 Git 时间线更新事件
        timeline_data = [commit.to_dict() for commit in commits[:10]]  # 只发送最近10条
        self.sse_manager.broadcast("git_timeline", {
            "type": "timeline_update",
            "data": timeline_data,
            "timestamp": datetime.now().isoformat()
        })
    
    def do_GET(self):
        """处理 GET 请求"""
        try:
            if self.path == '/':
                self._serve_dev_center()
            elif self.path == '/api/members':
                self._send_json(self._get_member_data())
            elif self.path == '/api/kanban':
                self._send_json(self._get_kanban_data())
            elif self.path == '/api/task-stats':
                self._send_json(self.task_manager.get_task_stats())
            elif self.path == '/api/git-timeline':
                self._send_json(self._get_git_timeline())
            elif self.path == '/api/git-stats':
                self._send_json(self.git_adapter.get_commit_stats())
            elif self.path == '/api/system-info':
                self._send_json(self._get_system_info())
            elif self.path == '/events':
                self._handle_sse()
            elif self.path.startswith('/avatar/'):
                self._serve_avatar()
            elif self.path.startswith('/static/'):
                self._serve_static_file()
            else:
                self.send_error(404)
        except Exception as e:
            print(f"处理请求 {self.path} 时出错: {e}")
            self.send_error(500, str(e))
    
    def _serve_dev_center(self):
        """服务研发中心主页面"""
        dev_center_path = TEMPLATES_DIR / 'dev_center.html'
        if not dev_center_path.exists():
            # 如果 dev_center.html 不存在，回退到 index.html
            dev_center_path = TEMPLATES_DIR / 'index.html'
        
        self._serve_file(dev_center_path, 'text/html')
    
    def _serve_avatar(self):
        """服务成员头像"""
        member_id = self.path.split('/')[-1]
        avatar_path = AGENTS_DIR / member_id / "avatar.png"
        if avatar_path.exists():
            self._serve_file(avatar_path, 'image/png')
        else:
            self.send_error(404)
    
    def _serve_static_file(self):
        """服务静态文件"""
        file_path = STATIC_DIR / self.path.split('/static/')[-1]
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
        """获取成员数据"""
        try:
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                registry = json.load(f)
            
            members = []
            for member_id, data in registry.get("members", {}).items():
                species_info = self._get_member_species(member_id)
                avatar_exists = (AGENTS_DIR / member_id / "avatar.png").exists()
                
                members.append({
                    "id": member_id,
                    "name": data.get("name", member_id),
                    "code_name": data.get("code_name", member_id),
                    "role_display": data.get("metadata", {}).get("title", data.get("role", "未知")),
                    "species": species_info["species"],
                    "avatar": f"/avatar/{member_id}" if avatar_exists else None,
                    "avatar_emoji": data.get("metadata", {}).get("avatar", "🐾"),
                    "status": data.get("status", "unknown"),
                    "model": data.get("model", "unknown"),
                    "description": data.get("metadata", {}).get("description", "")
                })
            return members
        except Exception as e:
            print(f"获取成员数据失败: {e}")
            return []
    
    def _get_member_species(self, member_id):
        """获取成员种族信息"""
        if member_id == 'panda':
            return {"species": "熊猫 🐼"}
            
        identity_path = AGENTS_DIR / member_id / "IDENTITY.md"
        if not identity_path.exists():
            return {"species": "未知"}
        try:
            with open(identity_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "- **生物:**" in line or "- **种族:**" in line:
                        species = line.split(':', 1)[1].strip().replace('**', '').strip()
                        return {"species": species}
            return {"species": "未知"}
        except:
            return {"species": "未知"}
    
    def _get_kanban_data(self):
        """获取四象限看板数据"""
        kanban_tasks = self.task_manager.get_kanban_tasks()
        
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
            "last_updated": datetime.now().isoformat()
        }
    
    def _get_git_timeline(self):
        """获取 Git 时间线数据"""
        commits = self.git_adapter.get_recent_commits(limit=20)
        return {
            "commits": [commit.to_dict() for commit in commits],
            "stats": self.git_adapter.get_commit_stats(),
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
        except:
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
    server = HTTPServer(('0.0.0.0', PORT), ZooDevCenterHandler)
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
        server.server_close()
        print("✅ 服务器已安全关闭")


if __name__ == '__main__':
    run_server()