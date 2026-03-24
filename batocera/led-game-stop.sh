#!/usr/bin/env bash
# led-game-stop.sh — Called by gameStop.sh when returning to EmulationStation.
#
# Kills the game animation process and restarts the main LED process,
# which will pick up the default animation from ledcontrol.toml.

SCRIPT="/userdata/system/LEDControl/LEDControl.py"
PID_FILE="/tmp/led-game.pid"

# Kill the game's LED process (its finally block will clear the LEDs)
if [ -f "$PID_FILE" ]; then
    kill "$(cat $PID_FILE)" 2>/dev/null || true
    sleep 0.5
    rm -f "$PID_FILE"
fi

# Restart the main LED process (picks up default animation from TOML)
python3 "$SCRIPT" &
echo $! > /tmp/ledcontrol.pid
