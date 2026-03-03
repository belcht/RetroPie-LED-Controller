#!/bin/bash
# install-batocera.sh - Automated installer for WS2812 LED Controller on Batocera
# Run as root: bash install-batocera.sh

set -e

echo "=== Batocera WS2812 LED Controller Installer ==="
echo "Running as user: $(whoami)"
echo "Repo directory: $(pwd)"
echo ""

REPO_DIR="$(pwd)"
SCRIPT_DIR="/userdata/system/scripts"
ES_SYSTEMS_DIR="/userdata/system/configs/emulationstation"

# Step 1: Create persistent script directory
echo "1. Creating persistent script directory..."
mkdir -p "$SCRIPT_DIR"
echo "   → $SCRIPT_DIR"

# Step 2: Copy main script and config
echo "2. Copying LEDControl.py and ledcontrol.toml..."
cp "$REPO_DIR/LEDControl.py" "$SCRIPT_DIR/" || { echo "ERROR: LEDControl.py not found in repo!"; exit 1; }
cp "$REPO_DIR/ledcontrol.toml" /userdata/system/scripts/ledcontrol.toml 2>/dev/null || echo "Warning: ledcontrol.toml not found (will use defaults)"

chmod +x "$SCRIPT_DIR/LEDControl.py"

# Step 3: Enable SPI
echo "3. Enabling SPI interface..."
if grep -q "dtparam=spi=on" /boot/config.txt; then
    echo "   SPI already enabled"
else
    echo "dtparam=spi=on" >> /boot/config.txt
    echo "   SPI enabled (reboot required for full effect)"
fi

# Step 4: Install rpi5-ws2812 library
echo "4. Installing rpi5-ws2812 library..."
pip3 install --break-system-packages rpi5-ws2812 || {
    echo "ERROR: Failed to install rpi5-ws2812"
    exit 1
}
echo "   Library installed successfully"

# Step 5: Create boot startup script (custom.sh)
echo "5. Creating boot startup hook..."
cat > /userdata/system/custom.sh << 'EOF'
#!/bin/bash
echo "[LED] Starting WS2812 controller at boot..."
/userdata/system/scripts/LEDControl.py &
EOF
chmod +x /userdata/system/custom.sh

# Step 6: Create shutdown hook
echo "6. Creating shutdown hook..."
cat > /userdata/system/custom-shutdown.sh << 'EOF'
#!/bin/bash
echo "[LED] Clearing LEDs on shutdown..."
/userdata/system/scripts/LEDControl.py --animate off
sleep 0.3
/userdata/system/scripts/LEDControl.py --animate off
echo "[LED] Shutdown clear complete"
EOF
chmod +x /userdata/system/custom-shutdown.sh

# Step 7: Create simple EmulationStation custom system (optional menu)
echo "7. Creating EmulationStation LED Control system..."
mkdir -p "$ES_SYSTEMS_DIR/roms/ledcontrol"
cat > "$ES_SYSTEMS_DIR/roms/ledcontrol/gamelist.xml" << 'EOF'
<gameList>
  <game>
    <path>./off.sh</path>
    <name>Turn LEDs Off</name>
  </game>
  <game>
    <path>./kitt-red.sh</path>
    <name>KITT Red</name>
  </game>
  <game>
    <path>./rainbow.sh</path>
    <name>Rainbow Wave</name>
  </game>
</gameList>
EOF

# Create simple launcher scripts
cat > "$ES_SYSTEMS_DIR/roms/ledcontrol/off.sh" << 'EOF'
#!/bin/bash
/userdata/system/scripts/LEDControl.py --animate off
EOF

cat > "$ES_SYSTEMS_DIR/roms/ledcontrol/kitt-red.sh" << 'EOF'
#!/bin/bash
/userdata/system/scripts/LEDControl.py --animate kitt --color red
EOF

cat > "$ES_SYSTEMS_DIR/roms/ledcontrol/rainbow.sh" << 'EOF'
#!/bin/bash
/userdata/system/scripts/LEDControl.py --animate rainbow
EOF

chmod +x "$ES_SYSTEMS_DIR/roms/ledcontrol/"*.sh

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Next steps:"
echo "1. Edit config: vi /userdata/system/scripts/ledcontrol.toml"
echo "2. Reboot Batocera to start the LEDs"
echo "3. In EmulationStation you should now see a new 'LED Control' system"
echo ""
echo "To manually test:"
echo "   /userdata/system/scripts/LEDControl.py --animate kitt --color red"
echo ""
echo "Log file for shutdown hook: /userdata/system/custom-shutdown.sh"
