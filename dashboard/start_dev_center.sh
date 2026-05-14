#!/bin/bash
# Zoo Dev-Center 启动脚本

cd "$(dirname "$0")/.."

echo "🚀 启动 Zoo Dev-Center v1.0..."

# 停止已运行的服务器
echo "🛑 停止现有服务器..."
pkill -f "app_enhanced.py" 2>/dev/null
pkill -f "app.py" 2>/dev/null
sleep 1

# 启动增强版服务器
echo "📡 启动增强版服务器 (端口: 18792)..."
nohup venv/bin/python dashboard/app_enhanced.py > dashboard/server_enhanced.log 2>&1 &

# 等待服务器启动
sleep 2

# 检查服务器状态
if curl -s http://localhost:18792/api/system-info > /dev/null 2>&1; then
    echo "✅ Zoo Dev-Center 启动成功!"
    echo ""
    echo "📊 看板地址: http://localhost:18792"
    echo "📈 API 端点:"
    echo "  - 看板数据: http://localhost:18792/api/kanban"
    echo "  - 任务统计: http://localhost:18792/api/task-stats"
    echo "  - Git时间线: http://localhost:18792/api/git-timeline"
    echo "  - 实时事件: http://localhost:18792/events"
    echo ""
    echo "🐜 由织巢蚁精心构建 | 飝龘动物园生态"
else
    echo "❌ 服务器启动失败，请检查日志: dashboard/server_enhanced.log"
    tail -20 dashboard/server_enhanced.log
fi