#!/usr/bin/env bash
# led-control.sh — LED Control menu for RetroPie Ports
#
# Install to /home/pi/RetroPie/roms/ports/ alongside led-joy2key.py.
# Appears as "LED Control" in the Ports section of EmulationStation.

LOG="/tmp/ledcontrol-es.log"
PYTHON="/home/pi/LEDControl/venv/bin/python3"
UPDATE_CFG="/home/pi/LEDControl/update_config.py"
CONFIG="/home/pi/ledcontrol.toml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JOY2KEY="$SCRIPT_DIR/led-joy2key.py"

_joy2key_start() {
    pkill -f joy2key 2>/dev/null || true
    sleep 0.1
    for js in /dev/input/js*; do
        [[ -e "$js" ]] && python3 "$JOY2KEY" "$js"
    done
}

_joy2key_stop() {
    pkill -f joy2key 2>/dev/null || true
}

_apply() {
    local section="$1" key="$2" val="$3"
    "$PYTHON" "$UPDATE_CFG" "$CONFIG" "$section" "$key" "\"$val\"" >> "$LOG" 2>&1
    sudo systemctl stop ledcontrol.service  >> "$LOG" 2>&1
    sleep 0.5
    sudo systemctl start ledcontrol.service >> "$LOG" 2>&1
}

_set_animation() {
    local choice anim
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
    clear
    [[ -z "$choice" ]] && return

    case "$choice" in
        1) anim="kitt"    ;;
        2) anim="glow"    ;;
        3) anim="meteor"  ;;
        4) anim="twinkle" ;;
        5) anim="cycle"   ;;
        6) anim="rainbow" ;;
        7) anim=""        ;;
        8) anim="off"     ;;
        *) return ;;
    esac

    if [[ "$anim" == "cycle" || "$anim" == "rainbow" ]]; then
        dialog --msgbox "$anim generates its own colors — your color selection is ignored for this animation." \
            6 55 2>&1 >/dev/tty
        clear
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') - Set animation: ${anim:-solid}" >> "$LOG"
    _apply general default_animate "$anim"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Done" >> "$LOG"
}

_set_color() {
    local choice color
    choice=$(dialog --menu "Set Color" 18 45 9 \
        1 "Red"    \
        2 "Orange" \
        3 "Yellow" \
        4 "Green"  \
        5 "Cyan"   \
        6 "Blue"   \
        7 "Purple" \
        8 "Pink"   \
        9 "White"  \
        2>&1 >/dev/tty)
    clear
    [[ -z "$choice" ]] && return

    case "$choice" in
        1) color="red"    ;;
        2) color="orange" ;;
        3) color="yellow" ;;
        4) color="green"  ;;
        5) color="cyan"   ;;
        6) color="blue"   ;;
        7) color="purple" ;;
        8) color="pink"   ;;
        9) color="white"  ;;
        *) return ;;
    esac

    local current_anim
    current_anim=$("$PYTHON" -c "
import tomllib
with open('$CONFIG', 'rb') as f:
    c = tomllib.load(f)
print(c.get('general', {}).get('default_animate', ''))
" 2>/dev/null)

    if [[ "$current_anim" == "cycle" || "$current_anim" == "rainbow" ]]; then
        dialog --msgbox "$current_anim generates its own colors — this color will apply when you switch animations." \
            7 58 2>&1 >/dev/tty
        clear
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') - Set color: $color" >> "$LOG"
    _apply general default_color "$color"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Done" >> "$LOG"
}

_leds_off() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - LEDs off" >> "$LOG"
    sudo systemctl stop ledcontrol.service >> "$LOG" 2>&1
}

# ── Main loop ─────────────────────────────────────────────────────────────────
clear
_joy2key_start

while true; do
    choice=$(dialog --menu "LED Control" 12 40 4 \
        1 "Set Animation" \
        2 "Set Color"     \
        3 "LEDs Off"      \
        4 "Exit"          \
        2>&1 >/dev/tty)
    clear

    case "$choice" in
        1) _set_animation ;;
        2) _set_color     ;;
        3) _leds_off      ;;
        4 | "") break     ;;
    esac
done

_joy2key_stop
clear
