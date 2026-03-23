#!/usr/bin/env bash
LOG="/tmp/ledcontrol-es.log"
PYTHON="/home/pi/LEDControl/venv/bin/python3"
UPDATE_CFG="/home/pi/LEDControl/update_config.py"
CONFIG="/home/pi/ledcontrol.toml"
JOY2KEY="/opt/retropie/admin/joy2key/joy2key.py"

_joy2key_start() {
    [[ ! -f "$JOY2KEY" ]] && return
    for js in /dev/input/js*; do
        [[ -e "$js" ]] || continue
        python3 "$JOY2KEY" "$js" kcub1 kcuf1 kcuu1 kcud1 0x0a 0x1b
    done
}

_joy2key_stop() {
    pkill -f "joy2key.py" 2>/dev/null || true
}

_joy2key_start

choice=$(dialog --menu "Set Animation" 20 55 10 \
    1 "KITT (scanner)" \
    2 "Glow (pulse)" \
    3 "Meteor Shower" \
    4 "Twinkle Sparkles" \
    5 "Cycle  [generates own colors]" \
    6 "Rainbow Wave  [generates own colors]" \
    7 "Solid Color" \
    8 "Off" \
    2>&1 >/dev/tty)

_joy2key_stop

[[ -z "$choice" ]] && exit 0

case "$choice" in
    1) anim="kitt" ;;
    2) anim="glow" ;;
    3) anim="meteor" ;;
    4) anim="twinkle" ;;
    5) anim="cycle" ;;
    6) anim="rainbow" ;;
    7) anim="" ;;
    8) anim="off" ;;
    *) exit 0 ;;
esac

echo "$(date '+%Y-%m-%d %H:%M:%S') - Set animation: ${anim:-solid}" >> "$LOG"

if [[ "$anim" == "cycle" || "$anim" == "rainbow" ]]; then
    dialog --msgbox "$anim generates its own colors — your color selection is ignored for this animation." \
        6 55 2>&1 >/dev/tty
fi

"$PYTHON" "$UPDATE_CFG" "$CONFIG" general default_animate "\"$anim\"" >> "$LOG" 2>&1
sudo systemctl stop ledcontrol.service >> "$LOG" 2>&1
sleep 0.5
sudo systemctl start ledcontrol.service >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Done" >> "$LOG"
