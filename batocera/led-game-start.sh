#!/usr/bin/env bash
# led-game-start.sh — Called by gameStart.sh when a game launches.
# Batocera passes: $1=event $2=system $3=emulator $4=rom_or_command
# Sends a WebSocket command to the running LEDControl service — no stop/start needed.

EVENT="$1"
SYSTEM="$2"
ROM="$4"

# Only handle game start events
[[ "$EVENT" != "gameStart" ]] && exit 0

# Skip ports (utility scripts launched from ES Ports section)
[[ "$SYSTEM" == "ports" ]] && exit 0

python3 /userdata/system/LEDControl/led-ws-cmd.py --system "$SYSTEM" --rom "$ROM" \
    --config /userdata/system/ledcontrol.toml
