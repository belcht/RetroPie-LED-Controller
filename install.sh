#!/bin/bash
# install.sh — Automated setup for Raspberry Pi 5 WS2812 LED Controller
# Run as normal user: bash install.sh (prompts for sudo when needed)

set -e

echo "=== Installing WS2812 LED Controller for Raspberry Pi 5 ==="

REPO_DIR="$(pwd)"
echo "Repo directory: $REPO_DIR"

PROJECT_DIR="/home/pi/LEDControl"
OLD_ROMS_DIR="/home/pi/RetroPie/roms/ledcontrol"
PORTS_DIR="/home/pi/RetroPie/roms/ports"
PORTS_GAMELIST="/home/pi/.emulationstation/gamelists/ports/gamelist.xml"
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

# ── 7. EmulationStation — LED Control in Ports ────────────────────────────────
echo ""
echo "7. Installing LED Control into Ports..."

# Copy scripts to ports roms directory
mkdir -p "$PORTS_DIR"
cp "$REPO_DIR/es/led-control.sh" "$PORTS_DIR/"
cp "$REPO_DIR/es/led-joy2key.py" "$PORTS_DIR/"
chmod +x "$PORTS_DIR/led-control.sh" "$PORTS_DIR/led-joy2key.py"

# Copy cover art
IMAGES_DIR="$(dirname "$PORTS_GAMELIST")/images"
mkdir -p "$IMAGES_DIR"
cp "$REPO_DIR/es/images/led-control.png" "$IMAGES_DIR/"

# Add LED Control entry to ports gamelist
mkdir -p "$(dirname "$PORTS_GAMELIST")"
python3 - <<'PYEOF'
import os, re
gamelist = '/home/pi/.emulationstation/gamelists/ports/gamelist.xml'
image_abs = '/home/pi/.emulationstation/gamelists/ports/images/led-control.png'
entry = (
    '  <game>\n'
    '    <path>./led-control.sh</path>\n'
    '    <name>LED Control</name>\n'
    '    <desc>Configure WS2812 LED animations and colors for your arcade cabinet marquee. '
    'Choose from KITT scanner, glow pulse, meteor shower, twinkle sparkles, color cycle, '
    'rainbow wave, solid color, or off. Changes take effect instantly.</desc>\n'
    '    <image>' + image_abs + '</image>\n'
    '    <developer>belcht</developer>\n'
    '    <publisher>belcht</publisher>\n'
    '    <releasedate>20260101T000000</releasedate>\n'
    '    <genre>Utility</genre>\n'
    '    <players>1</players>\n'
    '    <rating>1.0</rating>\n'
    '  </game>'
)
if os.path.exists(gamelist):
    content = open(gamelist).read()
    if 'led-control' not in content:
        content = content.replace('</gameList>', entry + '\n</gameList>')
        open(gamelist, 'w').write(content)
        print('   Added LED Control to ports gamelist')
    elif image_abs not in content:
        content = re.sub(r'<game>.*?led-control\.sh.*?</game>', entry, content, flags=re.DOTALL)
        open(gamelist, 'w').write(content)
        print('   Updated LED Control gamelist entry')
    else:
        print('   LED Control already in ports gamelist — skipping')
else:
    open(gamelist, 'w').write('<?xml version="1.0"?>\n<gameList>\n' + entry + '\n</gameList>\n')
    print('   Created ports gamelist with LED Control entry')
PYEOF

# Add Ports system to es_systems.cfg if not already present
if ! grep -q "<name>ports</name>" "$ES_SYSTEMS" 2>/dev/null; then
    sudo python3 - <<'PYEOF'
import re
path = '/etc/emulationstation/es_systems.cfg'
entry = """  <system>
    <name>ports</name>
    <fullname>Ports</fullname>
    <path>/home/pi/RetroPie/roms/ports</path>
    <extension>.sh .SH</extension>
    <command>bash %ROM%</command>
    <platform>pc</platform>
    <theme>ports</theme>
  </system>"""
content = open(path).read()
content = content.replace('</systemList>', entry + '\n</systemList>')
open(path, 'w').write(content)
print('   Added Ports system to ' + path)
PYEOF
else
    echo "   Ports system already in $ES_SYSTEMS — skipping"
fi

# Remove old custom ledcontrol system from es_systems.cfg (migration cleanup)
if grep -q "<name>ledcontrol</name>" "$ES_SYSTEMS" 2>/dev/null; then
    sudo python3 -c "
import re, sys
path = '$ES_SYSTEMS'
content = open(path).read()
content = re.sub(r'\s*<system>\s*<name>ledcontrol</name>.*?</system>', '', content, flags=re.DOTALL)
open(path, 'w').write(content)
print('   Removed old ledcontrol system entry from ' + path)
"
fi

# Clean up old ledcontrol roms dir scripts (no longer used)
rm -f "$OLD_ROMS_DIR/set-animation.sh" "$OLD_ROMS_DIR/set-color.sh" \
      "$OLD_ROMS_DIR/off.sh" "$OLD_ROMS_DIR/led-joy2key.py"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit /home/pi/ledcontrol.toml to set your defaults and per-system animations"
echo "  2. Restart EmulationStation — LED Control appears under Ports"
echo "  3. Reboot to test boot behavior: sudo reboot"
echo ""
echo "Quick test:"
echo "  $PYTHON $PROJECT_DIR/LEDControl.py --animate kitt --color red"
