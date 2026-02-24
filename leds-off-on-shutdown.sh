#!/bin/bash
LOG="/var/log/leds-off-shutdown.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook STARTED" >> "$LOG"

VENV_PYTHON="/home/pi/LEDControl/venv/bin/python3"
SCRIPT="/home/pi/LEDControl/LEDControl.py"

# Stop the main service first (if running)
systemctl stop ledcontrol.service 2>>"$LOG"

# Clear LEDs - try 3 times
for attempt in {1..3}; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Clear attempt $attempt" >> "$LOG"
    "$VENV_PYTHON" "$SCRIPT" --animate off >> "$LOG" 2>&1
    sleep 0.1
done

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook FINISHED" >> "$LOG"
