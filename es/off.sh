#!/usr/bin/env bash
LOG="/tmp/ledcontrol-es.log"
PYTHON="/home/pi/LEDControl/venv/bin/python3"

echo "$(date '+%Y-%m-%d %H:%M:%S') - LEDs Off" >> "$LOG"
"$PYTHON" /home/pi/LEDControl/LEDControl.py --animate off >> "$LOG" 2>&1
sudo systemctl stop ledcontrol.service >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Done" >> "$LOG"
