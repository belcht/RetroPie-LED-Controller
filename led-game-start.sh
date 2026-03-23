#!/usr/bin/env bash
# led-game-start.sh — Called by runcommand-onstart.sh when a game launches.
#
# RetroPie passes: $1=system $2=emulator $3=rom_path $4=command
#
# Stops the main LED service, then runs a game-specific animation in the
# background (based on [systems] and [roms] in ledcontrol.toml).
# The PID is saved so led-game-end.sh can clean it up.

SYSTEM="$1"
ROM="$3"
PYTHON="/home/pi/LEDControl/venv/bin/python3"
SCRIPT="/home/pi/LEDControl/LEDControl.py"
PID_FILE="/tmp/led-game.pid"

# Stop main service so it doesn't conflict
sudo systemctl stop ledcontrol.service 2>/dev/null
sleep 0.3

# Launch game animation in background
"$PYTHON" "$SCRIPT" --system "$SYSTEM" --rom "$ROM" &
echo $! > "$PID_FILE"
