#!/bin/bash
# install.sh - Automated setup for Raspberry Pi 5 WS2812 LED Controller
# Run as normal user: bash install.sh (prompts for sudo when needed)

set -e

echo "=== Installing WS2812 LED Controller for Raspberry Pi 5 ==="

# Capture repo path FIRST (as user pi)
REPO_DIR="$(pwd)"
echo "Repo directory: $REPO_DIR"

PROJECT_DIR="/home/pi/LEDControl"

# Create project directory (no sudo)
echo "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create virtual environment (as pi - no sudo)
echo "Creating virtual environment..."
python3 -m venv venv

# Install the library (as pi)
echo "Installing rpi5-ws2812 library..."
source venv/bin/activate
pip install --upgrade pip
pip install rpi5-ws2812
deactivate

# Copy main script and config (as pi)
echo "Copying files from repo ($REPO_DIR)..."
cp "$REPO_DIR/LEDControl.py" . 2>/dev/null || echo "Warning: LEDControl.py not found"
cp "$REPO_DIR/ledcontrol.toml" /home/pi/ 2>/dev/null || echo "Warning: ledcontrol.toml not found - create manually in /home/pi/"

# Enable SPI (requires sudo)
echo "Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Copy and enable systemd services (requires sudo)
echo "Installing systemd services..."
sudo cp "$REPO_DIR/ledcontrol.service" /etc/systemd/system/ 2>/dev/null || echo "ledcontrol.service not found"
sudo cp "$REPO_DIR/leds-off.service" /etc/systemd/system/ 2>/dev/null || echo "leds-off.service not found"
sudo cp "$REPO_DIR/leds-off-on-shutdown.sh" /usr/local/bin/ 2>/dev/null || echo "leds-off-on-shutdown.sh not found"

sudo chmod +x /usr/local/bin/leds-off-on-shutdown.sh 2>/dev/null || true

sudo systemctl daemon-reload
sudo systemctl enable ledcontrol.service
sudo systemctl enable leds-off.service
sudo systemctl start ledcontrol.service

# RetroPie menu integration (as pi - no sudo)
echo "Installing RetroPie menu module..."
mkdir -p ~/RetroPie-Setup/scriptmodules/supplementary/
cp "$REPO_DIR/ledcontrol.sh" ~/RetroPie-Setup/scriptmodules/supplementary/
chmod +x ~/RetroPie-Setup/scriptmodules/supplementary/ledcontrol.sh
echo "Copied ledcontrol.sh to ~/RetroPie-Setup/scriptmodules/supplementary/"

echo ""
echo "=== Installation complete! ==="
echo "Next steps:"
echo "1. Edit /home/pi/ledcontrol.toml for your defaults"
echo "2. sudo systemctl restart ledcontrol.service"
echo "3. Reboot to test: sudo reboot"
echo "4. Access in RetroPie: Setup → Configuration/tools → WS2812 LED Control"
