import os
import json
import time
import subprocess
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

PORT = 18792
PROJECT_ROOT = Path("/home/afei/workspace/code/feida_zoo")
TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
TASK_TRACKER_PATH = PROJECT_ROOT / "framework" / "shared" / "task_tracker.json"


@dataclass
class GitCommit:
    """Git 提交记录模型"""
    hash: str
    author_name: str
    author_email: str
    date: str
    message: str
    emoji: str = ""
    member: str = ""

    def to_dict(self):
        return asdict(self)


class GitAdapter:
    """Git 适配器类"""

    # 成员 Emoji 映射表
    MEMBER_EMOJI_MAP = {
        '🐢': 'alpha',
        '🐜': 'weaver',
        '🦂': 'stinger',
        '🐼': 'panda',
        '📜': 'aeterna'
    }

    # Emoji 到中文描述的映射
    EMOJI_DESCRIPTION = {
        '🐢': '阿尔法 (架构师)',
        '🐜': '织巢蚁 (工程师)',
        '🦂': '毒刺 (安全审计)',
        '🐼': '熊猫 (园长)',
        '📜': '史官 (历史记录)'
    }

    def __init__(self, repo_path: str = None):
        """
        初始化 Git 适配器

        Args:
            repo_path: Git 仓库路径，默认为当前项目的根目录
        """
        if repo_path is None:
            self.repo_path = PROJECT_ROOT
        else:
            self.repo_path = Path(repo_path)

        # 缓存配置
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 60  # 缓存时间 60 秒

    def _is_git_repo(self) -> bool:
        """检查是否为 Git 仓库"""
        git_dir = self.repo_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _run_git_command(self, cmd: List[str]) -> Tuple[str, str]:
        """
        运行 Git 命令并返回结果

        Args:
            cmd: Git 命令列表

        Returns:
            (stdout, stderr) 元组
        """
        try:
            process = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=10  # 10 秒超时
            )
            return process.stdout.strip(), process.stderr.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git 命令执行超时")
        except Exception as e:
            raise RuntimeError(f"执行 Git 命令失败: {e}")

    def _parse_git_log_line(self, line: str) -> Optional[GitCommit]:
        """
        解析 Git log 格式化的行

        Git log 格式: %H|%an|%ae|%ad|%s
        """
        parts = line.split('|', 4)
        if len(parts) != 5:
            return None

        commit_hash, author_name, author_email, date_str, message = parts

        # 提取 Emoji 和识别成员
        emoji = ""
        member = ""

        # 从消息中提取 Emoji (通常是第一个字符)
        if message and len(message) > 0:
            # 检查消息开头是否有 Emoji
            first_char = message[0]
            if first_char in self.MEMBER_EMOJI_MAP:
                emoji = first_char
                member = self.MEMBER_EMOJI_MAP[emoji]
            else:
                # 检查消息中是否包含 Emoji
                for emoji_char in self.MEMBER_EMOJI_MAP:
                    if emoji_char in message:
                        emoji = emoji_char
                        member = self.MEMBER_EMOJI_MAP[emoji]
                        break

        return GitCommit(
            hash=commit_hash[:8],  # 只取短哈希
            author_name=author_name,
            author_email=author_email,
            date=date_str,
            message=message,
            emoji=emoji,
            member=member
        )

    def get_recent_commits(self, limit: int = 50) -> List[GitCommit]:
        """
        获取最近的提交记录

        Args:
            limit: 限制返回的提交数量

        Returns:
            GitCommit 对象列表
        """
        # Git log 格式: 哈希|作者名|作者邮箱|日期|消息
        format_str = "%H|%an|%ae|%ad|%s"
        cmd = ["git", "log", f"--pretty=format:{format_str}", f"--max-count={limit}"]

        stdout, stderr = self._run_git_command(cmd)
        if stderr:
            print(f"Git 命令警告: {stderr}")

        commits = []
        for line in stdout.split('\n'):
            if line.strip():
                commit = self._parse_git_log_line(line)
                if commit:
                    commits.append(commit)

        return commits

    def get_commit_stats(self) -> Dict:
        """
        获取提交统计信息 - 使用 git shortlog -sn --all 获取真实统计数据

        Returns:
            包含统计信息的字典
        """
        cache_key = f"commit_stats_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data

        try:
            # 使用 git shortlog -sn --all 获取所有分支的提交统计
            cmd = ["git", "shortlog", "-sn", "--all", "--no-merges"]
            stdout, stderr = self._run_git_command(cmd)
            
            if stderr:
                print(f"Git shortlog 警告: {stderr}")
                # 如果失败，回退到原来的方法
                return self._get_commit_stats_fallback()
            
            # 解析 shortlog 输出，格式如："    12\tAuthor Name <email>"
            author_stats = {}
            total_commits = 0
            
            for line in stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # 匹配数字和作者名
                parts = line.split('\t')
                if len(parts) >= 2:
                    try:
                        count = int(parts[0].strip())
                        author_info = parts[1].strip()
                        author_stats[author_info] = count
                        total_commits += count
                    except ValueError:
                        continue
            
            # 获取所有提交（不仅仅是最近的）来建立 Emoji 统计
            # 我们需要分析所有提交的 Emoji 分布
            all_commits = []
            try:
                # 获取所有提交的简略信息
                all_commits = self.get_recent_commits(limit=200)  # 获取足够多的提交
            except Exception as e:
                print(f"获取所有提交失败: {e}")
                # 使用最近提交作为替代
                all_commits = self.get_recent_commits(limit=50)
            
            # 分析所有提交的 Emoji 分布
            emoji_counts = {}
            for commit in all_commits:
                if commit.emoji and commit.emoji in self.MEMBER_EMOJI_MAP:
                    member_id = self.MEMBER_EMOJI_MAP[commit.emoji]
                    if member_id not in emoji_counts:
                        emoji_counts[member_id] = 0
                    emoji_counts[member_id] += 1
            
            # 如果没有 Emoji 统计数据，使用默认分布（基于最近的提交）
            if not emoji_counts and all_commits:
                for commit in all_commits[:20]:  # 只看最近的20个提交
                    if commit.emoji and commit.emoji in self.MEMBER_EMOJI_MAP:
                        member_id = self.MEMBER_EMOJI_MAP[commit.emoji]
                        if member_id not in emoji_counts:
                            emoji_counts[member_id] = 0
                        emoji_counts[member_id] += 1
            
            # 按成员统计
            member_counts = {}
            for emoji, member_id in self.MEMBER_EMOJI_MAP.items():
                member_counts[member_id] = {
                    "id": member_id,
                    "emoji": emoji,
                    "name": self.EMOJI_DESCRIPTION[emoji],
                    "commit_count": emoji_counts.get(member_id, 0)
                }
            
            # 统计未知成员（没有 Emoji 的提交）
            unknown_count = total_commits - sum(emoji_counts.values())
            member_counts["unknown"] = {
                "id": "unknown",
                "emoji": "❓",
                "name": "未知成员",
                "commit_count": max(0, unknown_count)  # 确保不为负数
            }
            
            # 转换为列表排序
            members_list = sorted(
                [m for m in member_counts.values() if m["commit_count"] > 0],
                key=lambda x: x["commit_count"],
                reverse=True
            )
            
            result = {
                "members": members_list,
                "total_commits": total_commits,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"获取真实提交统计失败: {e}")
            # 回退到原来的方法
            return self._get_commit_stats_fallback()

        # 缓存结果
        self._cache[cache_key] = (result, time.time())
        return result
    
    def _get_commit_stats_fallback(self) -> Dict:
        """
        回退方法：使用原来的 git log 方法获取统计
        """
        try:
            commits = self.get_recent_commits(limit=200)
        except Exception as e:
            print(f"回退方法也失败: {e}")
            # 返回默认数据
            return {
                "members": [
                    {"id": "weaver", "name": "织巢蚁 (工程师)", "commit_count": 0, "emoji": "🐜"},
                    {"id": "stinger", "name": "毒刺 (安全审计)", "commit_count": 0, "emoji": "🦂"},
                    {"id": "panda", "name": "熊猫 (园长)", "commit_count": 0, "emoji": "🐼"},
                    {"id": "alpha", "name": "阿尔法 (架构师)", "commit_count": 0, "emoji": "🐢"},
                    {"id": "aeterna", "name": "史官 (历史记录)", "commit_count": 0, "emoji": "📜"}
                ],
                "total_commits": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }

        # 按成员统计
        member_counts = {}
        for emoji, member_id in self.MEMBER_EMOJI_MAP.items():
            member_counts[member_id] = {
                "id": member_id,
                "emoji": emoji,
                "name": self.EMOJI_DESCRIPTION[emoji],
                "commit_count": 0
            }

        # 统计提交
        for commit in commits:
            if commit.member and commit.member in member_counts:
                member_counts[commit.member]["commit_count"] += 1

        # 转换为列表排序
        members_list = sorted(
            member_counts.values(),
            key=lambda x: x["commit_count"],
            reverse=True
        )

        return {
            "members": members_list,
            "total_commits": len(commits),
            "last_updated": datetime.now().isoformat()
        }

    def get_timeline(self, limit: int = 10) -> List[Dict]:
        """
        获取最近提交时间线

        Args:
            limit: 返回记录数量

        Returns:
            提交记录列表
        """
        cache_key = f"timeline_{limit}"
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data

        try:
            commits = self.get_recent_commits(limit=limit)
            result = [commit.to_dict() for commit in commits]
        except Exception as e:
            print(f"获取时间线失败: {e}")
            result = []

        # 缓存结果
        self._cache[cache_key] = (result, time.time())
        return result


# 全局 GitAdapter 单例
_git_adapter = None

def get_git_adapter() -> GitAdapter:
    """获取 GitAdapter 单例"""
    global _git_adapter
    if _git_adapter is None:
        try:
            _git_adapter = GitAdapter()
        except Exception as e:
            print(f"初始化 GitAdapter 失败: {e}")
            _git_adapter = GitAdapter(PROJECT_ROOT)
    return _git_adapter


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
                    adapter = get_git_adapter()
                    response_data = adapter.get_commit_stats()
                elif self.path == '/api/git-timeline':
                    adapter = get_git_adapter()
                    response_data = adapter.get_timeline(limit=10)
                elif self.path == '/api/system-info':
                    response_data = {"status": "ok", "version": "2.4.1"}

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

if __name__ == "__main__":
    print(f"Starting V2.4 Full-Compatibility server on {PORT}...")
    HTTPServer(('', PORT), ZooHandler).serve_forever()
