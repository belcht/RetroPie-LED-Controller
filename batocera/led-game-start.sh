#!/usr/bin/env bash
# led-game-start.sh — Called by gameStart.sh when a game launches.
#
# Batocera passes: $1=event $2=system $3=emulator $4=rom_or_command
#
# Stops the main LED service, then runs a game-specific animation in the
# background (based on [systems] and [roms] in ledcontrol.toml).

EVENT="$1"
SYSTEM="$2"
ROM="$4"
SCRIPT="/userdata/system/LEDControl/LEDControl.py"
PID_FILE="/tmp/led-game.pid"

# Debug: log all args so we can see exactly what Batocera passes
echo "$(date) gameStart: \$1=$1 \$2=$2 \$3=$3 \$4=$4" >> /tmp/led-game.log

# Only handle game start events (Batocera calls both hooks for both events)
[[ "$EVENT" != "gameStart" ]] && exit 0

# Skip ports system (utility scripts launched from ES Ports section)
[[ "$SYSTEM" == "ports" ]] && exit 0

# Stop main service so it doesn't conflict
batocera-services stop ledcontrol 2>/dev/null
sleep 0.3

# Launch game animation in its own session with stdout closed so it doesn't
# hold the emulatorlauncher pipe open
setsid python3 "$SCRIPT" --system "$SYSTEM" --rom "$ROM" > /dev/null 2>&1 &
echo $! > "$PID_FILE"
