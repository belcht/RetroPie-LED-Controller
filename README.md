# RetroPie LED Controller

Control WS2812/NeoPixel LED strips on a Raspberry Pi 5 via SPI — designed for arcade marquee panels and RetroPie cabinets.

## Features

- **Animations:** KITT scanner, Glow pulse, Color cycle, Rainbow wave, Meteor shower, Twinkle sparkles
- **Colors:** Red, green, blue, white, yellow, purple, cyan, orange, pink — or any hex color (`#FF8800`)
- **Solid color mode** and **off mode**
- **Global brightness limiter** (default 80%) for power management
- **Persistent config** via `ledcontrol.toml` — no need to edit the script
- **Systemd service** — auto-starts on boot, cleans up LEDs on shutdown/reboot
- **RetroPie Setup menu** integration for in-emulator control
- Runs in a Python virtual environment (no system pollution)

---

## Requirements

- Raspberry Pi 5 (tested on Raspberry Pi OS Bookworm 64-bit)
- WS2812 / NeoPixel LED strip (14 LEDs default — adjustable in config)
- SPI enabled via `raspi-config`

---

## Wiring

| LED wire | Connect to |
|---|---|
| Data In | GPIO 10 (MOSI, physical pin 19) |
| GND | Any Pi GND pin |
| 5V | External 5V supply (shared GND with Pi) |

**Recommended:** 330–470Ω resistor in series on the data line. 1000µF capacitor across 5V/GND at the strip start.

> **Powering direct from Pi:** Each WS2812 LED draws up to 60mA at full white. 14 LEDs = up to 840mA. This is within the Pi 5's headroom under normal load, but use caution — monitor temperatures before installing in a case. The 80% brightness default reduces peak draw to ~670mA.

---

## Installation

Clone the repo and run the installer:

```bash
cd /home/pi
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller
bash install.sh
```

The script will:
1. Create `/home/pi/LEDControl/` and set up a Python virtual environment
2. Install the `rpi5-ws2812` library
3. Copy `LEDControl.py`, `update_config.py`, and the default config
4. Enable SPI (non-interactively via `raspi-config`)
5. Install and enable the systemd services
6. Add the RetroPie Setup menu module

After installation:

```bash
# Edit your defaults
nano /home/pi/ledcontrol.toml

# Restart to apply
sudo systemctl restart ledcontrol.service

# Test boot behavior
sudo reboot
```

---

## Configuration

All persistent settings live in `/home/pi/ledcontrol.toml`:

```toml
[hardware]
num_leds = 14       # adjust to your strip length
spi_bus = 0
spi_device = 0

[general]
global_brightness = 0.8    # 80% max brightness (0.0–1.0)
default_animate = "kitt"   # kitt | glow | cycle | rainbow | meteor | twinkle | "" (solid)
default_color = "red"      # color name or hex e.g. "#FF8800"

[glow]
min_brightness = 0.5
max_brightness = 1.0
duration = 1.0

[kitt]
tail_length = 6
base_speed = 0.04

[cycle]
cycle_duration = 10.0
fade_time = 1.5
fade_enabled = true
# colors = ["red", "blue", "green", "purple", "orange"]  # optional subset

[rainbow]
speed = 0.02

[meteor]
tail_length = 8
speed = 0.05

[twinkle]
num_sparkles = 5
fade_speed = 0.04
```

After editing, restart the service:

```bash
sudo systemctl restart ledcontrol.service
```

---

## Usage

**RetroPie menu:** RetroPie Setup → Configuration/tools → WS2812 LED Control

**Command line:**

```bash
# Run an animation
/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --animate kitt --color red

# Solid color
/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --color white

# Hex color
/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --color '#FF8800' --animate glow

# Turn off immediately
/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --animate off
```

---

## Development (Mac → Pi workflow)

Edit files on your Mac in VSCode, then push to the Pi with:

```bash
# First time: set up SSH key auth (so no password prompt)
ssh-copy-id pi@retropie.local

# Deploy and restart service
./deploy.sh retropie.local
```

`deploy.sh` rsyncs the Python files and config, then restarts the service automatically.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| LEDs stay on after reboot | `journalctl -u leds-off.service` — did the shutdown hook run? |
| No lights at all | SPI enabled? `lsmod \| grep spi`. Check wiring and 5V supply. |
| `Module not found` error | Re-run `pip install rpi5-ws2812` inside the venv |
| Service fails to start | `sudo systemctl status ledcontrol.service` and `journalctl -u ledcontrol.service -e` |

---

## License

MIT — fork, modify, share freely.

Built with help from Grok (xAI) and Claude (Anthropic).
