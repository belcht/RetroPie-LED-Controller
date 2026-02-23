#!/usr/bin/env bash

# This file is part of The RetroPie Project
#
# See the LICENSE.md file at the top-level directory of this distribution.

rp_module_id="ledcontrol"
rp_module_desc="WS2812 LED Control"
rp_module_section="config"

CONFIG_FILE="/home/pi/ledcontrol.toml"

function gui_ledcontrol() {
    local cmd=(dialog --backtitle "$__backtitle" --menu "LED Control - Choose Color or Animation" 24 80 16)
    local options=(
        1 "Red"
        2 "Green"
        3 "Blue"
        4 "White"
        5 "Yellow"
        6 "Purple"
        7 "Cyan"
        8 "Off"
        9 "KITT (scanner)"
        10 "Glow (pulse)"
        11 "Cycle (color loop)"
        12 "Rainbow Wave"
        13 "Meteor Shower"
        14 "Twinkle Sparkles"
        15 "Restart LED Service"
        16 "Stop LED Service"
    )
    local choice=$("${cmd[@]}" "${options[@]}" 2>&1 >/dev/tty)
    [[ -z "$choice" ]] && return

    case "$choice" in
        1) set_color "red" ;;
        2) set_color "green" ;;
        3) set_color "blue" ;;
        4) set_color "white" ;;
        5) set_color "yellow" ;;
        6) set_color "purple" ;;
        7) set_color "cyan" ;;
        8) set_color "off" ;;
        9)  set_animation "kitt" ;;
        10) set_animation "glow" ;;
        11) set_animation "cycle" ;;
        12) set_animation "rainbow" ;;
        13) set_animation "meteor" ;;
        14) set_animation "twinkle" ;;
        15) sudo systemctl restart ledcontrol.service && echo "Service restarted" && sleep 2 ;;
        16) sudo systemctl stop ledcontrol.service && echo "Service stopped" && sleep 2 ;;
    esac
}

function set_color() {
    local color="$1"

    # Set solid mode + color
    update_toml "general" "default_animate" '""'
    update_toml "general" "default_color" "\"$color\""

    sudo systemctl stop ledcontrol.service 2>/dev/null
    sleep 1  # give old process time to fully exit
    sudo systemctl start ledcontrol.service
    echo "Set to solid $color"
    sleep 2
}

function set_animation() {
    local anim="$1"

    # Set animation, keep current color
    update_toml "general" "default_animate" "\"$anim\""

    sudo systemctl stop ledcontrol.service 2>/dev/null
    sleep 1  # give old process time to fully exit
    sudo systemctl start ledcontrol.service
    echo "Set to $anim animation"
    sleep 2
}

function update_toml() {
    local section="$1"
    local key="$2"
    local value="$3"

    # Create section if missing
    if ! grep -q "\[$section\]" "$CONFIG_FILE" 2>/dev/null; then
        echo "[$section]" >> "$CONFIG_FILE"
    fi

    # Update or add the key
    if grep -q "^$key\s*=" "$CONFIG_FILE"; then
        sed -i "/^\[$section\]/,/^\[/ s/^$key\s*=.*$/$key = $value/" "$CONFIG_FILE"
    else
        sed -i "/^\[$section\]/a $key = $value" "$CONFIG_FILE"
    fi
}
