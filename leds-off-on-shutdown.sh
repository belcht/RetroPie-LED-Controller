#!/bin/bash
# Shutdown hook — blanks the WS2812 strip cleanly on halt/reboot.
# Stops the live service first so we don't race on SPI, then writes zeros directly.
# This script must exit quickly (TimeoutSec=10 in leds-off.service).

LOG="/var/log/leds-off-shutdown.log"
VENV_PYTHON="/home/pi/LEDControl/venv/bin/python3"
CONFIG="/home/pi/ledcontrol.toml"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook STARTED" >> "$LOG"

# Stop the running service (and any stragglers from a prior crash)
# Before touching SPI ourselves — otherwise we race on the bus.
systemctl stop ledcontrol.service 2>>"$LOG" || true
pkill -f LEDControl.py 2>>"$LOG" || true
sleep 0.3

# Blank the strip directly — no animation engine, no WebSocket, just zeros.
# Heredoc keeps this self-contained so a corrupt LEDControl.py can't break shutdown.
"$VENV_PYTHON" - <<'PY' >> "$LOG" 2>&1 || true
import tomllib
from rpi5_ws2812.ws2812 import WS2812SpiDriver, Color
try:
    with open('/home/pi/ledcontrol.toml', 'rb') as f:
        cfg = tomllib.load(f)
except Exception:
    cfg = {}
hw  = cfg.get('hardware', {})
n   = hw.get('num_leds', 14)
bus = hw.get('spi_bus', 0)
dev = hw.get('spi_device', 0)
strip = WS2812SpiDriver(spi_bus=bus, spi_device=dev, led_count=n).get_strip()
strip.set_all_pixels(Color(0, 0, 0))
strip.show()
PY

echo "$(date '+%Y-%m-%d %H:%M:%S') - Shutdown hook FINISHED" >> "$LOG"
