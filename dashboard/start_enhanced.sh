#!/bin/bash
# start_enhanced.sh — 启动增强版 Dashboard
# 需要 FEIDA_ZOO_HOME 环境变量（默认 /home/afei/workspace/code/feida_zoo）
FEIDA_ZOO_HOME="${FEIDA_ZOO_HOME:-/home/afei/workspace/code/feida_zoo}"
cd "${FEIDA_ZOO_HOME}/dashboard"
pkill -f app_enhanced.py
sleep 1
python3 app_enhanced.py
