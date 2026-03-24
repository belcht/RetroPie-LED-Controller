# RetroPie / Batocera LED Controller

Control WS2812/NeoPixel LED strips on a Raspberry Pi 5 via SPI — designed for arcade marquee panels.
Supports both **RetroPie** and **Batocera** from a single repository.

![LED Control](es/images/led-control.png)

---

## Features

- **Animations:** KITT scanner, Cylon eye, Glow pulse, Center pulse, Meteor shower, Twinkle sparkles, Color cycle, Rainbow wave, Solid color, Off
- **Colors:** Red, orange, yellow, green, cyan, blue, purple, pink, white — or any hex value (`#FF8800`)
- **Per-system animations** — different LEDs for MAME, NES, SNES, and more (configured in TOML)
- **Per-ROM overrides** — specific games can have their own animation and color
- **EmulationStation Ports menu** — change animation and color from inside ES using a joystick-navigable dialog menu
- **Persistent config** via `ledcontrol.toml` — no script editing needed
- **Auto-starts on boot**, cleans up LEDs on shutdown
- **Global brightness limiter** (default 80%) for power management

---

## Requirements

| | RetroPie | Batocera |
|---|---|---|
| Hardware | Raspberry Pi 5 | Raspberry Pi 5 |
| OS | Raspberry Pi OS Bookworm 64-bit | Batocera v40+ |
| Python library | `rpi5-ws2812` | `adafruit-blinka` + `adafruit-circuitpython-neopixel-spi` |
| Service manager | systemd | batocera-services |

---

## Wiring

| LED wire | Connect to |
|---|---|
| Data In | GPIO 10 (MOSI, physical pin 19) |
| GND | Any Pi GND pin |
| 5V | External 5V supply (shared GND with Pi) |

**Recommended:** 330–470Ω resistor in series on the data line. 1000µF capacitor across 5V/GND at the strip start.

### Power Math

Each WS2812 LED draws up to **60mA at full white**. At the default 80% brightness cap, that drops to ~48mA per LED.

| LEDs | Peak current (80% brightness) | Notes |
|------|-------------------------------|-------|
| 10   | ~480mA | Fine on Pi 5V rail with a good supply |
| 14   | ~672mA | Default strip size in this project |
| 20   | ~960mA | Safe limit when sharing the Pi's supply |
| 30   | ~1440mA | Requires a dedicated external 5V supply |

The script enforces a **default maximum of 20 LEDs** (`MAX_LEDS = 20`). To raise it, edit `LEDControl.py` and `ledcontrol.toml`, and use a dedicated external 5V supply with a shared GND.

---

## Installation — RetroPie

SSH into your Pi and run:

```bash
cd ~
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller
bash install.sh
```

The installer:
1. Creates `/home/pi/LEDControl/` with a Python virtual environment
2. Installs the `rpi5-ws2812` library
3. Enables SPI
4. Installs and enables systemd services (auto-start + clean shutdown)
5. Installs the RetroPie Setup menu module
6. Installs RunCommand hooks for per-game LED reactions
7. Adds **LED Control** to the EmulationStation Ports menu with cover art

Restart EmulationStation after installation.

---

## Installation — Batocera

Batocera does not include `git`. Choose one of the methods below.

### Option A — Install directly on the Batocera machine (any OS)

SSH into Batocera and run these commands:

```bash
ssh root@bat1.local
cd /tmp
wget https://github.com/belcht/RetroPie-LED-Controller/archive/refs/heads/main.zip -O led.zip
unzip led.zip
cd RetroPie-LED-Controller-main
bash batocera/install.sh
```

> **Windows users:** PowerShell and Command Prompt on Windows 10/11 both include a built-in SSH client.
> Open PowerShell and run `ssh root@bat1.local` — no extra software needed.

### Option B — Deploy from Mac/Linux (rsync)

For iterative development from a Mac or Linux machine:

```bash
# First time: set up passwordless SSH
ssh-keygen -t ed25519    # skip if you already have a key
ssh-copy-id root@bat1.local

# Clone the repo on your Mac/Linux machine
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller

# Deploy and restart the LED service
./deploy-batocera.sh             # default: root@bat1.local
./deploy-batocera.sh 192.168.1.x # or use an IP address
```

### Option C — Copy files from Windows via network share

Batocera shares its storage over the local network. From Windows Explorer:

1. Open `\\bat1.local` (or `\\<your-batocera-ip>`) in File Explorer
2. Navigate to `share\system\`
3. Copy the `batocera/` folder contents to `share\system\LEDControl\`

Then SSH in and run the install script:

```
ssh root@bat1.local "bash /userdata/system/LEDControl/install.sh"
```

> **Tip:** If `bat1.local` doesn't resolve on Windows, use the Batocera machine's IP address instead.
> Find it under Batocera → Network Settings, or check your router's DHCP table.

### After Batocera installation

Restart EmulationStation. **LED Control** will appear in the Ports section with cover art.

---

## Configuration

### RetroPie — `/home/pi/ledcontrol.toml`
### Batocera — `/userdata/system/ledcontrol.toml`

```toml
[hardware]
num_leds = 14       # number of LEDs in your strip
spi_bus = 0
spi_device = 0

[general]
global_brightness = 0.8    # 0.0–1.0
default_animate = "kitt"   # see animations list below
default_color = "red"      # color name or hex e.g. "#FF8800"

[glow]
min_brightness = 0.5
max_brightness = 1.0
duration = 1.0

[kitt]
tail_length = 6
base_speed = 0.04

[cylon]
speed = 0.03
min_stare = 0.4
max_stare = 1.2

[centerpulse]            # Batocera only
base_speed = 0.04
pause_at_full = 0.2

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

# Per-system animations — use the system folder name (RetroPie) or system name (Batocera)
[systems]
default   = { animate = "kitt",    color = "red" }
arcade    = { animate = "kitt",    color = "red" }
nes       = { animate = "glow",    color = "white" }
snes      = { animate = "glow",    color = "purple" }
megadrive = { animate = "meteor",  color = "blue" }
n64       = { animate = "rainbow" }
psx       = { animate = "glow",    color = "cyan" }

# Per-ROM overrides (ROM filename without extension)
[roms]
# "Street Fighter II" = { animate = "kitt", color = "red" }
```

### Animations

| Name | Description |
|---|---|
| `kitt` | KITT scanner — single dot bouncing left/right with tail |
| `cylon` | Cylon eye — wider eye with roaming stare pause at each end |
| `glow` | Breathing pulse — full strip fades in and out |
| `centerpulse` | Expands from center outward, then collapses |
| `meteor` | Meteor shower — streaks falling across the strip |
| `twinkle` | Random sparkles fading in and out |
| `cycle` | Slow cross-fade through all colors (or a custom list) |
| `rainbow` | Rainbow wave scrolling across the strip |
| `""` | Solid color — no animation |
| `off` | LEDs off |

### Restart the service after editing config

**RetroPie:**
```bash
sudo systemctl restart ledcontrol.service
```

**Batocera:**
```bash
batocera-services stop ledcontrol
batocera-services start ledcontrol
```

---

## EmulationStation Ports Menu

**LED Control** appears in the Ports section of EmulationStation. Launch it for a joystick-navigable menu:

- **Set Animation** — choose from all available animations
- **Set Color** — choose from 9 colors
- **LEDs Off** — stop the service immediately
- **Exit** — return to EmulationStation

Changes take effect immediately.

---

## Per-Game LED Reactions

When a game launches, the LED service automatically switches to the animation configured for that system (or ROM) in `ledcontrol.toml`. When the game exits, the default animation resumes.

Add entries under `[systems]` using the system name, or under `[roms]` for specific game titles.

---

## Command Line

**RetroPie:**
```bash
PYTHON=/home/pi/LEDControl/venv/bin/python3
LED=/home/pi/LEDControl/LEDControl.py
$PYTHON $LED --animate kitt --color red
$PYTHON $LED --color '#FF8800' --animate glow
$PYTHON $LED --animate off
```

**Batocera:**
```bash
python3 /userdata/system/LEDControl/LEDControl.py --animate kitt --color red
python3 /userdata/system/LEDControl/LEDControl.py --color '#FF8800' --animate glow
python3 /userdata/system/LEDControl/LEDControl.py --animate off
```

---

## Troubleshooting

### RetroPie

| Symptom | Check |
|---|---|
| LEDs stay on after reboot | `journalctl -u leds-off.service` |
| No LEDs at all | SPI enabled? `lsmod \| grep spi`. Check wiring and 5V supply. |
| `Module not found` error | Activate venv and run `pip install rpi5-ws2812` |
| Service won't start | `sudo systemctl status ledcontrol.service` |
| ES Ports menu not appearing | `grep ports /etc/emulationstation/es_systems.cfg` — re-run `bash install.sh` if missing |

### Batocera

| Symptom | Check |
|---|---|
| No LEDs at all | SPI enabled? Check `/userdata/system/config.txt` for `dtparam=spi=on` — reboot required after adding |
| Service won't start | `batocera-services start ledcontrol` in SSH — check for Python errors |
| Two LED animations running | Stale second service instance — `batocera-services stop ledcontrol` twice, then start once |
| ES Ports menu not appearing | Check `/userdata/system/configs/emulationstation/gamelists/ports/gamelist.xml` exists |
| ES stuck on loading screen after playing a game | SSH in and run `batocera-services stop ledcontrol; batocera-services start ledcontrol` — then reboot |
| Joystick not working in LED Control menu | Check `/dev/input/js0` exists. Reboot and try again. |

---

## Repository Layout

```
RetroPie-LED-Controller/
├── install.sh                  # RetroPie installer
├── LEDControl.py               # RetroPie LED controller
├── update_config.py            # TOML updater (shared)
├── ledcontrol.toml             # Default config (shared)
├── ledcontrol.service          # RetroPie systemd service
├── leds-off.service            # RetroPie shutdown service
├── leds-off-on-shutdown.sh     # RetroPie shutdown hook
├── ledcontrol.sh               # RetroPie Setup menu module
├── deploy.sh                   # Mac/Linux → RetroPie rsync deploy
├── deploy-batocera.sh          # Mac/Linux → Batocera rsync deploy
├── es/
│   ├── led-control.sh          # RetroPie ES Ports menu script
│   ├── led-joy2key.py          # Joystick→keyboard daemon (RetroPie)
│   └── images/
│       └── led-control.png     # Cover art (shared)
└── batocera/
    ├── install.sh              # Batocera installer
    ├── LEDControl.py           # Batocera LED controller (neopixel_spi)
    ├── ledcontrol-service      # batocera-services script
    ├── led-game-start.sh       # Batocera game start hook
    ├── led-game-stop.sh        # Batocera game stop hook
    └── es/
        ├── led-control.sh      # Batocera ES Ports menu script
        └── led-joy2key.py      # Joystick→keyboard daemon (Batocera)
```

---

## License

MIT — fork, modify, share freely.
