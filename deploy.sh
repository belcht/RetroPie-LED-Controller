#!/usr/bin/env bash
# deploy.sh — Sync repo to RetroPie or Batocera and run install
#
# NOTE: this runs the LED-ONLY installer (install.sh / batocera/install.sh) for fast
#       iteration on the LED software after a box is already set up. For a FIRST-TIME /
#       FULL build (OS update + RetroPie + hardening + LED), use picadeinstall.sh
#       instead — see docs/QUICKSTART.md.
#
# Usage:
#   bash deploy.sh retropie                  # deploy to RetroPie (default)
#   bash deploy.sh batocera                  # deploy to Batocera
#   bash deploy.sh pivert.local              # any hostname — auto-detects retropie
#   bash deploy.sh retropie 192.168.1.42     # named target with IP override
#   bash deploy.sh batocera 192.168.1.55     # named target with IP override
#   bash deploy.sh retropie --sync-only      # sync files only, skip install
#
# First-time setup:
#   ssh-copy-id pi@retropie.local            # RetroPie (password: raspberry)
#   ssh-copy-id root@batocera.local          # Batocera  (password: linux)

set -e

LOG="$(dirname "$0")/deploy.log"
exec > >(tee "$LOG") 2>&1
echo "Deploy started: $(date)"

# ── Parse args ────────────────────────────────────────────────────────────────
TARGET=""
HOST_OVERRIDE=""
SYNC_ONLY=false

for arg in "$@"; do
    case $arg in
        retropie|batocera) TARGET="$arg" ;;
        --sync-only)       SYNC_ONLY=true ;;
        *)                 HOST_OVERRIDE="$arg" ;;
    esac
done

# If no named target given, default to retropie
[ -z "$TARGET" ] && TARGET="retropie"

# ── Target config ─────────────────────────────────────────────────────────────
if [ "$TARGET" = "batocera" ]; then
    DEFAULT_HOST="batocera.local"
    PI_USER="root"
    REMOTE_DIR="/userdata/system/LEDControl"
    INSTALL_CMD="bash batocera/install.sh"
else
    DEFAULT_HOST="retropie.local"
    PI_USER="pi"
    REMOTE_DIR="/home/pi/LEDControl"
    INSTALL_CMD="bash install.sh"
fi

PI_HOST="${HOST_OVERRIDE:-$DEFAULT_HOST}"
REMOTE="$PI_USER@$PI_HOST"

echo "=== RetroLED Deploy ==="
echo "Target  : $TARGET"
echo "Host    : $REMOTE"
echo "Remote  : $REMOTE_DIR"
echo ""

# ── Connection check ──────────────────────────────────────────────────────────
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE" true 2>/dev/null; then
    echo "ERROR: Cannot connect to $PI_HOST as $PI_USER"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Make sure the device is on and on the same network"
    echo "  2. Try passing the IP: bash deploy.sh $TARGET 192.168.x.x"
    echo "  3. Set up passwordless SSH:"
    if [ "$TARGET" = "batocera" ]; then
        echo "       ssh-copy-id root@$PI_HOST   (password: linux)"
    else
        echo "       ssh-copy-id pi@$PI_HOST     (password: raspberry)"
    fi
    exit 1
fi

echo "Connection OK"
echo ""

# ── Sync ──────────────────────────────────────────────────────────────────────
ssh "$REMOTE" "mkdir -p $REMOTE_DIR"

echo "Syncing files..."
rsync -avz --delete \
    --exclude='.git/' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='*.so' \
    --exclude='deploy.log' \
    ./ "$REMOTE:$REMOTE_DIR/"

echo ""
echo "Sync complete."

if [ "$SYNC_ONLY" = true ]; then
    echo "Skipping install (--sync-only)"
    exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────
echo ""
echo "Running $INSTALL_CMD on $TARGET..."
ssh "$REMOTE" "cd $REMOTE_DIR && $INSTALL_CMD"

echo ""
echo "=== Deploy complete! ==="
echo ""
if [ "$TARGET" = "batocera" ]; then
    echo "Useful commands:"
    echo "  Service status : ssh $REMOTE 'batocera-services status ledcontrol'"
    echo "  Start service  : ssh $REMOTE 'batocera-services start ledcontrol'"
    echo "  Restart ES     : ssh $REMOTE 'batocera-es restart'"
else
    echo "Useful commands:"
    echo "  LED logs       : ssh $REMOTE 'journalctl -u ledcontrol.service -f'"
    echo "  Service status : ssh $REMOTE 'sudo systemctl status ledcontrol.service'"
    echo "  Restart ES     : ssh $REMOTE 'sudo systemctl restart emulationstation'"
fi
