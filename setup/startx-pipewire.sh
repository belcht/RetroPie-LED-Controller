#!/bin/bash
# startx wrapper for dual-purpose (arcade + desktop) cabinets.
#
# EmulationStation needs raw ALSA for its volume control, so picadeinstall masks
# PipeWire system-wide. But the PIXEL desktop (startx) needs PipeWire for audio.
# This wrapper turns PipeWire ON for the duration of a desktop session and OFF
# (re-masks) when you leave it — so both worlds have working sound, with no manual
# steps. You start ES from the autostart and quit it to reach the shell, so ES is
# never running during startx and the audio cards hand off cleanly.
#
# Installed by picadeinstall as /usr/local/bin/startx, which shadows
# /usr/bin/startx on PATH. Just run `startx` as usual.
PW="pipewire.service pipewire.socket pipewire-pulse.service pipewire-pulse.socket wireplumber.service"

_pw_on(){
    systemctl --user unmask $PW 2>/dev/null
    systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service \
                           pipewire.socket pipewire-pulse.socket 2>/dev/null
}
_pw_off(){
    systemctl --user stop $PW 2>/dev/null
    systemctl --user mask $PW 2>/dev/null
}

# Always re-mask on the way out, even if the session is interrupted.
trap _pw_off EXIT INT TERM

_pw_on
/usr/bin/startx "$@"   # blocks until the desktop session ends, then trap re-masks
