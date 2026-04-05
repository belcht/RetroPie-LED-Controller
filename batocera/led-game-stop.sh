#!/usr/bin/env bash
# led-game-stop.sh — Called by gameStop.sh when returning to EmulationStation.
# Restores the default animation from ledcontrol.toml via WebSocket command.

EVENT="$1"
SYSTEM="$2"

# Only handle game stop events, skip ports
[[ "$EVENT" != "gameStop" ]] && exit 0
[[ "$SYSTEM" == "ports" ]] && exit 0

python3 /userdata/system/LEDControl/led-ws-cmd.py --restore \
    --config /userdata/system/ledcontrol.toml
