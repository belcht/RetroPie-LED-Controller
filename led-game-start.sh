#!/usr/bin/env bash
# led-game-start.sh — Called by runcommand-onstart.sh when a game launches.
# RetroPie passes: $1=system $2=emulator $3=rom_path $4=command
# Sends a WebSocket command to the running LEDControl service — no stop/start needed.

python3 /home/pi/LEDControl/led-ws-cmd.py --system "$1" --rom "$3" \
    --config /home/pi/ledcontrol.toml
