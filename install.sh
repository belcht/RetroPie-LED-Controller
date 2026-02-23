#!/bin/bash
# install.sh - Automated setup for Raspberry Pi 5 WS2812 LED Controller
# Run with: sudo bash install.sh

set -e

echo "=== Installing WS2812 LED Controller for Raspberry Pi 5 ==="

PROJECT_DIR="/home/pi/LEDControl"
REPO_DIR="$(pwd)"

# Create project directory
echo "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Install the library
echo "Installing rpi5-ws2812 library..."
source venv/bin/activate
pip install --upgrade pip
pip install rpi5-ws2812
deactivate

# Copy main script and config (from repo)
echo "Copying files from repo..."
cp "$REPO_DIR/LEDControl.py" . 2>/dev/null || echo "Warning: LEDControl.py not found in repo"
cp "$REPO_DIR/ledcontrol.toml" /home/pi/ 2>/dev/null || echo "Warning: ledcontrol.toml not found - create manually in /home/pi/"

# Enable SPI (non-interactively)
echo "Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Copy systemd services and shutdown script
echo "Installing systemd services..."
sudo cp "$REPO_DIR/ledcontrol.service" /etc/systemd/system/ 2>/dev/null || echo "ledcontrol.service not found"
sudo cp "$REPO_DIR/leds-off.service" /etc/systemd/system/ 2>/dev/null || echo "leds-off.service not found"
sudo cp "$REPO_DIR/leds-off-on-shutdown.sh" /usr/local/bin/ 2>/dev/null || echo "leds-off-on-shutdown.sh not found"

sudo chmod +x /usr/local/bin/leds-off-on-shutdown.sh 2>/dev/null || true

# Reload and enable services
sudo systemctl daemon-reload
sudo systemctl enable ledcontrol.service
sudo systemctl enable leds-off.service
sudo systemctl start ledcontrol.service

# RetroPie menu integration
echo "Installing RetroPie menu module..."
mkdir -p ~/RetroPie-Setup/scriptmodules/supplementary/
cp "$REPO_DIR/ledcontrol.sh" ~/RetroPie-Setup/scriptmodules/supplementary/ 2>/dev/null || echo "ledcontrol.sh not found - copy manually"
chmod +x ~/RetroPie-Setup/scriptmodules/supplementary/ledcontrol.sh 2>/dev/null || true

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "1. Edit /home/pi/ledcontrol.toml to set your preferred defaults"
echo "2. Restart service to apply changes:"
echo "   sudo systemctl restart ledcontrol.service"
echo "3. Test on reboot:"
echo "   sudo reboot"
echo "4. Access in RetroPie: Setup → Configuration/tools → WS2812 LED Control"
echo ""
echo "If anything is missing, copy files manually from the repo."
