#!/bin/bash
# install.sh — Automated setup for Raspberry Pi 5 WS2812 LED Controller
# Run as normal user: bash install.sh (prompts for sudo when needed)

set -e

echo "=== Installing WS2812 LED Controller for Raspberry Pi 5 ==="

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Repo directory: $REPO_DIR"

PROJECT_DIR="/home/pi/LEDControl"
RETRO_LED_DIR="$PROJECT_DIR/retro-led"
PORTS_DIR="/home/pi/RetroPie/roms/ports"
PORTS_GAMELIST="/home/pi/.emulationstation/gamelists/ports/gamelist.xml"
PORTS_IMAGES_DIR="$(dirname "$PORTS_GAMELIST")/images"
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

# ── 2. Copy / overwrite all scripts ──────────────────────────────────────────
echo ""
echo "2. Copying scripts (overwriting existing)..."
if [ "$REPO_DIR" != "$PROJECT_DIR" ]; then
    cp -f "$REPO_DIR/LEDControl.py"     "$PROJECT_DIR/"
    cp -f "$REPO_DIR/update_config.py"  "$PROJECT_DIR/"
    cp -f "$REPO_DIR/led-game-start.sh" "$PROJECT_DIR/"
    cp -f "$REPO_DIR/led-game-end.sh"   "$PROJECT_DIR/"
    cp -f "$REPO_DIR/led-ws-cmd.py"     "$PROJECT_DIR/"
    echo "   Scripts copied"
else
    echo "   Scripts already in place (deployed via rsync)"
fi
chmod +x "$PROJECT_DIR/led-game-start.sh" "$PROJECT_DIR/led-game-end.sh" "$PROJECT_DIR/led-ws-cmd.py"

# Copy config — only if not already present (preserve user customizations)
if [ ! -f "/home/pi/ledcontrol.toml" ]; then
    cp "$REPO_DIR/ledcontrol.toml" /home/pi/
    echo "   Copied default ledcontrol.toml to /home/pi/"
else
    echo "   /home/pi/ledcontrol.toml already exists — preserving (edit manually to add new sections)"
fi

# ── 3. RetroLED — copy with vendored websockets ───────────────────────────────
echo ""
echo "3. Installing RetroLED..."
mkdir -p "$RETRO_LED_DIR/assets/images"
mkdir -p "$RETRO_LED_DIR/vendor"

if [ "$REPO_DIR" != "$PROJECT_DIR" ]; then
    cp -f "$REPO_DIR/retro-led/retro-led.py" "$RETRO_LED_DIR/"
    cp -rf "$REPO_DIR/retro-led/vendor/."    "$RETRO_LED_DIR/vendor/"
    cp -rf "$REPO_DIR/retro-led/assets/."   "$RETRO_LED_DIR/assets/"
    echo "   RetroLED files copied"
else
    echo "   RetroLED files already in place (deployed via rsync)"
fi
chmod +x "$RETRO_LED_DIR/retro-led.py"

# Download Press Start 2P font if not already present
FONT_PATH="$RETRO_LED_DIR/assets/PressStart2P.ttf"
if [ ! -f "$FONT_PATH" ]; then
    echo "   Downloading Press Start 2P font..."
    curl -fsSL \
        "https://github.com/google/fonts/raw/main/ofl/pressstart2p/PressStart2P-Regular.ttf" \
        -o "$FONT_PATH" 2>/dev/null && echo "   Font downloaded." || \
        echo "   Font download failed — will use fallback monospace font"
fi

# ── 4. Enable SPI ─────────────────────────────────────────────────────────────
echo ""
echo "4. Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# ── 5. Systemd services ───────────────────────────────────────────────────────
echo ""
echo "5. Installing systemd services..."
sudo cp -f "$REPO_DIR/ledcontrol.service"        /etc/systemd/system/
sudo cp -f "$REPO_DIR/leds-off.service"          /etc/systemd/system/
sudo cp -f "$REPO_DIR/leds-off-on-shutdown.sh"   /usr/local/bin/
sudo chmod +x /usr/local/bin/leds-off-on-shutdown.sh

echo "pi ALL=(ALL) NOPASSWD: /bin/systemctl start ledcontrol.service, /bin/systemctl stop ledcontrol.service, /bin/systemctl restart ledcontrol.service" \
    | sudo tee /etc/sudoers.d/ledcontrol > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable ledcontrol.service
sudo systemctl enable leds-off.service
sudo systemctl restart ledcontrol.service

# ── 6. RetroPie Setup menu module ─────────────────────────────────────────────
echo ""
echo "6. Installing RetroPie Setup menu module..."
sudo mkdir -p ~/RetroPie-Setup/scriptmodules/supplementary/
sudo cp -f "$REPO_DIR/ledcontrol.sh" ~/RetroPie-Setup/scriptmodules/supplementary/
sudo chmod +x ~/RetroPie-Setup/scriptmodules/supplementary/ledcontrol.sh

# ── 7. RunCommand hooks ───────────────────────────────────────────────────────
echo ""
echo "7. Installing runcommand hooks..."

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

# ── 8. Install pygame ─────────────────────────────────────────────────────────
echo ""
echo "8. Installing pygame..."
if ! python3 -c "import pygame" 2>/dev/null; then
    sudo apt-get install -y python3-pygame
    echo "   pygame installed"
else
    echo "   pygame already available"
fi

# ── 9. EmulationStation — RetroLED in Ports ───────────────────────────────────
echo ""
echo "9. Installing RetroLED into Ports..."

mkdir -p "$PORTS_DIR"
mkdir -p "$PORTS_IMAGES_DIR"

# RetroLED launcher script in ports
cat > "$PORTS_DIR/RetroLED.sh" << 'LAUNCHER'
#!/bin/bash
# RetroLED — arcade LED controller
cd /home/pi/LEDControl/retro-led
python3 /home/pi/LEDControl/retro-led/retro-led.py
LAUNCHER
chmod +x "$PORTS_DIR/RetroLED.sh"

# Copy cover art
cp -f "$REPO_DIR/es/images/led-control.png" "$PORTS_IMAGES_DIR/retro-led.png"

# Remove old led-control.sh entries, add RetroLED — always overwrite
mkdir -p "$(dirname "$PORTS_GAMELIST")"
python3 - <<'PYEOF'
import os, re
gamelist    = '/home/pi/.emulationstation/gamelists/ports/gamelist.xml'
image_abs   = '/home/pi/.emulationstation/gamelists/ports/images/retro-led.png'
entry = (
    '  <game>\n'
    '    <path>./RetroLED.sh</path>\n'
    '    <name>RetroLED</name>\n'
    '    <desc>Arcade-styled LED controller. Visualize and control your WS2812 cabinet LEDs '
    'in real time. Choose animations, colors, and brightness with joystick navigation.</desc>\n'
    '    <image>' + image_abs + '</image>\n'
    '    <developer>Belch Studios</developer>\n'
    '    <publisher>Belch Studios</publisher>\n'
    '    <releasedate>19810101T000000</releasedate>\n'
    '    <genre>Utility</genre>\n'
    '    <players>1</players>\n'
    '    <rating>1.0</rating>\n'
    '  </game>'
)
if os.path.exists(gamelist):
    content = open(gamelist).read()
    # Remove any old LED control entries (led-control.sh or RetroLED.sh)
    content = re.sub(r'\s*<game>(?:(?!</game>).)*(?:led-control|RetroLED)[^<]*\.sh(?:(?!</game>).)*</game>',
                     '', content, flags=re.DOTALL)
    content = content.replace('</gameList>', entry + '\n</gameList>')
    open(gamelist, 'w').write(content)
    print('   Updated ports gamelist')
else:
    os.makedirs(os.path.dirname(gamelist), exist_ok=True)
    open(gamelist, 'w').write('<?xml version="1.0"?>\n<gameList>\n' + entry + '\n</gameList>\n')
    print('   Created ports gamelist')
PYEOF

# Remove old ports scripts no longer needed
rm -f "$PORTS_DIR/led-control.sh" "$PORTS_DIR/led-joy2key.py"

# ── 10. Ports system in ES (ensure present) ───────────────────────────────────
if ! grep -q "<name>ports</name>" "$ES_SYSTEMS" 2>/dev/null; then
    sudo python3 - <<'PYEOF'
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
fi

# Remove old custom ledcontrol system (migration cleanup)
if grep -q "<name>ledcontrol</name>" "$ES_SYSTEMS" 2>/dev/null; then
    sudo python3 -c "
import re
path = '$ES_SYSTEMS'
content = open(path).read()
content = re.sub(r'\s*<system>\s*<name>ledcontrol</name>.*?</system>', '', content, flags=re.DOTALL)
open(path, 'w').write(content)
print('   Removed old ledcontrol system entry')
"
fi

# ── 11. rsync convenience alias ───────────────────────────────────────────────
echo ""
echo "11. Setting up rsync deploy alias..."
BASHRC="/home/pi/.bashrc"
if ! grep -q "retro-led-sync" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'ALIAS'

# RetroLED: pull latest from GitHub and reinstall
alias retro-led-sync='cd /home/pi/LEDControl && git pull && bash install.sh'
ALIAS
    echo "   Added 'retro-led-sync' alias to ~/.bashrc"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation complete! ==="
echo ""
echo "RetroLED appears under: Ports → RetroLED"
echo ""
echo "Next steps:"
echo "  1. Edit /home/pi/ledcontrol.toml to set your LED count and defaults"
echo "  2. Restart EmulationStation"
echo "  3. Run 'retro-led-sync' any time to pull and reinstall latest"
echo ""
echo "Quick test:"
echo "  $PYTHON $PROJECT_DIR/LEDControl.py --animate kitt --color red"
