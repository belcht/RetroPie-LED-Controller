#!/usr/bin/env python3
"""
led-joy2key.py — Minimal joystick-to-keyboard daemon for dialog menus.

Uses /dev/uinput to generate real keyboard events, identical to a physical
keyboard press. This ensures correct single-step navigation in ncurses/dialog
without TIOCSTI artifacts.

Forks into background immediately so the caller can continue.
Killed by name (pkill -f led-joy2key.py) when the dialog closes.

Usage: python3 led-joy2key.py [/dev/input/js0]
"""

import os, sys, struct, fcntl, time

# ── Joystick event constants ──────────────────────────────────────────────────
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS   = 0x02
JS_EVENT_INIT   = 0x80

JS_MIN      = -32768
JS_MAX      =  32768
JS_THRESH   = 0.75
JS_AXIS_REP = 0.20   # global axis cooldown (seconds)
JS_BTN_REP  = 0.15   # button debounce (seconds)

JS_EVENT_FORMAT = 'IhBB'
JS_EVENT_SIZE   = struct.calcsize(JS_EVENT_FORMAT)

# ── uinput constants ──────────────────────────────────────────────────────────
UINPUT_PATH = '/dev/uinput'

UI_SET_EVBIT  = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

EV_SYN = 0
EV_KEY = 1
SYN_REPORT = 0

KEY_UP    = 103
KEY_DOWN  = 108
KEY_LEFT  = 105
KEY_RIGHT = 106
KEY_ENTER = 28   # KEY_ENTER (Return)
KEY_ESC   = 1

# struct input_event: timeval (2 × long) + type (u16) + code (u16) + value (s32)
# On 64-bit ARM (Pi 5): long = 8 bytes → total 24 bytes
INPUT_EVENT = struct.Struct('llHHi')

# ── Key mappings ──────────────────────────────────────────────────────────────
# Axis 0 = horizontal, Axis 1 = vertical
AXIS_KEYS = {
    (0, -1): KEY_LEFT,
    (0,  1): KEY_RIGHT,
    (1, -1): KEY_UP,
    (1,  1): KEY_DOWN,
}

# Button IDs from ES input config (es_input.cfg id= field):
#   "a" (confirm) = id 11, "b" (back) = id 10
BUTTON_KEYS = {
    11: KEY_ENTER,   # "a" button — confirm
    10: KEY_ESC,     # "b" button — back/cancel
}


def open_uinput():
    try:
        fd = os.open(UINPUT_PATH, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return None

    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    for key in [KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_ESC]:
        fcntl.ioctl(fd, UI_SET_KEYBIT, key)

    # struct uinput_user_dev:
    #   name[80] + id{bus,vendor,product,version}(4×u16) + ff_effects_max(u32)
    #   + absmax[64] + absmin[64] + absfuzz[64] + absflat[64]  (each 64×s32)
    udev = struct.pack('80sHHHHI' + 'i' * 256,
                       b'led-joy2key', 0, 0, 0, 0, 0, *([0] * 256))
    os.write(fd, udev)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.2)  # allow kernel to register the device
    return fd


def close_uinput(fd):
    try:
        fcntl.ioctl(fd, UI_DEV_DESTROY)
    except Exception:
        pass
    os.close(fd)


def send_key(uinput_fd, keycode):
    t = time.time()
    sec = int(t)
    usec = int((t % 1) * 1_000_000)
    press   = INPUT_EVENT.pack(sec, usec, EV_KEY, keycode, 1)
    syn     = INPUT_EVENT.pack(sec, usec, EV_SYN, SYN_REPORT, 0)
    release = INPUT_EVENT.pack(sec, usec, EV_KEY, keycode, 0)
    os.write(uinput_fd, press + syn + release + syn)


def run(js_path, uinput_fd):
    axis_prev = {}
    axis_last = 0.0
    btn_last  = {}

    try:
        fd = open(js_path, 'rb')
    except OSError:
        return

    while True:
        try:
            data = fd.read(JS_EVENT_SIZE)
        except OSError:
            break
        if not data or len(data) < JS_EVENT_SIZE:
            break

        js_time, js_value, js_type, js_number = struct.unpack(JS_EVENT_FORMAT, data)

        if js_type & JS_EVENT_INIT:
            continue

        keycode = None

        if js_type == JS_EVENT_BUTTON and js_value == 1:
            now = time.time()
            if now - btn_last.get(js_number, 0) > JS_BTN_REP:
                btn_last[js_number] = now
                keycode = BUTTON_KEYS.get(js_number)

        elif js_type == JS_EVENT_AXIS:
            if js_value <= JS_MIN * JS_THRESH:
                direction = -1
            elif js_value >= JS_MAX * JS_THRESH:
                direction = 1
            else:
                direction = 0

            prev = axis_prev.get(js_number, 0)
            axis_prev[js_number] = direction

            now = time.time()
            if direction != 0 and direction != prev and now - axis_last > JS_AXIS_REP:
                keycode = AXIS_KEYS.get((js_number, direction))
                if keycode:
                    axis_last = now

        if keycode is not None:
            send_key(uinput_fd, keycode)

    fd.close()


def main():
    js_path = sys.argv[1] if len(sys.argv) > 1 else '/dev/input/js0'

    uinput_fd = open_uinput()
    if uinput_fd is None:
        print("led-joy2key: cannot open /dev/uinput", file=sys.stderr)
        sys.exit(1)

    # Fork — parent exits immediately so the caller continues
    if os.fork():
        os._exit(0)

    try:
        run(js_path, uinput_fd)
    finally:
        close_uinput(uinput_fd)


if __name__ == '__main__':
    main()
