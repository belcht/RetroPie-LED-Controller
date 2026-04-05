#!/bin/bash
# batocera/install.sh — Batocera WS2812 LED Controller installer
# Run as root from the repo root: bash batocera/install.sh

set -e

echo "=== Installing WS2812 LED Controller for Batocera ==="

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Repo directory: $REPO_DIR"

INSTALL_DIR="/userdata/system/LEDControl"
RETRO_LED_DIR="$INSTALL_DIR/retro-led"
CONFIG_PATH="/userdata/system/ledcontrol.toml"
SERVICES_DIR="/userdata/system/services"
PORTS_DIR="/userdata/roms/ports"
GAMELIST_DIR="/userdata/system/configs/emulationstation/gamelists/ports"
IMAGES_DIR="$GAMELIST_DIR/images"
GAMELIST="$GAMELIST_DIR/gamelist.xml"
GAME_START="/userdata/system/scripts/gameStart.sh"
GAME_STOP="/userdata/system/scripts/gameStop.sh"

# ── 1. Install directories ─────────────────────────────────────────────────────
echo ""
echo "1. Creating install directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$RETRO_LED_DIR/assets/images"
mkdir -p "$RETRO_LED_DIR/vendor"

# ── 2. Copy / overwrite all scripts ──────────────────────────────────────────
echo ""
echo "2. Copying scripts (overwriting existing)..."
# batocera/ subdirectory files must be promoted to INSTALL_DIR root
cp -f "$REPO_DIR/batocera/LEDControl.py"     "$INSTALL_DIR/"
cp -f "$REPO_DIR/batocera/led-game-start.sh" "$INSTALL_DIR/"
cp -f "$REPO_DIR/batocera/led-game-stop.sh"  "$INSTALL_DIR/"
# led-ws-cmd.py and update_config.py live at repo root — already at INSTALL_DIR via rsync
chmod +x "$INSTALL_DIR/led-game-start.sh" "$INSTALL_DIR/led-game-stop.sh" "$INSTALL_DIR/led-ws-cmd.py"
echo "   Scripts copied"

# Copy config only if not already present (preserve customizations)
if [ ! -f "$CONFIG_PATH" ]; then
    cp "$REPO_DIR/ledcontrol.toml" "$CONFIG_PATH"
    echo "   Copied default ledcontrol.toml to $CONFIG_PATH"
else
    echo "   $CONFIG_PATH already exists — preserving"
fi

# ── 3. RetroLED — copy with vendored websockets ───────────────────────────────
echo ""
echo "3. Installing RetroLED..."
# retro-led/ subdir deploys to RETRO_LED_DIR via rsync — already in place
chmod +x "$RETRO_LED_DIR/retro-led.py"
echo "   RetroLED already in place (deployed via rsync)"

# Download Press Start 2P font if not present
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
BAT_CONFIG="/userdata/system/config.txt"
if grep -q "dtparam=spi=on" "$BAT_CONFIG" 2>/dev/null; then
    echo "   SPI already enabled in $BAT_CONFIG"
elif grep -q "dtparam=spi=on" /boot/config.txt 2>/dev/null; then
    echo "   SPI already enabled in /boot/config.txt"
else
    echo "dtparam=spi=on" >> "$BAT_CONFIG"
    echo "   Added dtparam=spi=on to $BAT_CONFIG (reboot required)"
fi

# ── 5. Install Python library ─────────────────────────────────────────────────
echo ""
echo "5. Installing neopixel_spi library..."
python3 -m pip install adafruit-blinka adafruit-circuitpython-neopixel-spi -q
echo "   Libraries installed"

# ── 6. batocera-services ──────────────────────────────────────────────────────
echo ""
echo "6. Installing batocera-services entry..."
mkdir -p "$SERVICES_DIR"
cp -f "$REPO_DIR/batocera/ledcontrol-service" "$SERVICES_DIR/ledcontrol"
chmod +x "$SERVICES_DIR/ledcontrol"
batocera-services enable ledcontrol
echo "   Service enabled"

# ── 7. Game hooks ─────────────────────────────────────────────────────────────
echo ""
echo "7. Installing game hooks..."
_install_hook() {
    local hook_file="$1"
    local hook_call="$2"
    if [ -f "$hook_file" ]; then
        if grep -q "LEDControl" "$hook_file" 2>/dev/null; then
            echo "   $hook_file already has LED hook — skipping"
        else
            printf '\n# LED Controller hook\n%s\n' "$hook_call" >> "$hook_file"
            echo "   Appended LED hook to $hook_file"
        fi
    else
        mkdir -p "$(dirname "$hook_file")"
        printf '#!/bin/bash\n# LED Controller hook\n%s\n' "$hook_call" > "$hook_file"
        chmod +x "$hook_file"
        echo "   Created $hook_file"
    fi
}

_install_hook "$GAME_START" '/userdata/system/LEDControl/led-game-start.sh "$@"'
_install_hook "$GAME_STOP"  '/userdata/system/LEDControl/led-game-stop.sh "$@"'

# ── 8. RetroLED in Ports ──────────────────────────────────────────────────────
echo ""
echo "8. Installing RetroLED into Ports..."
mkdir -p "$PORTS_DIR"
mkdir -p "$IMAGES_DIR"

cp -f "$REPO_DIR/es/images/led-control.png" "$IMAGES_DIR/retro-led.png"

# RetroLED launcher script
cat > "$PORTS_DIR/RetroLED.sh" << 'LAUNCHER'
#!/bin/bash
# RetroLED — arcade LED controller
export DISPLAY=:0
cd /userdata/system/LEDControl/retro-led
python3 /userdata/system/LEDControl/retro-led/retro-led.py > /tmp/retro-led.log 2>&1
LAUNCHER
chmod +x "$PORTS_DIR/RetroLED.sh"

# Remove old led-control.sh if present
rm -f "$PORTS_DIR/led-control.sh" "$PORTS_DIR/led-joy2key.py"

# Update gamelist — overwrite any old LED entries
python3 - <<PYEOF
import os, re
gamelist  = '$GAMELIST'
image_abs = '$IMAGES_DIR/retro-led.png'
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

# ── 9. rsync convenience alias ────────────────────────────────────────────────
echo ""
echo "9. Setting up rsync deploy alias..."
BASHRC="/root/.bashrc"
if ! grep -q "retro-led-sync" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'ALIAS'

# RetroLED: pull latest from GitHub and reinstall
alias retro-led-sync='cd /userdata/system/LEDControl && git pull && bash batocera/install.sh'
ALIAS
    echo "   Added 'retro-led-sync' alias to ~/.bashrc"
fi

# ── 10. Start service ─────────────────────────────────────────────────────────
echo ""
echo "10. Starting LED service..."
batocera-services start ledcontrol
echo "    Service started"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation complete! ==="
echo ""
echo "RetroLED appears under: Ports → RetroLED"
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_PATH to set your LED count and defaults"
echo "  2. Restart EmulationStation"
echo "  3. Run 'retro-led-sync' any time to pull and reinstall latest"
echo ""
echo "Service management:"
echo "  batocera-services start ledcontrol"
echo "  batocera-services stop ledcontrol"
