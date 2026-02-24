# RetroPie-LED-Controller
Manually Control LED Lights Connected via GPIO for RetroPie Arcades
# Raspberry Pi 5 WS2812 LED Controller for RetroPie & More

This project controls WS2812/NeoPixel LED strips on a Raspberry Pi 5 using SPI (via the `rpi5-ws2812` library). It includes:
- Multiple animations (KITT scanner, glow pulse, color cycle, rainbow wave, meteor shower, twinkle sparkles)
- Configurable defaults via TOML file
- Systemd service for auto-start on boot
- Clean LED shutdown on reboot/shutdown
- RetroPie Setup menu integration for easy mode/color selection

Perfect for adding visual flair to your RetroPie cabinet, arcade machine, or any Pi project!

## Features
- Animations: KITT, Glow, Cycle, Rainbow, Meteor, Twinkle
- Solid color mode
- Persistent config in `ledcontrol.toml`
- Graceful LED shutdown on reboot
- RetroPie menu control (colors + animations)
- Runs in a virtual environment (no system pollution)

## Requirements
- Raspberry Pi 5 (tested on Bookworm)
- Raspberry Pi OS (64-bit recommended)
- WS2812 LED strip (14 LEDs in this example — adjustable in script)
- External 5V power supply (or use the 3.3v GPIO pin for short LED runs) for the strip (common GND with Pi)
- SPI enabled (`raspi-config` → Interface Options → SPI → Yes)

## Wiring
- LED Data In → Pi GPIO 10 (MOSI, physical pin 19)
- LED GND → Pi GND (any GND pin)
- LED 5V → External 5V supply (do **not** power long strips from Pi 5V pins) (short runs may be powered from 3.3v gpio pin)

Recommended: 330–470Ω resistor in series on data line + 1000µF capacitor across 5V/GND at strip start.

## Installation

The easiest way is to clone this repo and run the automated setup script:

```bash
cd /home/pi
git clone https://github.com/yourusername/rpi5-ws2812-led-control.git
cd rpi5-ws2812-led-control
sudo bash install.sh

The script will:

Create /home/pi/LEDControl/ project directory
Set up a virtual environment
Install rpi5-ws2812
Copy the main script and default config
Enable SPI (non-interactively)
Install and enable systemd services
Add the RetroPie menu module

After installation:

Edit /home/pi/ledcontrol.toml to set your default animation/color (see below)
Restart service:Bashsudo systemctl restart ledcontrol.service
Reboot to test boot behavior:Bashsudo reboot

Configuration
All persistent settings live in /home/pi/ledcontrol.toml. Example:
[general]
default_animate = "kitt"      # "kitt", "glow", "cycle", "rainbow", "meteor", "twinkle", "off", or "" for solid only
default_color = "red"

[glow]
min_brightness = 0.3
max_brightness = 1.0
duration = 2.5

[kitt]
tail_length = 6
base_speed = 0.04

[cycle]
cycle_duration = 10.0
fade_time = 1.5
fade_enabled = true

[rainbow]
speed = 0.02

[meteor]
tail_length = 8
speed = 0.05

[twinkle]
num_sparkles = 5
fade_speed = 0.04

After editing, restart the service:
Bashsudo systemctl restart ledcontrol.service
Usage

RetroPie Menu: Go to RetroPie Setup → Configuration/tools → WS2812 LED Control
Choose a color (sets solid mode) or animation (uses current color)
Manual control:Bash# Quick change helper (create this script if you want)
~/set_led.sh kitt red
~/set_led.sh rainbow
~/set_led.sh off
Immediate off (one-shot):Bash/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --animate off

Troubleshooting

LEDs stay on after reboot → Check journalctl -u leds-off.service — ensure shutdown hook ran.
No lights → Confirm SPI enabled (lsmod | grep spi), wiring, external 5V power.
Module not found → Re-run pip install rpi5-ws2812 inside venv.
Service fails → sudo systemctl status ledcontrol.service and journalctl -u ledcontrol.service -e

Credits / License
Built with help from Grok (xAI).
MIT License — feel free to fork, modify, share.
Enjoy your glowing RetroPie setup!
