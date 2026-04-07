#!/bin/bash
cd /home/afei/workspace/code/feida_zoo/dashboard
pkill -f app_enhanced.py
sleep 1
python3 app_enhanced.py
