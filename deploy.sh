#!/usr/bin/env bash
# deploy.sh — Sync repo files to Pi and restart the LED service.
#
# Usage:
#   ./deploy.sh                    # uses default hostname 'retropie.local'
#   ./deploy.sh 192.168.1.42       # use IP address
#   ./deploy.sh retropie.local     # use hostname
#
# Requirements:
#   - SSH key auth to the Pi: ssh-copy-id pi@retropie.local
#   - rsync installed on Mac (comes with macOS)

set -e

PI="${1:-retropie.local}"
REMOTE="pi@${PI}"
PROJECT="/home/pi/LEDControl"
PORTS="/home/pi/RetroPie/roms/ports"

echo "==> Deploying to ${REMOTE}..."

# ── Python scripts → /home/pi/LEDControl/ ─────────────────────────────────────
rsync -av --exclude='*.pyc' --exclude='__pycache__' \
    LEDControl.py \
    update_config.py \
    led-game-start.sh \
    led-game-end.sh \
    "${REMOTE}:${PROJECT}/"

ssh "${REMOTE}" "chmod +x ${PROJECT}/led-game-start.sh ${PROJECT}/led-game-end.sh"

# ── Config → /home/pi/ ────────────────────────────────────────────────────────
# Note: only deploy if you've intentionally changed the repo's toml.
# Your Pi's toml may have local customizations.
rsync -av ledcontrol.toml "${REMOTE}:/home/pi/"

# ── RetroPie menu module ───────────────────────────────────────────────────────
rsync -av ledcontrol.sh \
    "${REMOTE}:~/RetroPie-Setup/scriptmodules/supplementary/"

# ── ES scripts + cover art → Ports ───────────────────────────────────────────
ssh "${REMOTE}" "mkdir -p ${PORTS}"
rsync -av es/led-control.sh es/led-joy2key.py "${REMOTE}:${PORTS}/"
ssh "${REMOTE}" "chmod +x ${PORTS}/led-control.sh ${PORTS}/led-joy2key.py"
ssh "${REMOTE}" "mkdir -p ~/.emulationstation/gamelists/ports/images"
rsync -av es/images/led-control.png "${REMOTE}:~/.emulationstation/gamelists/ports/images/"

# ── Restart service ───────────────────────────────────────────────────────────
echo "==> Restarting ledcontrol.service..."
ssh "${REMOTE}" "sudo systemctl restart ledcontrol.service"

echo ""
echo "==> Done."
echo "    Check status : ssh ${REMOTE} 'sudo systemctl status ledcontrol.service'"
echo "    View logs    : ssh ${REMOTE} 'journalctl -u ledcontrol.service -f'"
