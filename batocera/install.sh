#!/bin/bash
# batocera/install.sh — Batocera WS2812 LED Controller installer
# Run as root from the repo root: bash batocera/install.sh

set -e

echo "=== Installing WS2812 LED Controller for Batocera ==="

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Repo directory: $REPO_DIR"

INSTALL_DIR="/userdata/system/LEDControl"
CONFIG_PATH="/userdata/system/ledcontrol.toml"
SERVICES_DIR="/userdata/system/services"
PORTS_DIR="/userdata/roms/ports"
GAMELIST_DIR="/userdata/system/configs/emulationstation/gamelists/ports"
IMAGES_DIR="$GAMELIST_DIR/images"
GAMELIST="$GAMELIST_DIR/gamelist.xml"
GAME_START="/userdata/system/scripts/gameStart.sh"
GAME_STOP="/userdata/system/scripts/gameStop.sh"

# ── 1. Install directory ───────────────────────────────────────────────────────
echo ""
echo "1. Creating install directory..."
mkdir -p "$INSTALL_DIR"

# ── 2. Copy scripts ───────────────────────────────────────────────────────────
echo ""
echo "2. Copying scripts..."
cp "$REPO_DIR/batocera/LEDControl.py"       "$INSTALL_DIR/"
cp "$REPO_DIR/batocera/led-game-start.sh"   "$INSTALL_DIR/"
cp "$REPO_DIR/batocera/led-game-stop.sh"    "$INSTALL_DIR/"
cp "$REPO_DIR/update_config.py"             "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/led-game-start.sh" "$INSTALL_DIR/led-game-stop.sh"

# Copy config only if not already present (preserve customizations)
if [ ! -f "$CONFIG_PATH" ]; then
    cp "$REPO_DIR/ledcontrol.toml" "$CONFIG_PATH"
    echo "   Copied default ledcontrol.toml to $CONFIG_PATH"
else
    echo "   $CONFIG_PATH already exists — skipping (edit manually to add new sections)"
fi

# ── 3. Enable SPI ─────────────────────────────────────────────────────────────
echo ""
echo "3. Enabling SPI interface..."
BAT_CONFIG="/userdata/system/config.txt"
if grep -q "dtparam=spi=on" "$BAT_CONFIG" 2>/dev/null; then
    echo "   SPI already enabled in $BAT_CONFIG"
elif grep -q "dtparam=spi=on" /boot/config.txt 2>/dev/null; then
    echo "   SPI already enabled in /boot/config.txt"
else
    echo "dtparam=spi=on" >> "$BAT_CONFIG"
    echo "   Added dtparam=spi=on to $BAT_CONFIG (reboot required)"
fi

# ── 4. Install Python library ─────────────────────────────────────────────────
echo ""
echo "4. Installing neopixel_spi library..."
python3 -m pip install adafruit-blinka adafruit-circuitpython-neopixel-spi -q
echo "   Libraries installed"

# ── 5. batocera-services ──────────────────────────────────────────────────────
echo ""
echo "5. Installing batocera-services entry..."
mkdir -p "$SERVICES_DIR"
cp "$REPO_DIR/batocera/ledcontrol-service" "$SERVICES_DIR/ledcontrol"
chmod +x "$SERVICES_DIR/ledcontrol"
batocera-services enable ledcontrol
echo "   Service enabled"

# ── 6. Game hooks ─────────────────────────────────────────────────────────────
echo ""
echo "6. Installing game hooks..."
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

# ── 7. ES Ports entry ─────────────────────────────────────────────────────────
echo ""
echo "7. Installing LED Control into Ports..."
mkdir -p "$PORTS_DIR"
cp "$REPO_DIR/batocera/es/led-control.sh" "$PORTS_DIR/"
cp "$REPO_DIR/batocera/es/led-joy2key.py"  "$PORTS_DIR/"
chmod +x "$PORTS_DIR/led-control.sh" "$PORTS_DIR/led-joy2key.py"

mkdir -p "$IMAGES_DIR"
cp "$REPO_DIR/es/images/led-control.png" "$IMAGES_DIR/"

mkdir -p "$GAMELIST_DIR"
image_abs="$IMAGES_DIR/led-control.png"
python3 - <<PYEOF
import os, re
gamelist = '$GAMELIST'
image_abs = '$image_abs'
entry = (
    '  <game>\n'
    '    <path>./led-control.sh</path>\n'
    '    <name>LED Control</name>\n'
    '    <desc>Configure WS2812 LED animations and colors for your arcade cabinet marquee. '
    'Choose from KITT scanner, Cylon eye, glow pulse, center pulse, meteor shower, '
    'twinkle sparkles, color cycle, rainbow wave, solid color, or off. '
    'Changes take effect instantly.</desc>\n'
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

# ── 8. Start service now ──────────────────────────────────────────────────────
echo ""
echo "8. Starting LED service..."
batocera-services start ledcontrol
echo "   Service started"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_PATH to set your defaults and per-system animations"
echo "  2. Restart EmulationStation — LED Control appears under Ports"
echo "  3. Reboot to confirm auto-start: reboot"
echo ""
echo "Quick test:"
echo "  python3 $INSTALL_DIR/LEDControl.py --animate kitt --color red"
echo ""
echo "Service management:"
echo "  batocera-services start ledcontrol"
echo "  batocera-services stop ledcontrol"
