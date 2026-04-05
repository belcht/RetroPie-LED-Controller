#!/bin/bash
LOG="/var/log/leds-off-shutdown.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook STARTED" >> "$LOG"

VENV_PYTHON="/home/pi/LEDControl/venv/bin/python3"
SCRIPT="/home/pi/LEDControl/LEDControl.py"
CONFIG="/home/pi/ledcontrol.toml"

# Clear LEDs - try 3 times (do not call systemctl stop — systemd handles service shutdown)
echo "$(date '+%Y-%m-%d %H:%M:%S') - Clearing LEDs" >> "$LOG"
"$VENV_PYTHON" "$SCRIPT" --animate off --config "$CONFIG" >> "$LOG" 2>&1 || true

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook FINISHED" >> "$LOG"
