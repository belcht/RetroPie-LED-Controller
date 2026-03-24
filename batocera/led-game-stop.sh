#!/usr/bin/env bash
# led-game-stop.sh — Called by gameStop.sh when returning to EmulationStation.
#
# Kills the game animation process and restarts the main LED service,
# which will pick up the default animation from ledcontrol.toml.

EVENT="$1"
SYSTEM="$2"
PID_FILE="/tmp/led-game.pid"

# Only handle game stop events, skip ports (utility scripts)
[[ "$EVENT" != "gameStop" ]] && exit 0
[[ "$SYSTEM" == "ports" ]] && exit 0

# Kill the game's LED process (its finally block will clear the LEDs)
if [ -f "$PID_FILE" ]; then
    kill "$(cat $PID_FILE)" 2>/dev/null || true
    sleep 0.5
    rm -f "$PID_FILE"
fi

# Restart the main service (picks up default animation from TOML)
batocera-services start ledcontrol
