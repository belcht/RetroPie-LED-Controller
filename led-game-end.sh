#!/usr/bin/env bash
# led-game-end.sh — Called by runcommand-onend.sh when returning to EmulationStation.
#
# Kills the game animation process and restores the main LED service,
# which will pick up the default animation from ledcontrol.toml.

PID_FILE="/tmp/led-game.pid"

# Kill the game's LED process cleanly
if [ -f "$PID_FILE" ]; then
    LED_PID=$(cat "$PID_FILE")
    kill "$LED_PID" 2>/dev/null
    # Give it a moment to clean up (it will turn off LEDs via finally block)
    sleep 0.5
    rm -f "$PID_FILE"
fi

# Restart the main service (uses TOML default animation)
sudo systemctl start ledcontrol.service
