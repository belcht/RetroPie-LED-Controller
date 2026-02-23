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
