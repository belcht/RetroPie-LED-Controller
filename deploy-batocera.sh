#!/usr/bin/env bash
# deploy-batocera.sh — Sync batocera files to Batocera machine and restart LED.
#
# Usage:
#   ./deploy-batocera.sh                # default: root@bat1.local
#   ./deploy-batocera.sh 192.168.1.42   # use IP address
#   ./deploy-batocera.sh bat1.local     # use hostname
#
# Requirements:
#   - SSH key auth: ssh-copy-id root@bat1.local
#   - rsync installed on Mac (comes with macOS)
#
# Note: Batocera does not include git — use this script instead of git pull.

set -e

BAT="${1:-bat1.local}"
REMOTE="root@${BAT}"
INSTALL_DIR="/userdata/system/LEDControl"
PORTS_DIR="/userdata/roms/ports"
GAMELIST_IMAGES="/userdata/system/configs/emulationstation/gamelists/ports/images"

echo "==> Deploying to ${REMOTE}..."

# ── Core scripts → /userdata/system/LEDControl/ ───────────────────────────────
ssh "${REMOTE}" "mkdir -p ${INSTALL_DIR}"
rsync -av --exclude='*.pyc' --exclude='__pycache__' \
    batocera/LEDControl.py \
    batocera/led-game-start.sh \
    batocera/led-game-stop.sh \
    update_config.py \
    "${REMOTE}:${INSTALL_DIR}/"
ssh "${REMOTE}" "chmod +x ${INSTALL_DIR}/led-game-start.sh ${INSTALL_DIR}/led-game-stop.sh"

# ── Config → /userdata/system/ ────────────────────────────────────────────────
# Note: --ignore-existing preserves any local customisations already on the machine.
rsync -av --ignore-existing ledcontrol.toml "${REMOTE}:/userdata/system/"

# ── ES scripts + cover art → Ports ───────────────────────────────────────────
ssh "${REMOTE}" "mkdir -p ${PORTS_DIR}"
rsync -av batocera/es/led-control.sh batocera/es/led-joy2key.py "${REMOTE}:${PORTS_DIR}/"
ssh "${REMOTE}" "chmod +x ${PORTS_DIR}/led-control.sh ${PORTS_DIR}/led-joy2key.py"
ssh "${REMOTE}" "mkdir -p ${GAMELIST_IMAGES}"
rsync -av es/images/led-control.png "${REMOTE}:${GAMELIST_IMAGES}/"

# ── Restart LED process ───────────────────────────────────────────────────────
echo "==> Restarting LED process..."
ssh "${REMOTE}" "
    if [ -f /tmp/ledcontrol.pid ]; then
        kill \$(cat /tmp/ledcontrol.pid) 2>/dev/null || true
        sleep 0.3
        rm -f /tmp/ledcontrol.pid
    fi
    python3 ${INSTALL_DIR}/LEDControl.py &
    echo \$! > /tmp/ledcontrol.pid
    echo 'LED process started (PID '\$(cat /tmp/ledcontrol.pid)')'
"

echo ""
echo "==> Done."
echo "    View log  : ssh ${REMOTE} 'cat /tmp/ledcontrol-es.log'"
echo "    Test      : ssh ${REMOTE} 'python3 ${INSTALL_DIR}/LEDControl.py --animate kitt --color red'"
echo "    Kill LED  : ssh ${REMOTE} 'kill \$(cat /tmp/ledcontrol.pid)'"
