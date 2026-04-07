#!/usr/bin/env python3
"""
动物园成员使用事件总线的示例

展示如何在实际的动物园成员中使用事件总线进行通信。
"""

import sys
import os
import time
import threading

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from framework.shared.event_bus.event_bus import EventBus


class ZooMember:
    """动物园成员基类"""
    
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.event_bus = EventBus(member_name=name)
        self._setup_subscriptions()
        print(f"🐾 {self.name} ({self.role}) 已加入动物园，事件总线就绪")
    
    def _setup_subscriptions(self):
        """设置订阅（子类重写）"""
        pass
    
    def publish_event(self, event_type, payload, delay_seconds=0):
        """发布事件"""
        return self.event_bus.publish(event_type, payload, delay_seconds)
    
    def process_events(self):
        """处理事件"""
        return self.event_bus.process_events()
    
    def say(self, message):
        """成员说话"""
        print(f"[{self.name}] {message}")


class WeaverAnt(ZooMember):
    """织巢蚂蚁 - 工程师"""
    
    def _setup_subscriptions(self):
        """蚂蚁订阅的任务"""
        # 订阅新任务事件
        self.event_bus.subscribe("new_task", self.handle_new_task)
        # 订阅错误事件
        self.event_bus.subscribe("error", self.handle_error)
    
    def handle_new_task(self, event):
        """处理新任务"""
        task = event['payload']
        self.say(f"收到新任务: {task['description']}，优先级: {task.get('priority', 'normal')}")
        
        # 模拟处理任务
        time.sleep(0.5)
        
        # 发布任务完成事件
        self.publish_event("task_completed", {
            "task_id": task.get('id', 'unknown'),
            "result": "成功",
            "duration": 0.5,
            "worker": self.name
        })
    
    def handle_error(self, event):
        """处理错误"""
        error = event['payload']
        self.say(f"检测到错误: {error['error']}，建议: {error.get('suggestion', '无')}")
        
        # 尝试修复错误
        time.sleep(0.3)
        self.publish_event("error_fixed", {
            "original_error": error['error'],
            "fixer": self.name,
            "timestamp": time.time()
        })


class PandaManager(ZooMember):
    """熊猫园长 - 管理者"""
    
    def _setup_subscriptions(self):
        """园长订阅的事件"""
        # 订阅所有任务完成事件
        self.event_bus.subscribe("task_completed", self.handle_task_completed)
        # 订阅错误修复事件
        self.event_bus.subscribe("error_fixed", self.handle_error_fixed)
    
    def assign_task(self, description, assignee=None, priority="normal"):
        """分配任务"""
        task_id = f"task_{int(time.time())}"
        self.say(f"分配任务: {description} → {assignee or '未指定'}")
        
        self.publish_event("new_task", {
            "id": task_id,
            "description": description,
            "assignee": assignee,
            "priority": priority,
            "created_by": self.name
        })
        return task_id
    
    def handle_task_completed(self, event):
        """处理任务完成事件"""
        result = event['payload']
        self.say(f"任务完成: {result['task_id']}，执行者: {result['worker']}，结果: {result['result']}")
    
    def handle_error_fixed(self, event):
        """处理错误修复事件"""
        fix = event['payload']
        self.say(f"错误已修复: {fix['original_error']}，修复者: {fix['fixer']}")


class StingerHedgehog(ZooMember):
    """毒刺刺猬 - 审计员"""
    
    def _setup_subscriptions(self):
        """刺猬订阅的事件（审计所有事件）"""
        # 使用通配符方式订阅所有事件
        self.event_bus.subscribe("task_completed", self.audit_event)
        self.event_bus.subscribe("error", self.audit_event)
        self.event_bus.subscribe("error_fixed", self.audit_event)
        self.event_bus.subscribe("new_task", self.audit_event)
    
    def audit_event(self, event):
        """审计事件"""
        # 检查事件格式和内容
        required_fields = ['id', 'type', 'publisher', 'timestamp', 'payload']
        missing = [field for field in required_fields if field not in event]
        
        if missing:
            self.say(f"⚠️  审计警告: 事件 {event.get('id', 'unknown')} 缺少字段: {missing}")
        else:
            self.say(f"✅ 审计通过: {event['type']} from {event['publisher']}")
        
        # 记录审计日志
        self.publish_event("audit_log", {
            "event_id": event['id'],
            "event_type": event['type'],
            "auditor": self.name,
            "result": "passed" if not missing else "warning",
            "timestamp": time.time()
        })


def run_zoo_scenario():
    """运行动物园场景演示"""
    print("=" * 60)
    print("🏰 飝龘动物园 - 事件总线通信演示")
    print("=" * 60)
    
    # 创建动物园成员
    print("\n创建动物园成员...")
    panda = PandaManager("Panda", "园长")
    weaver = WeaverAnt("Weaver", "工程师蚂蚁")
    stinger = StingerHedgehog("Stinger", "审计员刺猬")
    
    time.sleep(1)
    
    # 场景1: 分配任务
    print("\n" + "=" * 60)
    print("场景1: 熊猫园长分配任务给蚂蚁")
    print("=" * 60)
    
    task1_id = panda.assign_task("修复并发安全问题", "Weaver", "high")
    task2_id = panda.assign_task("优化数据库查询", "Weaver", "medium")
    
    # 处理事件
    print("\n处理事件...")
    for _ in range(3):
        for member in [panda, weaver, stinger]:
            member.process_events()
        time.sleep(0.5)
    
    # 场景2: 模拟错误发生
    print("\n" + "=" * 60)
    print("场景2: 系统错误处理流程")
    print("=" * 60)
    
    # 发布错误事件
    weaver.publish_event("error", {
        "error": "数据库连接超时",
        "location": "db_connection.py:42",
        "severity": "critical",
        "suggestion": "检查网络连接和数据库状态"
    })
    
    # 处理事件
    print("\n处理错误事件...")
    for _ in range(3):
        for member in [panda, weaver, stinger]:
            member.process_events()
        time.sleep(0.5)
    
    # 场景3: 延迟任务
    print("\n" + "=" * 60)
    print("场景3: 延迟提醒任务")
    print("=" * 60)
    
    # 发布5秒后的提醒
    panda.publish_event("reminder", {
        "message": "每日站会时间到了！",
        "meeting_room": "虚拟会议室A",
        "participants": ["Panda", "Weaver", "Stinger"]
    }, delay_seconds=5)
    
    print("园长设置了5秒后的会议提醒...")
    
    # 等待并处理
    print("等待5秒...")
    for i in range(6):
        if i == 5:
            print("5秒到了，处理提醒事件...")
        for member in [panda, weaver, stinger]:
            member.process_events()
        time.sleep(1)
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("事件总线统计信息")
    print("=" * 60)
    
    for member in [panda, weaver, stinger]:
        stats = member.event_bus.get_statistics()
        print(f"\n{member.name} 的统计:")
        print(f"  总事件数: {stats['total_events']}")
        print(f"  已处理事件: {stats['processed_events']}")
        print(f"  待处理事件: {stats['pending_events']}")
        print(f"  订阅者数量: {sum(stats['subscribers'].values())}")
    
    # 显示生成的文件
    print("\n" + "=" * 60)
    print("生成的事件文件")
    print("=" * 60)
    
    base_dir = os.path.join(os.path.dirname(__file__))
    for file in ["events.json", "subscriptions.json", "processed_events.json"]:
        file_path = os.path.join(base_dir, file)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"{file}: {size} 字节")
    
    print("\n" + "=" * 60)
    print("🎉 动物园事件总线演示完成！")
    print("=" * 60)
    print("\n总结:")
    print("✅ 成员间通过事件总线解耦通信")
    print("✅ 支持异步处理和延迟事件")
    print("✅ 审计员可以监控所有事件")
    print("✅ 事件持久化存储，支持跨进程访问")
    print("✅ 完整的发布/订阅模式实现")


if __name__ == "__main__":
    run_zoo_scenario()