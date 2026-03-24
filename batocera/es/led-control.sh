#!/usr/bin/env bash
# led-control.sh — LED Control menu for Batocera Ports
#
# Installed to /userdata/roms/ports/ alongside led-joy2key.py.
# Appears as "LED Control" in the Ports section of EmulationStation.

LOG="/tmp/ledcontrol-es.log"
SCRIPT="/userdata/system/LEDControl/LEDControl.py"
UPDATE_CFG="/userdata/system/LEDControl/update_config.py"
CONFIG="/userdata/system/ledcontrol.toml"
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
    python3 "$UPDATE_CFG" "$CONFIG" "$section" "$key" "\"$val\"" >> "$LOG" 2>&1
    # Kill current LED process
    if [ -f /tmp/ledcontrol.pid ]; then
        kill "$(cat /tmp/ledcontrol.pid)" 2>/dev/null || true
        sleep 0.3
        rm -f /tmp/ledcontrol.pid
    fi
    # Start new instance with updated config
    python3 "$SCRIPT" >> "$LOG" 2>&1 &
    echo $! > /tmp/ledcontrol.pid
}

_set_animation() {
    local choice anim
    choice=$(dialog --menu "Set Animation" 24 55 10 \
        1 "KITT (scanner)" \
        2 "Cylon Eye (roaming stare)" \
        3 "Glow (pulse)" \
        4 "Center Pulse (Batocera)" \
        5 "Meteor Shower" \
        6 "Twinkle Sparkles" \
        7 "Cycle  [generates own colors]" \
        8 "Rainbow Wave  [generates own colors]" \
        9 "Solid Color" \
        10 "Off" \
        2>&1 >/dev/tty)
    clear
    [[ -z "$choice" ]] && return

    case "$choice" in
        1)  anim="kitt"        ;;
        2)  anim="cylon"       ;;
        3)  anim="glow"        ;;
        4)  anim="centerpulse" ;;
        5)  anim="meteor"      ;;
        6)  anim="twinkle"     ;;
        7)  anim="cycle"       ;;
        8)  anim="rainbow"     ;;
        9)  anim=""            ;;
        10) anim="off"         ;;
        *)  return             ;;
    esac

    if [[ "$anim" == "cycle" || "$anim" == "rainbow" ]]; then
        dialog --msgbox "$anim generates its own colors — color selection is ignored for this animation." \
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
        *) return         ;;
    esac

    local current_anim
    current_anim=$(python3 -c "
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
    if [ -f /tmp/ledcontrol.pid ]; then
        kill "$(cat /tmp/ledcontrol.pid)" 2>/dev/null || true
        sleep 0.3
        rm -f /tmp/ledcontrol.pid
    fi
    python3 "$SCRIPT" --animate off >> "$LOG" 2>&1
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
