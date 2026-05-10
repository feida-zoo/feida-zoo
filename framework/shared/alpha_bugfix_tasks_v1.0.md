# 🐢 Bugfix 任务简报 — 毒刺 P2 修复

> **发送方**: 阿尔法 🐢
> **接收方**: 织巢 🐜
> **日期**: 2026-05-10

---

## 修复清单

### 🔴 P2-1：`check_release_signal()` 放行信号只精确匹配

**文件**: `framework/core/harness/validators.py`
**问题**: `"LGTM，代码质量不错"` 不会被识别为放行，因为精确匹配要求只有 `"lgtm"` 三个字

**修复方向**：改为 `any(signal in normalized for signal in RELEASE_SIGNALS)` 做部分匹配，但排除 `"条件性通过"` 命中 `"通过"`

```python
def check_release_signal(review_text: str) -> bool:
    if not review_text:
        return False
    normalized = review_text.lower().strip()
    if "条件性通过" in normalized:
        return False
    return any(signal in normalized for signal in RELEASE_SIGNALS)
```

---

### 🔴 P2-2 + P2-4：InboxWatcher / DeliveryWatcher 同步阻塞

**文件**: `framework/core/mesh/inbox_watcher.py`, `framework/core/mesh/delivery_watcher.py`
**问题**: `start()` 和 `start_filesystem_watch()` 里的 `while self._running` 无限循环阻塞调用线程

**修复方向**：`start()` 内部用 `threading.Thread(daemon=True)` 包装轮询逻辑，`start()` 本身立即返回

```python
def start(self):
    thread = threading.Thread(target=self._run, daemon=True)
    thread.start()
    logger.info("InboxWatcher 守护线程已启动")
    self._thread = thread

def _run(self):
    while self._running:
        for agent_id in agent_ids:
            self._check_inbox(agent_id)
        time.sleep(2)
```

---

### 🟡 P2-3：InboxWatcher 硬编码 fallback agent 列表

**文件**: `framework/core/mesh/inbox_watcher.py`
**问题**: 注册表加载失败时静默使用硬编码列表兜底

**修复方向**：注册表加载失败应该报错，或者动态读取 `framework/data/registry.json`

---

### 🔴 P2-5：`_expectations` 字典在 Timer 回调中无锁

**文件**: `framework/core/mesh/delivery_watcher.py`
**问题**: `notify_delivered()` 在 Timer 线程中删除条目，`_check_filesystem()` 在主线程中遍历——竞态条件

**修复方向**：所有 `_expectations` 的读写加 `threading.Lock`

```python
def __init__(self, mesh_dir: str):
    self._lock = threading.Lock()
    
def notify_delivered(self, task_id, file_path):
    with self._lock:
        # ... existing logic
```

---

### 🟡 P2-6：`on_message_received` 回调缺测试

**文件**: `framework/tests/mesh/test_agent_session.py`
**问题**: AgentSession 新增了 `on_message_received` 回调但没有测试

**修复方向**：添加测试，模拟回调触发

---

### 🟡 附赠：头像 404

**文件**: `dashboard/app_enhanced.py`
**问题**: 看板页面请求 `static/avatars/` 下的头像图片返回 404。头像图片在 `agents/` 目录下。

**修复方向**：在 `_serve_static_file()` 中增加头像路径映射，或者把头像软链到 `static/avatars/`

---

做完通知毒刺审计 🦂
