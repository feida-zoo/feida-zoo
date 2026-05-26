# ZooMesh Daemon 热重载指南

> 适用场景：修改 `framework/core/mesh/zoo_mesh_daemon.py` 或相关模块后，需要让运行中的 daemon 加载新代码。

## ⚠️ 核心陷阱

**网关重启 ≠ daemon 重启**

- `gateway restart` 只重启 **Node.js gateway 进程**
- ZooMesh daemon 是 **gateway-start hook 拉起的独立 Python 子进程**
- Python 模块 `import` 后缓存在 `sys.modules`，**进程生命周期内不会自动重新加载修改后的源码**

## ✅ 正确步骤

### 1. 定位 daemon 进程

```bash
# 方法 A：通过端口
lsof -t -i :18793

# 方法 B：通过进程名
ps aux | grep "zoo_mesh_daemon.py" | grep -v grep
```

### 2. Kill 旧进程

```bash
kill $(lsof -t -i :18793)
# 或
kill <PID>
```

### 3. 等待 plugin 自动拉起（约 5-10 秒）

plugin 的 crash 重启机制：
- daemon 异常退出 → plugin 检测到 → 5 秒后自动 `spawn` 新进程
- 最大重试 5 次，连续崩溃则停止

### 4. 验证新进程已启动

```bash
lsof -i :18793 | head -3
curl -s http://127.0.0.1:18793/health
```

### 5. 验证新代码已加载

```bash
# 测试 already_done 逻辑（对已完成的 pipeline）
curl -s -X POST http://127.0.0.1:18793/phase_complete \
  -H 'Content-Type: application/json' \
  -d '{"pipeline_id":"pl_xxx","result":"pass","agent_id":"test"}'
# 期望返回：{"status": "already_done", ...}
```

## ❌ 错误做法

| 做法 | 为什么错 |
|------|---------|
| `gateway restart` | 只重启 gateway，daemon 子进程仍在跑旧代码 |
| 修改 `.py` 文件后等 | Python 不会自动重新加载已 import 的模块 |
| 直接 `python3 zoo_mesh_daemon.py` | 可能跟 plugin 拉起的进程冲突（端口占用） |

## 🔧 自动化方案（可选）

在 deliver/final_check 阶段，如果修改了 daemon 代码，可以：

```bash
# 写入 deliver.md 后执行
kill $(lsof -t -i :18793) && sleep 8 && curl -s http://127.0.0.1:18793/health
```

## 📁 相关文件

- daemon 源码：`framework/core/mesh/zoo_mesh_daemon.py`
- plugin 启动逻辑：`plugins/zoo-pipeline/src/hooks/gateway-start.ts`
- daemon 日志：`/tmp/zoo_mesh_daemon.log`（手动启动时）
- plugin 日志：gateway stdout（通过 `openclaw logs` 查看）
