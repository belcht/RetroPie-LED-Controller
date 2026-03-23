#!/usr/bin/env python3
"""
led-joy2key.py — Minimal joystick-to-keyboard daemon for dialog menus.

Maps joystick axes to arrow keys and buttons to Enter/Escape.
Fires only on threshold crossing (not while held) to prevent double steps.
Forks into background immediately so the caller can continue.
Killed by name (pkill -f led-joy2key.py) when the dialog closes.

Usage: python3 led-joy2key.py [/dev/input/js0]
"""

import os, sys, struct, fcntl, termios, time

JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS   = 0x02
JS_EVENT_INIT   = 0x80

JS_MIN    = -32768
JS_MAX    =  32768
JS_THRESH = 0.75
JS_REP      = 0.15    # minimum seconds between button presses (debounce)
JS_AXIS_REP = 0.20    # minimum seconds between any axis key injection (global cooldown)

EVENT_FORMAT = 'IhBB'
EVENT_SIZE   = struct.calcsize(EVENT_FORMAT)

# Axis 0 = horizontal, Axis 1 = vertical
AXIS_KEYS = {
    (0, -1): '\x1b[D',  # left
    (0,  1): '\x1b[C',  # right
    (1, -1): '\x1b[A',  # up
    (1,  1): '\x1b[B',  # down
}

# Button 0 = confirm, Button 1 = cancel
BUTTON_KEYS = {
    0: '\r',    # Enter
    1: '\x1b',  # Escape
}

def inject(tty_fd, chars):
    for c in chars:
        fcntl.ioctl(tty_fd, termios.TIOCSTI, c)

def run(js_path, tty_fd):
    axis_prev = {}   # last direction per axis — only fire on threshold crossing
    axis_last = 0.0  # timestamp of last axis key injected — global cooldown
    btn_last  = {}   # timestamp of last button press for debounce

    try:
        fd = open(js_path, 'rb')
    except OSError:
        return

    while True:
        try:
            data = fd.read(EVENT_SIZE)
        except OSError:
            break
        if not data or len(data) < EVENT_SIZE:
            break

        js_time, js_value, js_type, js_number = struct.unpack(EVENT_FORMAT, data)

        if js_type & JS_EVENT_INIT:
            continue

        chars = None

        if js_type == JS_EVENT_BUTTON and js_value == 1:
            now = time.time()
            if now - btn_last.get(js_number, 0) > JS_REP:
                btn_last[js_number] = now
                chars = BUTTON_KEYS.get(js_number)

        elif js_type == JS_EVENT_AXIS:
            if js_value <= JS_MIN * JS_THRESH:
                direction = -1
            elif js_value >= JS_MAX * JS_THRESH:
                direction = 1
            else:
                direction = 0

            prev = axis_prev.get(js_number, 0)
            axis_prev[js_number] = direction

            # Only fire when crossing INTO the threshold, not while held,
            # and respect global cooldown to suppress duplicate axis reports
            now = time.time()
            if direction != 0 and direction != prev and now - axis_last > JS_AXIS_REP:
                chars = AXIS_KEYS.get((js_number, direction))
                if chars:
                    axis_last = now

        if chars:
            inject(tty_fd, chars)

    fd.close()

def main():
    js_path = sys.argv[1] if len(sys.argv) > 1 else '/dev/input/js0'

    try:
        tty_fd = os.open('/dev/tty', os.O_WRONLY)
    except OSError:
        print("led-joy2key: cannot open /dev/tty", file=sys.stderr)
        sys.exit(1)

    # Fork — parent exits immediately so the caller continues
    if os.fork():
        os._exit(0)

    run(js_path, tty_fd)
    os.close(tty_fd)

if __name__ == '__main__':
    main()
