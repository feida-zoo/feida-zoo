#!/usr/bin/env python3
"""
毒刺提供的 Task 1.5 修复建议实现示例
包含高危问题的修复方案
"""

import threading
import json
from pathlib import Path
from typing import Dict, Any, Optional
import os


class FixedRegistryManager:
    """
    修复后的 RegistryManager
    添加线程锁和文件锁，防止并发数据竞争
    """
    
    DEFAULT_VERSION = "1.0.0"
    
    def __init__(self, registry_file: str):
        self.registry_file = Path(registry_file).resolve()
        self._registry: Dict[str, Any] = {}
        self._lock = threading.Lock()  # 线程锁
        self._dirty = False  # 脏标记，用于优化性能
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """加载注册表文件（线程安全）"""
        with self._lock:
            if self.registry_file.exists():
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    self._registry = json.load(f)
            else:
                self._registry = {
                    "members": {},
                    "version": self.DEFAULT_VERSION,
                    "last_updated": None
                }
            self._dirty = False  # 加载后重置脏标记
            return self._registry
    
    def save(self, force: bool = False) -> None:
        """
        保存注册表到文件（线程安全）
        
        Args:
            force: 强制保存，即使没有修改
        """
        if not self._dirty and not force:
            return  # 优化：没有修改时跳过保存
        
        with self._lock:
            self._registry["last_updated"] = datetime.now().isoformat()
            
            # 原子写入：先写入临时文件，然后重命名
            temp_file = self.registry_file.with_suffix('.json.tmp')
            
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._registry, f, indent=2, ensure_ascii=False)
                
                # 原子重命名（Unix系统上）
                temp_file.replace(self.registry_file)
                self._dirty = False  # 保存成功后重置脏标记
                
            except Exception as e:
                # 清理临时文件
                if temp_file.exists():
                    temp_file.unlink(missing_ok=True)
                raise e
    
    def register_member(self, member_data: Dict[str, Any]) -> str:
        """注册新成员（标记为脏）"""
        # ... 原有逻辑 ...
        self._dirty = True
        return member_id
    
    # 其他方法类似，在修改_registry时设置_dirty = True


class FixedWorkspaceManager:
    """
    修复后的 WorkspaceManager
    添加路径安全验证，防止路径逃逸攻击
    """
    
    META_FILE_NAME = "member.json"
    DEFAULT_SUBDIRS = ["src", "docs", "outputs"]
    
    def __init__(self, agents_base_path: str):
        self.agents_base_path = Path(agents_base_path).resolve()
        self._ensure_base_directory()
    
    def _validate_member_id(self, member_id: str) -> None:
        """
        验证成员ID的安全性
        
        Raises:
            ValueError: 如果成员ID不安全
        """
        # 1. 不能是空字符串
        if not member_id:
            raise ValueError("成员ID不能为空")
        
        # 2. 不能是绝对路径
        if Path(member_id).is_absolute():
            raise ValueError(f"成员ID不能是绝对路径: '{member_id}'")
        
        # 3. 不能包含路径遍历尝试
        if member_id in ('.', '..'):
            raise ValueError(f"无效的成员ID: '{member_id}'")
        
        # 4. 检查规范化后是否逃逸出base_path
        try:
            # 尝试拼接并规范化
            full_path = (self.agents_base_path / member_id).resolve()
            
            # 确保路径在base_path内
            full_path.relative_to(self.agents_base_path)
            
        except ValueError:
            raise ValueError(f"检测到路径遍历尝试: '{member_id}'")
        
        # 5. 不允许的字符（根据需求调整）
        forbidden_chars = ['\x00', '\n', '\r']  # 空字符和换行符
        for char in forbidden_chars:
            if char in member_id:
                raise ValueError(f"成员ID包含非法字符: '{char}'")
    
    def get_workspace_path(self, member_id: str) -> Path:
        """
        安全获取成员工作区路径
        
        Args:
            member_id: 成员ID
            
        Returns:
            安全的工作区路径
            
        Raises:
            ValueError: 如果成员ID不安全
        """
        self._validate_member_id(member_id)
        return (self.agents_base_path / member_id).resolve()
    
    def create_workspace(self, member_id: str) -> Path:
        """
        安全创建成员工作区
        
        Args:
            member_id: 成员ID
            
        Returns:
            创建的工作区路径
            
        Raises:
            ValueError: 如果成员ID不安全或工作区已存在
        """
        self._validate_member_id(member_id)
        workspace_path = self.get_workspace_path(member_id)
        
        # 原有逻辑...
        # 确保路径在base_path内（双重检查）
        try:
            workspace_path.relative_to(self.agents_base_path)
        except ValueError:
            raise ValueError(f"路径逃逸出安全区域: '{member_id}'")
        
        # 创建工作区...
        return workspace_path


if __name__ == "__main__":
    print("🦂 毒刺修复建议示例")
    print("=" * 50)
    
    # 测试修复后的WorkspaceManager
    import tempfile
    temp_dir = tempfile.TemporaryDirectory()
    
    manager = FixedWorkspaceManager(temp_dir.name)
    
    test_cases = [
        ("normal", True, "正常ID"),
        ("", False, "空ID"),
        ("/etc/passwd", False, "绝对路径"),
        ("..", False, "上级目录"),
        ("normal/../evil", True, "相对路径（但会被规范化）"),
    ]
    
    print("路径安全测试:")
    for member_id, should_pass, description in test_cases:
        try:
            path = manager.get_workspace_path(member_id)
            status = "✅ 通过" if should_pass else "❌ 应该失败但通过了"
        except ValueError as e:
            status = "✅ 正确拒绝" if not should_pass else f"❌ 错误拒绝: {e}"
        
        print(f"  '{member_id:20}' - {description:20} - {status}")
    
    temp_dir.cleanup()
    
    print("\n🔧 修复总结:")
    print("1. RegistryManager: 添加线程锁 + 原子写入 + 脏标记优化")
    print("2. WorkspaceManager: 添加成员ID安全验证")
    print("3. 性能优化: 减少不必要的文件写入")
    print("4. 安全性: 防止路径逃逸和并发数据竞争")