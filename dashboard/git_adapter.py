#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Adapter - Zoo Dev-Center Git 集成适配器
实现实时获取 Git Log 并按 Emoji 识别成员的功能
"""

import subprocess
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import threading
from dataclasses import dataclass, asdict


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
    """Git 适配器类 - 支持多仓库"""
    
    # 项目定义
    _FEIDA_ZOO_HOME = os.environ.get("FEIDA_ZOO_HOME", "/home/afei/workspace/code/feida_zoo")

    PROJECTS = {
        "feida_zoo": {
            "path": _FEIDA_ZOO_HOME,
            "name": "feida-zoo",
            "emoji": "🏗️"
        },
        "panda": {
            "path": os.path.join(os.path.dirname(_FEIDA_ZOO_HOME), "panda"),
            "name": "panda",
            "emoji": "🐼"
        },
        "members": {
            "path": os.path.dirname(_FEIDA_ZOO_HOME),
            "name": "members",
            "emoji": "🏠"
        }
    }
    
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
            # 默认为当前项目的根目录
            self.repo_path = Path(__file__).parent.parent
        else:
            self.repo_path = Path(repo_path)
        
        # 不抛出异常，让 get_recent_commits 等方法自行容错
    
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
                encoding='utf-8'
            )
            return process.stdout.strip(), process.stderr.strip()
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
    
    def get_all_projects(self) -> Dict:
        """获取所有项目列表"""
        return self.PROJECTS
    
    def get_recent_commits_for_project(self, project_key: str, limit: int = 50) -> List[GitCommit]:
        """获取指定项目的最近提交"""
        if project_key not in self.PROJECTS:
            return []
        old_path = self.repo_path
        self.repo_path = Path(self.PROJECTS[project_key]["path"])
        try:
            commits = self.get_recent_commits(limit=limit)
        except:
            commits = []
        self.repo_path = old_path
        return commits
    
    def get_commit_stats_for_project(self, project_key: str) -> Dict:
        """获取指定项目的提交统计"""
        if project_key not in self.PROJECTS:
            return {"total_commits": 0, "members": {}}
        old_path = self.repo_path
        self.repo_path = Path(self.PROJECTS[project_key]["path"])
        try:
            stats = self.get_commit_stats()
        except:
            stats = {"total_commits": 0, "members": {}}
        self.repo_path = old_path
        return stats
    
    def get_recent_commits(self, limit: int = 50) -> List[GitCommit]:
        """
        获取最近的提交记录
        
        Args:
            limit: 限制返回的提交数量
            
        Returns:
            GitCommit 对象列表
        """
        # Git log 格式: 哈希|作者名|作者邮箱|日期|消息
        if not self._is_git_repo():
            return []
        format_str = "%H|%an|%ae|%ad|%s"
        cmd = ["git", "log", f"--pretty=format:{format_str}", f"--max-count={limit}"]
        
        try:
            stdout, stderr = self._run_git_command(cmd)
        except:
            return []
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
        获取提交统计信息
        
        Returns:
            包含统计信息的字典
        """
        commits = self.get_recent_commits(limit=100)
        
        # 按成员统计
        member_stats = {}
        for emoji, member_id in self.MEMBER_EMOJI_MAP.items():
            member_stats[member_id] = {
                'emoji': emoji,
                'name': self.EMOJI_DESCRIPTION.get(emoji, member_id),
                'count': 0,
                'recent_commits': []
            }
        
        # 统计未知成员
        member_stats['unknown'] = {
            'emoji': '❓',
            'name': '未知成员',
            'count': 0,
            'recent_commits': []
        }
        
        # 统计提交
        for commit in commits:
            if commit.member and commit.member in member_stats:
                member_stats[commit.member]['count'] += 1
                member_stats[commit.member]['recent_commits'].append(commit.to_dict())
            else:
                member_stats['unknown']['count'] += 1
                member_stats['unknown']['recent_commits'].append(commit.to_dict())
        
        # 限制每个成员的最近提交数量
        for stats in member_stats.values():
            stats['recent_commits'] = stats['recent_commits'][:5]
        
        return {
            'total_commits': len(commits),
            'members': member_stats,
            'last_updated': datetime.now().isoformat()
        }
    
    def get_repo_info(self) -> Dict:
        """
        获取仓库基本信息
        
        Returns:
            仓库信息字典
        """
        info = {}
        
        # 获取当前分支
        branch_stdout, _ = self._run_git_command(["git", "branch", "--show-current"])
        info['current_branch'] = branch_stdout.strip()
        
        # 获取远程信息
        remote_stdout, _ = self._run_git_command(["git", "remote", "-v"])
        info['remotes'] = remote_stdout.strip()
        
        # 获取最新提交
        commits = self.get_recent_commits(limit=1)
        if commits:
            info['latest_commit'] = commits[0].to_dict()
        
        info['repo_path'] = str(self.repo_path)
        info['is_git_repo'] = self._is_git_repo()
        
        return info


class GitTimelineWatcher:
    """Git 时间线监视器，用于实时更新"""
    
    def __init__(self, git_adapter: GitAdapter, update_interval: int = 30):
        """
        初始化时间线监视器
        
        Args:
            git_adapter: GitAdapter 实例
            update_interval: 更新间隔（秒）
        """
        self.git_adapter = git_adapter
        self.update_interval = update_interval
        self._stop_event = threading.Event()
        self._thread = None
        self.last_commits = []
        self.callbacks = []
    
    def start(self):
        """启动监视器线程"""
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止监视器线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
    
    def register_callback(self, callback):
        """
        注册回调函数
        
        Args:
            callback: 当有新提交时调用的函数，接收 commits 列表作为参数
        """
        self.callbacks.append(callback)
    
    def _watch_loop(self):
        """监视循环"""
        while not self._stop_event.is_set():
            try:
                # 获取最新的提交
                current_commits = self.git_adapter.get_recent_commits(limit=20)
                
                # 检查是否有新提交
                if current_commits != self.last_commits:
                    self.last_commits = current_commits
                    
                    # 调用所有注册的回调
                    for callback in self.callbacks:
                        try:
                            callback(current_commits)
                        except Exception as e:
                            print(f"回调函数执行失败: {e}")
                
                # 等待下一次检查
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"Git 时间线监视错误: {e}")
                time.sleep(self.update_interval)
    
    def get_current_timeline(self) -> List[Dict]:
        """获取当前时间线数据"""
        return [commit.to_dict() for commit in self.last_commits]


# 单例实例
_git_adapter_instance = None
_git_watcher_instance = None


def get_git_adapter() -> GitAdapter:
    """获取 GitAdapter 单例实例"""
    global _git_adapter_instance
    if _git_adapter_instance is None:
        _git_adapter_instance = GitAdapter()
    return _git_adapter_instance


def get_git_watcher() -> GitTimelineWatcher:
    """获取 GitTimelineWatcher 单例实例"""
    global _git_watcher_instance
    if _git_watcher_instance is None:
        git_adapter = get_git_adapter()
        _git_watcher_instance = GitTimelineWatcher(git_adapter)
    return _git_watcher_instance


if __name__ == "__main__":
    # 测试代码
    adapter = GitAdapter()
    print("Git 仓库信息:")
    print(json.dumps(adapter.get_repo_info(), indent=2, ensure_ascii=False))
    
    print("\n提交统计:")
    stats = adapter.get_commit_stats()
    print(f"总提交数: {stats['total_commits']}")
    for member_id, member_stats in stats['members'].items():
        if member_stats['count'] > 0:
            print(f"{member_stats['emoji']} {member_stats['name']}: {member_stats['count']} 次提交")
    
    print("\n最近提交:")
    commits = adapter.get_recent_commits(limit=5)
    for commit in commits:
        print(f"{commit.emoji} {commit.hash}: {commit.message}")