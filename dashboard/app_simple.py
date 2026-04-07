import json
import os
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from git_adapter import get_git_adapter

PORT = 18792
PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")
TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
TASK_TRACKER_PATH = PROJECT_ROOT / "framework" / "shared" / "task_tracker.json"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            path = TEMPLATES_DIR / 'dev_center.html'
            if not path.exists(): path = TEMPLATES_DIR / 'index.html'
            with open(path, 'rb') as f: self.wfile.write(f.read())
        elif self.path == '/api/kanban':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            with open(TASK_TRACKER_PATH, 'rb') as f: self.wfile.write(f.read())
        elif self.path.startswith('/static/'):
            file_path = STATIC_DIR / self.path.split('/static/')[-1]
            if file_path.exists():
                self.send_response(200)
                self.end_headers()
                with open(file_path, 'rb') as f: self.wfile.write(f.read())
            else: self.send_error(404)
        else: self.send_error(404)

print(f"Starting simple server on {PORT}...")
HTTPServer(('', PORT), SimpleHandler).serve_forever()
