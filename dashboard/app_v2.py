import os
import json
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 18792
PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")
TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
TASK_TRACKER_PATH = PROJECT_ROOT / "framework" / "shared" / "task_tracker.json"

class ZooHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path == '/':
            target = TEMPLATES_DIR / 'dev_center.html'
            if not target.exists(): target = TEMPLATES_DIR / 'index.html'
            return str(target)
        if path.startswith('/static/'):
            return str(STATIC_DIR / path.split('/static/')[-1])
        return super().translate_path(path)

    def do_GET(self):
        # 统一处理所有 API 请求
        if self.path.startswith('/api/'):
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                # 读取基础数据
                try:
                    with open(TASK_TRACKER_PATH, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)
                except:
                    raw_data = {}

                response_data = {}

                if self.path == '/api/kanban':
                    response_data = self._adapt_kanban(raw_data)
                elif self.path == '/api/task-stats':
                    response_data = self._adapt_stats(raw_data)
                elif self.path == '/api/git-stats':
                    response_data = {"members": [
                        {"id": "weaver", "name": "织巢蚁 (工程师)", "commit_count": 21, "emoji": "🐜"},
                        {"id": "stinger", "name": "毒刺 (安全审计)", "commit_count": 7, "emoji": "🦂"},
                        {"id": "panda", "name": "熊猫 (园长)", "commit_count": 7, "emoji": "🐼"},
                        {"id": "alpha", "name": "阿尔法 (架构师)", "commit_count": 3, "emoji": "🐢"}
                    ]}
                elif self.path == '/api/git-timeline':
                    response_data = []
                elif self.path == '/api/system-info':
                    response_data = {"status": "ok", "version": "1.0.0"}
                
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"API Error: {e}")
                self.send_error(500, str(e))
                return
        
        # 针对 SSE 路径返回空事件流
        if self.path == '/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            return

        return super().do_GET()

    def _adapt_kanban(self, data):
        kanban = {
            "columns": {
                "backlog": {"title": "📥 需求池", "tasks": []},
                "in_progress": {"title": "🚧 进行中", "tasks": []},
                "in_review": {"title": "🔍 待验收", "tasks": []},
                "done": {"title": "✅ 已完成", "tasks": []}
            }
        }
        phases = data.get("phases", {})
        for p_key, p_val in phases.items():
            for t in p_val.get("tasks", []):
                status = t.get("status", "pending")
                target = "backlog"
                if status == "completed": target = "done"
                elif status == "in_progress": target = "in_progress"
                elif status == "in_review": target = "in_review"
                
                kanban["columns"][target]["tasks"].append({
                    "id": t.get("id"), 
                    "name": t.get("name"), 
                    "description": t.get("description", ""),
                    "assignee": t.get("assignee"), 
                    "severity": t.get("severity", "P3"),
                    "phase_name": p_val.get("name"), 
                    "completed_at": t.get("completed_at", ""),
                    "verification": t.get("verification", []),
                    "notes": t.get("notes", "")
                })
        return kanban

    def _adapt_stats(self, data):
        p1 = data.get("phases", {}).get("P1", {})
        p2 = data.get("phases", {}).get("P2", {})
        
        total_tasks = len(p1.get("tasks", [])) + len(p2.get("tasks", []))
        completed_tasks = len([t for t in p1.get("tasks", []) if t.get("status") == "completed"]) +                           len([t for t in p2.get("tasks", []) if t.get("status") == "completed"])
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0,
            "in_progress_tasks": 0,
            "current_phase": data.get("current_phase", "P2"),
            "current_phase_name": data.get("phases", {}).get(data.get("current_phase", "P2"), {}).get("name", "未知阶段"),
            "current_phase_status": data.get("phases", {}).get(data.get("current_phase", "P2"), {}).get("status", "pending"),
            "tdd_enabled": data.get("metadata", {}).get("tdd_enabled", True)
        }

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

print(f"Starting V2.4 Full-Compatibility server on {PORT}...")
HTTPServer(('', PORT), ZooHandler).serve_forever()
