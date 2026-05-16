"""
测试: 动物园仪表盘自启动
test_pl_18083bdc_dashboard_autostart

测试场景:
1. Gateway 启动时 Dashboard 进程自动启动
2. Gateway 重启后 Dashboard 自动恢复
3. Dashboard 端口冲突时优雅降级
"""
import subprocess
import time
import requests

DASHBOARD_PORT = 18792
DASHBOARD_SCRIPT = "dashboard/app_enhanced.py"
VENV_PYTHON = "/Users/zoo/workspace/code/feida_zoo/venv/bin/python"


def test_dashboard_starts_on_gateway_start():
    """Gateway 启动后 Dashboard 进程应存在"""
    result = subprocess.run(
        ["pgrep", "-f", "app_enhanced.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Dashboard 进程不存在"
    assert result.stdout.strip(), "无进程 PID"


def test_dashboard_health_ok():
    """Dashboard HTTP 端口响应健康检查"""
    resp = requests.get(f"http://127.0.0.1:{DASHBOARD_PORT}/api/task-stats", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_tasks" in data


def test_dashboard_recovers_after_crash():
    """Dashboard 崩溃后自动重启（TODO: pipeline 接入后验证）"""
    pass  # 接入 pipeline 的 crash auto-restart 机制后补充


def test_dashboard_port_conflict_graceful():
    """端口冲突时不崩溃，打日志降级"""
    pass  # 实现时补充
