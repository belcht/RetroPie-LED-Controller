#!/bin/bash
# install.sh — Automated setup for Raspberry Pi 5 WS2812 LED Controller
# Run as normal user: bash install.sh (prompts for sudo when needed)

set -e

echo "=== Installing WS2812 LED Controller for Raspberry Pi 5 ==="

REPO_DIR="$(pwd)"
echo "Repo directory: $REPO_DIR"

PROJECT_DIR="/home/pi/LEDControl"
ROMS_DIR="/home/pi/RetroPie/roms/ledcontrol"
ES_GAMELISTS="/home/pi/.emulationstation/gamelists/ledcontrol"
ES_SYSTEMS="/etc/emulationstation/es_systems.cfg"
RUNCOMMAND_DIR="/opt/retropie/configs/all"
PYTHON="$PROJECT_DIR/venv/bin/python3"

# ── 1. Project directory & venv ───────────────────────────────────────────────
echo ""
echo "1. Setting up project directory and virtual environment..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install rpi5-ws2812 -q
deactivate

# ── 2. Copy Python scripts ────────────────────────────────────────────────────
echo ""
echo "2. Copying scripts..."
cp "$REPO_DIR/LEDControl.py"     "$PROJECT_DIR/"
cp "$REPO_DIR/update_config.py"  "$PROJECT_DIR/"
cp "$REPO_DIR/led-game-start.sh" "$PROJECT_DIR/"
cp "$REPO_DIR/led-game-end.sh"   "$PROJECT_DIR/"
chmod +x "$PROJECT_DIR/led-game-start.sh" "$PROJECT_DIR/led-game-end.sh"

# Copy config only if it doesn't already exist (preserve user customizations)
if [ ! -f "/home/pi/ledcontrol.toml" ]; then
    cp "$REPO_DIR/ledcontrol.toml" /home/pi/
    echo "   Copied default ledcontrol.toml to /home/pi/"
else
    echo "   /home/pi/ledcontrol.toml already exists — skipping (edit manually to add new sections)"
fi

# ── 3. Enable SPI ─────────────────────────────────────────────────────────────
echo ""
echo "3. Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# ── 4. Systemd services ───────────────────────────────────────────────────────
echo ""
echo "4. Installing systemd services..."
sudo cp "$REPO_DIR/ledcontrol.service"        /etc/systemd/system/
sudo cp "$REPO_DIR/leds-off.service"          /etc/systemd/system/
sudo cp "$REPO_DIR/leds-off-on-shutdown.sh"   /usr/local/bin/
sudo chmod +x /usr/local/bin/leds-off-on-shutdown.sh

# Allow pi to control the LED service without a password prompt
echo "pi ALL=(ALL) NOPASSWD: /bin/systemctl start ledcontrol.service, /bin/systemctl stop ledcontrol.service, /bin/systemctl restart ledcontrol.service" \
    | sudo tee /etc/sudoers.d/ledcontrol > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable ledcontrol.service
sudo systemctl enable leds-off.service
sudo systemctl start ledcontrol.service

# ── 5. RetroPie Setup menu module ─────────────────────────────────────────────
echo ""
echo "5. Installing RetroPie Setup menu module..."
sudo mkdir -p ~/RetroPie-Setup/scriptmodules/supplementary/
sudo cp "$REPO_DIR/ledcontrol.sh" ~/RetroPie-Setup/scriptmodules/supplementary/
sudo chmod +x ~/RetroPie-Setup/scriptmodules/supplementary/ledcontrol.sh

# ── 6. RunCommand hooks ───────────────────────────────────────────────────────
echo ""
echo "6. Installing runcommand hooks..."

_install_hook() {
    local hook_file="$1"
    local hook_call="$2"

    if [ -f "$hook_file" ]; then
        if grep -q "LEDControl" "$hook_file" 2>/dev/null; then
            echo "   $hook_file already has LED hook — skipping"
        else
            echo "" >> "$hook_file"
            echo "# LED Controller hook" >> "$hook_file"
            echo "$hook_call" >> "$hook_file"
            echo "   Appended LED hook to $hook_file"
        fi
    else
        printf '#!/usr/bin/env bash\n# LED Controller hook\n%s\n' "$hook_call" > "$hook_file"
        chmod +x "$hook_file"
        echo "   Created $hook_file"
    fi
}

_install_hook "$RUNCOMMAND_DIR/runcommand-onstart.sh" \
    "/home/pi/LEDControl/led-game-start.sh \"\$@\""

_install_hook "$RUNCOMMAND_DIR/runcommand-onend.sh" \
    "/home/pi/LEDControl/led-game-end.sh \"\$@\""

# ── 7. EmulationStation system (LED Control in the carousel) ──────────────────
echo ""
echo "7. Setting up EmulationStation LED Control system..."

# Create ROMs directory and copy launcher scripts from repo
mkdir -p "$ROMS_DIR"
cp "$REPO_DIR/es/set-animation.sh" "$ROMS_DIR/"
cp "$REPO_DIR/es/set-color.sh"     "$ROMS_DIR/"
cp "$REPO_DIR/es/off.sh"           "$ROMS_DIR/"
chmod +x "$ROMS_DIR/set-animation.sh" "$ROMS_DIR/set-color.sh" "$ROMS_DIR/off.sh"
# Ensure pi owns the roms directory (in case install ran as root)
sudo chown -R pi:pi "$ROMS_DIR"

# Remove old preset scripts if present from a previous install
rm -f "$ROMS_DIR/kitt-"*.sh "$ROMS_DIR/glow-"*.sh "$ROMS_DIR/meteor-"*.sh \
      "$ROMS_DIR/twinkle-"*.sh "$ROMS_DIR/rainbow.sh" "$ROMS_DIR/cycle.sh" \
      "$ROMS_DIR/solid-"*.sh

# Copy gamelist
mkdir -p "$ES_GAMELISTS"
cp "$REPO_DIR/es/gamelist.xml" "$ES_GAMELISTS/"

# Add LED Control to es_systems.cfg if not already present
if ! grep -q "<name>ledcontrol</name>" "$ES_SYSTEMS" 2>/dev/null; then
    sudo sed -i 's|</systemList>|  <system>\n    <name>ledcontrol</name>\n    <fullname>LED Control</fullname>\n    <path>'"$ROMS_DIR"'</path>\n    <extension>.sh</extension>\n    <command>bash %ROM%</command>\n    <platform></platform>\n    <theme>carbon</theme>\n  </system>\n</systemList>|' "$ES_SYSTEMS"
    echo "   Added LED Control to $ES_SYSTEMS"
else
    echo "   LED Control already in $ES_SYSTEMS — skipping"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit /home/pi/ledcontrol.toml to set your defaults and per-system animations"
echo "  2. Restart EmulationStation to see the LED Control system in the carousel"
echo "  3. Reboot to test boot behavior: sudo reboot"
echo ""
echo "Quick test:"
echo "  $PYTHON $PROJECT_DIR/LEDControl.py --animate kitt --color red"
