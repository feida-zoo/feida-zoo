#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zoo Dashboard - 飝龘动物园成员展示看板
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# 配置
PORT = 18790
PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")
PANDA_ROOT = Path("/home/afei/workspace/panda")
REGISTRY_PATH = PROJECT_ROOT / "framework" / "data" / "registry.json"
AGENTS_DIR = PANDA_ROOT / "agents"
TEMPLATES_DIR = PANDA_ROOT / "dashboard" / "templates"
STATIC_DIR = PANDA_ROOT / "dashboard" / "static"

class ZooDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self._serve_file(TEMPLATES_DIR / 'index.html', 'text/html')
        elif self.path == '/api/members':
            self._send_json(self._get_member_data())
        elif self.path.startswith('/avatar/'):
            member_id = self.path.split('/')[-1]
            avatar_path = AGENTS_DIR / member_id / "avatar.png"
            if avatar_path.exists():
                self._serve_file(avatar_path, 'image/png')
            else:
                self.send_error(404)
        elif self.path == '/static/style.css':
            self._serve_file(STATIC_DIR / 'style.css', 'text/css')
        else:
            self.send_error(404)

    def _serve_file(self, path, content_type):
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
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def _get_member_data(self):
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
            return []

    def _get_member_species(self, member_id):
        # 特殊处理主脑 Panda 的种族
        if member_id == 'panda':
            return {"species": "熊猫 🐼"}
            
        identity_path = AGENTS_DIR / member_id / "IDENTITY.md"
        if not identity_path.exists():
            return {"species": "未知"}
        try:
            with open(identity_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "- **生物:**" in line or "- **种族:**" in line:
                        # 移除 Markdown 加粗标识（**）并清理空白
                        species = line.split(':', 1)[1].strip().replace('**', '').strip()
                        return {"species": species}
            return {"species": "未知"}
        except:
            return {"species": "未知"}

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), ZooDashboardHandler)
    print(f"🚀 Zoo-Dashboard v1.0 启动: http://localhost:{PORT}")
    server.serve_forever()
