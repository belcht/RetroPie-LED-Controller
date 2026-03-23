# RetroPie LED Controller

Control WS2812/NeoPixel LED strips on a Raspberry Pi 5 via SPI — designed for arcade marquee panels and RetroPie cabinets.

![LED Control](es/images/led-control.png)

---

## Features

- **Animations:** KITT scanner, Glow pulse, Meteor shower, Twinkle sparkles, Color cycle, Rainbow wave, Solid color, Off
- **Colors:** Red, orange, yellow, green, cyan, blue, purple, pink, white — or any hex value (`#FF8800`)
- **Per-system animations** — different LEDs for MAME, NES, SNES, and more (configured in TOML)
- **Per-ROM overrides** — specific games can have their own animation and color
- **EmulationStation Ports menu** — change animation and color from inside ES using a joystick-navigable dialog menu
- **Persistent config** via `ledcontrol.toml` — no script editing needed
- **Systemd service** — auto-starts on boot, cleans up LEDs on shutdown and reboot
- **Global brightness limiter** (default 80%) for power management
- Runs in a Python virtual environment (no system pollution)

---

## Requirements

- Raspberry Pi 5 (tested on Raspberry Pi OS Bookworm 64-bit)
- WS2812 / NeoPixel LED strip
- SPI enabled (the installer handles this)

---

## Wiring

| LED wire | Connect to |
|---|---|
| Data In | GPIO 10 (MOSI, physical pin 19) |
| GND | Any Pi GND pin |
| 5V | External 5V supply (shared GND with Pi) |

**Recommended:** 330–470Ω resistor in series on the data line. 1000µF capacitor across 5V/GND at the strip start.

> Each WS2812 LED draws up to 60mA at full white. Power from an external 5V supply for strips longer than a few LEDs. The 80% brightness default helps manage peak draw.

---

## Installation

```bash
cd /home/pi
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller
bash install.sh
```

The installer handles everything:

1. Creates `/home/pi/LEDControl/` with a Python virtual environment
2. Installs the `rpi5-ws2812` library
3. Copies scripts and default config
4. Enables SPI
5. Installs and enables systemd services (auto-start + clean shutdown)
6. Installs the RetroPie Setup menu module
7. Installs RunCommand hooks for per-game LED reactions
8. Adds **LED Control** to the EmulationStation Ports menu with cover art
9. Adds the Ports system to `es_systems.cfg` if not already present

Restart EmulationStation after installation. LED Control will appear under Ports.

---

## Configuration

All settings live in `/home/pi/ledcontrol.toml`:

```toml
[hardware]
num_leds = 14       # number of LEDs in your strip
spi_bus = 0
spi_device = 0

[general]
global_brightness = 0.8    # 0.0–1.0
default_animate = "kitt"   # kitt | glow | meteor | twinkle | cycle | rainbow | "" (solid) | off
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
# colors = ["red", "blue", "green", "purple"]  # optional subset

[rainbow]
speed = 0.02

[meteor]
tail_length = 8
speed = 0.05

[twinkle]
num_sparkles = 5
fade_speed = 0.04

# Per-system animations — system name matches the RetroPie system folder name
[systems]
default   = { animate = "kitt",    color = "red" }
arcade    = { animate = "kitt",    color = "red" }
nes       = { animate = "glow",    color = "white" }
snes      = { animate = "glow",    color = "purple" }
megadrive = { animate = "meteor",  color = "blue" }
n64       = { animate = "rainbow" }
psx       = { animate = "glow",    color = "cyan" }

# Per-ROM overrides (ROM name without extension)
[roms]
# "Street Fighter II" = { animate = "kitt", color = "red" }
```

After editing, restart the service:

```bash
sudo systemctl restart ledcontrol.service
```

---

## EmulationStation Ports Menu

LED Control appears in the **Ports** section of EmulationStation. Launch it to get a menu with:

- **Set Animation** — choose from all available animations
- **Set Color** — choose from 9 colors
- **LEDs Off** — stop the service immediately
- **Exit** — return to EmulationStation

Fully navigable with a joystick. Changes take effect immediately.

---

## Per-Game LED Reactions

When a game launches, the LED service automatically switches to the animation and color configured for that system (or ROM) in `ledcontrol.toml`. When the game exits, the default animation resumes.

Add entries under `[systems]` using the RetroPie system folder name, or under `[roms]` for specific game titles.

---

## Command Line

```bash
PYTHON=/home/pi/LEDControl/venv/bin/python3
LED=/home/pi/LEDControl/LEDControl.py

# Run an animation
$PYTHON $LED --animate kitt --color red

# Solid color
$PYTHON $LED --color white

# Hex color
$PYTHON $LED --color '#FF8800' --animate glow

# Turn off
$PYTHON $LED --animate off
```

---

## Mac → Pi Development Workflow

```bash
# First time: set up SSH key auth
ssh-copy-id pi@retropie.local

# Deploy changes and restart service
./deploy.sh retropie.local
```

`deploy.sh` rsyncs all scripts, config, and cover art to the Pi, then restarts the LED service.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| LEDs stay on after reboot | `journalctl -u leds-off.service` |
| No LEDs at all | SPI enabled? `lsmod \| grep spi`. Check wiring and 5V supply. |
| `Module not found` error | `pip install rpi5-ws2812` inside the venv |
| Service won't start | `sudo systemctl status ledcontrol.service` and `journalctl -u ledcontrol.service -e` |
| ES Ports menu not appearing | Check `grep ports /etc/emulationstation/es_systems.cfg` — re-run `bash install.sh` if missing |
| Joystick double-steps in menu | A system joy2key may still be running — reboot and try again |

---

## License

MIT — fork, modify, share freely.
