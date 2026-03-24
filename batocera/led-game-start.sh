#!/usr/bin/env bash
# led-game-start.sh — Called by gameStart.sh when a game launches.
#
# Batocera passes: $1=system $2=emulator $3=rom_path $4=command
#
# Stops the main LED service, then runs a game-specific animation in the
# background (based on [systems] and [roms] in ledcontrol.toml).

SYSTEM="$1"
ROM="$3"
SCRIPT="/userdata/system/LEDControl/LEDControl.py"
PID_FILE="/tmp/led-game.pid"

# Stop main service so it doesn't conflict
batocera-services stop ledcontrol 2>/dev/null
sleep 0.3

# Launch game animation in background
python3 "$SCRIPT" --system "$SYSTEM" --rom "$ROM" &
echo $! > "$PID_FILE"
