#!/usr/bin/env bash

# This file is part of The RetroPie Project
#
# See the LICENSE.md file at the top-level directory of this distribution.

rp_module_id="ledcontrol"
rp_module_desc="WS2812 LED Control"
rp_module_section="config"

CONFIG_FILE="/home/pi/ledcontrol.toml"
PYTHON="/home/pi/LEDControl/venv/bin/python3"
UPDATE_CFG="/home/pi/LEDControl/update_config.py"

# Animations that generate their own colors — color setting is ignored for these
COLOR_IGNORED_ANIMS=("rainbow" "cycle")

function gui_ledcontrol() {
    while true; do
        local cmd=(dialog --backtitle "$__backtitle" --menu "LED Control" 12 50 4)
        local options=(
            1 "Set Animation"
            2 "Set Color"
            3 "Restart LED Service"
            4 "Stop LED Service"
        )
        local choice=$("${cmd[@]}" "${options[@]}" 2>&1 >/dev/tty)
        [[ -z "$choice" ]] && return

        case "$choice" in
            1) menu_animation ;;
            2) menu_color ;;
            3) sudo systemctl restart ledcontrol.service && _msg "Service restarted." ;;
            4) sudo systemctl stop ledcontrol.service   && _msg "Service stopped." ;;
        esac
    done
}

function menu_animation() {
    local cmd=(dialog --backtitle "$__backtitle" --menu "Set Animation" 22 60 14)
    local options=(
        1  "KITT (scanner)"
        2  "Glow (pulse)"
        3  "Meteor Shower"
        4  "Twinkle Sparkles"
        5  "Cycle  [uses own colors]"
        6  "Rainbow Wave  [uses own colors]"
        7  "Solid Color"
        8  "Off"
    )
    local choice=$("${cmd[@]}" "${options[@]}" 2>&1 >/dev/tty)
    [[ -z "$choice" ]] && return

    case "$choice" in
        1) set_animation "kitt" ;;
        2) set_animation "glow" ;;
        3) set_animation "meteor" ;;
        4) set_animation "twinkle" ;;
        5) set_animation "cycle"   ; _warn_color_ignored "Cycle" ;;
        6) set_animation "rainbow" ; _warn_color_ignored "Rainbow" ;;
        7) set_solid ;;
        8) set_animation "off" ;;
    esac
}

function menu_color() {
    local cmd=(dialog --backtitle "$__backtitle" --menu "Set Color" 20 50 11)
    local options=(
        1  "Red"
        2  "Orange"
        3  "Yellow"
        4  "Green"
        5  "Cyan"
        6  "Blue"
        7  "Purple"
        8  "Pink"
        9  "White"
    )
    local choice=$("${cmd[@]}" "${options[@]}" 2>&1 >/dev/tty)
    [[ -z "$choice" ]] && return

    case "$choice" in
        1) set_color "red" ;;
        2) set_color "orange" ;;
        3) set_color "yellow" ;;
        4) set_color "green" ;;
        5) set_color "cyan" ;;
        6) set_color "blue" ;;
        7) set_color "purple" ;;
        8) set_color "pink" ;;
        9) set_color "white" ;;
    esac

    # Warn if current animation ignores color
    local current_anim
    current_anim=$(grep -A5 '^\[general\]' "$CONFIG_FILE" 2>/dev/null \
        | grep 'default_animate' | head -1 | sed 's/.*=\s*"\(.*\)"/\1/')
    for anim in "${COLOR_IGNORED_ANIMS[@]}"; do
        if [[ "$current_anim" == "$anim" ]]; then
            _warn_color_ignored "$current_anim"
            break
        fi
    done
}

# ── Actions ───────────────────────────────────────────────────────────────────

function set_animation() {
    local anim="$1"

    if [[ "$anim" == "off" ]]; then
        update_toml "general" "default_animate" '"off"'
    else
        update_toml "general" "default_animate" "\"$anim\""
    fi

    _restart_service
    _msg "Animation set to: $anim"
}

function set_color() {
    local color="$1"
    # Update color only — do NOT touch default_animate
    update_toml "general" "default_color" "\"$color\""
    _restart_service
    _msg "Color set to: $color"
}

function set_solid() {
    update_toml "general" "default_animate" '""'
    _restart_service
    _msg "Mode set to: Solid Color"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

function update_toml() {
    local section="$1"
    local key="$2"
    local value="$3"
    "$PYTHON" "$UPDATE_CFG" "$CONFIG_FILE" "$section" "$key" "$value"
}

function _restart_service() {
    sudo systemctl stop ledcontrol.service 2>/dev/null
    sleep 0.5
    sudo systemctl start ledcontrol.service
}

function _msg() {
    dialog --backtitle "$__backtitle" --infobox "$1" 4 40
    sleep 1.5
}

function _warn_color_ignored() {
    local anim="$1"
    dialog --backtitle "$__backtitle" \
        --msgbox "$anim generates its own colors.\nYour color selection is ignored for this animation." \
        6 55
}
