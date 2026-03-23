#!/usr/bin/env bash
clear
LOG="/tmp/ledcontrol-es.log"
PYTHON="/home/pi/LEDControl/venv/bin/python3"
UPDATE_CFG="/home/pi/LEDControl/update_config.py"
CONFIG="/home/pi/ledcontrol.toml"
JOY2KEY="/home/pi/RetroPie/roms/ledcontrol/led-joy2key.py"

_joy2key_start() {
    for js in /dev/input/js*; do
        [[ -e "$js" ]] && python3 "$JOY2KEY" "$js"
    done
}

_joy2key_stop() {
    pkill -f "led-joy2key.py" 2>/dev/null || true
}

_joy2key_start

choice=$(dialog --menu "Set Color" 18 45 9 \
    1 "Red" \
    2 "Orange" \
    3 "Yellow" \
    4 "Green" \
    5 "Cyan" \
    6 "Blue" \
    7 "Purple" \
    8 "Pink" \
    9 "White" \
    2>&1 >/dev/tty)

_joy2key_stop
clear

[[ -z "$choice" ]] && exit 0

case "$choice" in
    1) color="red" ;;
    2) color="orange" ;;
    3) color="yellow" ;;
    4) color="green" ;;
    5) color="cyan" ;;
    6) color="blue" ;;
    7) color="purple" ;;
    8) color="pink" ;;
    9) color="white" ;;
    *) exit 0 ;;
esac

echo "$(date '+%Y-%m-%d %H:%M:%S') - Set color: $color" >> "$LOG"

# Warn if current animation ignores color
current_anim=$("$PYTHON" -c "
import tomllib
with open('$CONFIG', 'rb') as f:
    c = tomllib.load(f)
print(c.get('general', {}).get('default_animate', ''))
" 2>/dev/null)

if [[ "$current_anim" == "cycle" || "$current_anim" == "rainbow" ]]; then
    dialog --msgbox "$current_anim generates its own colors — this color will apply when you switch to another animation." \
        7 58 2>&1 >/dev/tty
    clear
fi

"$PYTHON" "$UPDATE_CFG" "$CONFIG" general default_color "\"$color\"" >> "$LOG" 2>&1
sudo systemctl stop ledcontrol.service >> "$LOG" 2>&1
sleep 0.5
sudo systemctl start ledcontrol.service >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Done" >> "$LOG"
