#!/usr/bin/env bash
# led-game-end.sh — Called by runcommand-onend.sh when returning to EmulationStation.
# Restores the default animation from ledcontrol.toml via WebSocket command.

python3 /home/pi/LEDControl/led-ws-cmd.py --restore \
    --config /home/pi/ledcontrol.toml
