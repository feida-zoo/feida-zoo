# 跨成员事件总线 (Event Bus)

## 📋 概述

基于文件系统的异步消息队列，支持动物园成员间的发布/订阅模式通信，解耦成员唤醒逻辑。

## 🎯 功能特性

- ✅ **发布/订阅模式**: 支持事件发布和订阅
- ✅ **异步处理**: 事件产生与消费解耦，支持延迟处理
- ✅ **文件持久化**: JSON文件存储，跨进程/跨成员可见
- ✅ **并发安全**: 使用文件锁确保多线程/多进程安全
- ✅ **事件去重**: 避免重复处理相同事件
- ✅ **统计监控**: 提供详细的事件统计信息
- ✅ **自动清理**: 自动清理旧的事件数据

## 🏗️ 架构设计

```
事件总线架构:
├── EventBus (核心类)
│   ├── publish() - 发布事件
│   ├── subscribe() - 订阅事件
│   ├── process_events() - 处理事件
│   ├── get_statistics() - 获取统计
│   └── clear_processed_events() - 清理事件
├── 文件存储
│   ├── events.json - 所有事件
│   ├── subscriptions.json - 订阅关系
│   └── processed_events.json - 已处理事件
└── 并发控制
    ├── 文件锁 (fcntl)
    ├── 线程锁 (threading.RLock)
    └── 原子写入
```

## 📦 安装与使用

### 基本使用

```python
from framework.shared.event_bus.event_bus import EventBus

# 创建事件总线实例
bus = EventBus(member_name="panda")

# 订阅事件
def task_handler(event):
    print(f"收到任务: {event['payload']['description']}")

bus.subscribe("new_task", task_handler)

# 发布事件
event_id = bus.publish("new_task", {
    "description": "处理用户数据",
    "priority": "high"
})

# 处理事件
processed = bus.process_events()
```

### 单例模式

```python
from framework.shared.event_bus.event_bus import get_event_bus

# 获取全局事件总线实例
bus = get_event_bus(member_name="weaver")
```

## 🔧 API 参考

### EventBus 类

#### `__init__(base_dir=None, member_name="unknown")`
- `base_dir`: 事件存储目录（默认: `framework/shared/event_bus/`）
- `member_name`: 成员名称，用于标识事件发布者

#### `publish(event_type, payload, delay_seconds=0)`
发布事件到总线。
- `event_type`: 事件类型字符串
- `payload`: 事件载荷（字典）
- `delay_seconds`: 延迟处理时间（秒）
- 返回: 事件ID

#### `subscribe(event_type, callback)`
订阅指定类型的事件。
- `event_type`: 要订阅的事件类型
- `callback`: 事件处理回调函数，接收 `event_dict` 参数

#### `process_events(max_events=10)`
处理待处理的事件。
- `max_events`: 最大处理事件数量
- 返回: 实际处理的事件数量

#### `get_pending_events(event_type=None)`
获取待处理的事件。
- `event_type`: 可选，指定事件类型
- 返回: 待处理事件列表

#### `get_statistics()`
获取事件总线统计信息。
- 返回: 统计信息字典

#### `clear_processed_events(older_than_days=7)`
清理已处理的事件。
- `older_than_days`: 清理多少天前的已处理事件

## 📊 事件格式

```json
{
  "id": "panda_new_task_abc123",
  "type": "new_task",
  "publisher": "panda",
  "timestamp": 1743955200.0,
  "payload": {
    "description": "处理用户数据",
    "priority": "high"
  },
  "processed": false,
  "process_after": 0
}
```

## 🧪 测试

### 运行测试套件
```bash
python3 framework/shared/event_bus/test_basic.py
```

### 运行完整演示
```bash
python3 framework/shared/event_bus/event_bus_demo.py
```

### 运行动物园示例
```bash
python3 framework/shared/event_bus/zoo_members_example.py
```

## 🐘 动物园使用示例

### 成员通信场景

```python
# 熊猫园长分配任务
panda.assign_task("修复安全漏洞", "weaver", "high")

# 蚂蚁工程师处理任务
weaver.handle_new_task(event)

# 刺猬审计员监控事件
stinger.audit_event(event)
```

### 事件流
```
熊猫发布任务 → 事件总线 → 蚂蚁接收处理 → 发布完成事件 → 事件总线 → 熊猫接收确认
```

## 🔒 并发安全

### 多线程安全
- 使用 `threading.RLock` 保护内部状态
- 文件操作使用 `fcntl` 文件锁
- 原子写入避免文件损坏

### 多进程安全
- 基于文件的存储，所有进程可见相同数据
- 文件锁确保跨进程同步
- 事件ID全局唯一，避免冲突

## 📈 性能考虑

### 优化建议
1. **批量处理**: 使用 `process_events(max_events=50)` 批量处理
2. **定期清理**: 定期调用 `clear_processed_events()`
3. **事件去重**: 避免发布重复事件
4. **延迟事件**: 合理使用延迟处理减少即时负载

### 监控指标
```python
stats = bus.get_statistics()
print(f"总事件: {stats['total_events']}")
print(f"待处理: {stats['pending_events']}")
print(f"按类型: {stats['event_types']}")
```

## 🐛 故障排除

### 常见问题

1. **权限错误**
   - 确保 `event_bus/` 目录有写入权限
   - 检查文件锁是否正常工作

2. **事件丢失**
   - 验证 `events.json` 文件完整性
   - 检查订阅者是否正确注册

3. **重复处理**
   - 检查事件ID生成逻辑
   - 验证 `processed_events.json` 状态

### 调试模式
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📁 文件说明

- `event_bus.py` - 核心事件总线类
- `event_bus_demo.py` - 功能演示脚本
- `test_basic.py` - 单元测试套件
- `zoo_members_example.py` - 动物园使用示例
- `events.json` - 事件存储文件
- `subscriptions.json` - 订阅关系文件
- `processed_events.json` - 已处理事件记录

## 🔄 与现有系统集成

### 与成员系统集成
```python
class ZooMember:
    def __init__(self, name):
        self.event_bus = EventBus(member_name=name)
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        # 设置成员特定的事件处理器
        pass
```

### 与看板集成
```python
# 在看板中显示事件统计
def update_dashboard_stats():
    stats = event_bus.get_statistics()
    dashboard.show_event_stats(stats)
```

## 📝 版本历史

- **v1.0.0** (2026-04-06): 初始版本，实现核心功能
  - 发布/订阅模式
  - 文件持久化
  - 并发安全
  - 事件去重
  - 延迟事件支持

## 👥 贡献者

- **织巢 (Weaver)** - 核心实现
- **熊猫 (Panda)** - 需求定义与测试
- **毒刺 (Stinger)** - 安全审计

## 📄 许可证

飝龘动物园项目内部使用。

---

**🚀 让动物园成员真正"对话"，而不是孤岛作战！** 🐜🧨