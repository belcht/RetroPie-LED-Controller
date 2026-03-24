#!/usr/bin/env bash
# led-game-start.sh — Called by gameStart.sh when a game launches.
#
# Batocera passes: $1=system $2=emulator $3=rom_path $4=command
#
# Kills the main LED process, then runs a game-specific animation in the
# background (based on [systems] and [roms] in ledcontrol.toml).

SYSTEM="$1"
ROM="$3"
SCRIPT="/userdata/system/LEDControl/LEDControl.py"
PID_FILE="/tmp/led-game.pid"

# Kill main LED process
if [ -f /tmp/ledcontrol.pid ]; then
    kill "$(cat /tmp/ledcontrol.pid)" 2>/dev/null || true
    sleep 0.3
    rm -f /tmp/ledcontrol.pid
fi

# Launch game animation in background
python3 "$SCRIPT" --system "$SYSTEM" --rom "$ROM" &
echo $! > "$PID_FILE"
