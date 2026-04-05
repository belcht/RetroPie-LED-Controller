#!/usr/bin/env python3
"""
mock-service.py — Simulates LEDControl.py WebSocket server for local testing.
Run this on your Mac alongside retro-led.py to test the UI without hardware.

Usage:
    python3 retro-led/mock-service.py [--leds N]
"""

import asyncio
import json
import math
import random
import sys
import time
import argparse
import websockets

HOST = "127.0.0.1"
PORT = 8765

# ── State ─────────────────────────────────────────────────────────────────────
clients  = set()
animate  = 'kitt'
color    = (255, 0, 0)   # red default
brightness = 0.8
num_leds = 14
t        = 0.0           # animation clock

COLOR_MAP = {
    'red':    (255,   0,   0),
    'green':  (  0, 255,   0),
    'blue':   (  0,   0, 255),
    'white':  (255, 255, 255),
    'yellow': (255, 255,   0),
    'purple': (128,   0, 128),
    'cyan':   (  0, 255, 255),
    'orange': (255, 100,   0),
    'pink':   (255,  20, 147),
    'off':    (  0,   0,   0),
}

def dim(c, factor):
    return tuple(int(v * factor) for v in c)

def wheel(pos):
    pos = pos & 255
    if pos < 85:   return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170: pos -= 85; return (255 - pos * 3, 0, pos * 3)
    else:           pos -= 170; return (0, pos * 3, 255 - pos * 3)

# ── Animations ────────────────────────────────────────────────────────────────

def frame_kitt(t):
    tail = 6
    speed = 0.04
    total = (num_leds + tail * 2) * 2
    step  = int(t / speed) % total
    if step < num_leds + tail * 2:
        pos = step - tail + 1
    else:
        pos = (num_leds + tail * 2) * 2 - step + 1 - tail
    pixels = [(0, 0, 0)] * num_leds
    for i in range(tail):
        idx = pos - i
        if 0 <= idx < num_leds:
            b = 1.0 - (i / (tail - 1)) if tail > 1 else 1.0
            pixels[idx] = dim(color, b * brightness)
    return pixels

def frame_cylon(t):
    speed = 0.04
    period = (num_leds - 2) * 2
    phase  = (t / speed) % period
    eye_w  = 3 if num_leds % 2 == 1 else 4
    half   = eye_w / 2.0
    if phase < period / 2:
        pos = 1 + phase * (num_leds - 3) / (period / 2 - 1) if period > 2 else 1
    else:
        pos = num_leds - 2 - (phase - period / 2) * (num_leds - 3) / (period / 2 - 1) if period > 2 else 1
    pixels = [dim(color, 0.3 * brightness)] * num_leds
    pixels[0]           = dim(color, 0.3 * brightness)
    pixels[num_leds - 1] = dim(color, 0.3 * brightness)
    for i in range(num_leds):
        dist = abs(i - pos)
        if dist < half:
            intensity = 1.0 - (dist / half)
            pixels[i] = dim(color, intensity * brightness)
    return pixels

def frame_glow(t):
    dur = 1.0
    phase = (t % (dur * 2)) / dur
    if phase < 1.0:
        b = 0.5 + 0.5 * phase
    else:
        b = 0.5 + 0.5 * (2.0 - phase)
    c = dim(color, b * brightness)
    return [c] * num_leds

def frame_centerpulse(t):
    even      = (num_leds % 2 == 0)
    center_l  = num_leds // 2 - 1 if even else num_leds // 2
    center_r  = num_leds // 2
    max_rad   = num_leds // 2 - (1 if even else 0)
    period    = 0.04 * (max_rad + 1) + 0.2
    phase     = (t % (period * 2)) / period
    radius    = int(phase * max_rad) if phase < 1.0 else int((2.0 - phase) * max_rad)
    pixels    = [(0, 0, 0)] * num_leds
    for side in range(radius + 1):
        il = center_l - side
        ir = center_r + side
        b  = 1.0 - (side / max(max_rad, 1)) * 0.5
        c  = dim(color, b * brightness)
        if 0 <= il < num_leds: pixels[il] = c
        if 0 <= ir < num_leds: pixels[ir] = c
    return pixels

def frame_rainbow(t):
    speed = 0.02
    j = int(t / speed) % 256
    return [dim(wheel((i * 256 // num_leds + j) & 255), brightness) for i in range(num_leds)]

def frame_meteor(t):
    speed = 0.05
    tail  = 8
    period = (num_leds + tail) * speed
    pos   = (t % period) / speed - tail
    pixels = [(0, 0, 0)] * num_leds
    for i in range(tail):
        idx = int(pos) - i
        if 0 <= idx < num_leds:
            b = (1.0 - i / tail) * brightness
            pixels[idx] = dim(color, b)
    return pixels

def frame_twinkle(t, state):
    """state is a mutable list of sparkle dicts."""
    num_sparkles = 5
    fade_speed   = 0.04
    active = sum(1 for s in state if s is not None)
    if active < num_sparkles:
        idx = random.randint(0, num_leds - 1)
        if state[idx] is None:
            f = random.uniform(0.7, 1.0)
            state[idx] = {
                'bright': random.uniform(0.6, 1.0),
                'color': dim(color, f),
            }
    pixels = [(0, 0, 0)] * num_leds
    for i in range(num_leds):
        if state[i]:
            s = state[i]
            pixels[i] = dim(s['color'], s['bright'] * brightness)
            s['bright'] -= fade_speed
            if s['bright'] <= 0:
                state[i] = None
    return pixels

def frame_cycle(t):
    colors_list = [v for k, v in COLOR_MAP.items() if k != 'off']
    period = 10.0
    idx    = int(t / period) % len(colors_list)
    nxt    = (idx + 1) % len(colors_list)
    phase  = (t % period) / period
    if phase > 0.85:
        p   = (phase - 0.85) / 0.15
        cur = colors_list[idx]
        nxt = colors_list[nxt]
        c   = tuple(int(cur[j] * (1 - p) + nxt[j] * p) for j in range(3))
    else:
        c = colors_list[idx]
    return [dim(c, brightness)] * num_leds

def frame_solid():
    return [dim(color, brightness)] * num_leds

def frame_off():
    return [(0, 0, 0)] * num_leds

# ── WebSocket server ──────────────────────────────────────────────────────────

async def handler(websocket):
    clients.add(websocket)
    print(f"  Client connected  ({len(clients)} total)")
    try:
        async for message in websocket:
            try:
                cmd = json.loads(message)
                await handle_command(cmd)
            except Exception as e:
                print(f"  Bad message: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"  Client disconnected ({len(clients)} total)")

async def handle_command(cmd):
    global animate, color, brightness
    if cmd.get('cmd') == 'set':
        new_anim  = cmd.get('animate', animate)
        new_color = cmd.get('color',   'red')
        new_bright= cmd.get('brightness', brightness)
        save      = cmd.get('save', False)
        animate   = new_anim
        color     = COLOR_MAP.get(new_color, (255, 255, 255))
        brightness= float(new_bright)
        action = "SAVED" if save else "preview"
        print(f"  [{action}] animate={animate!r:12s}  color={new_color!r:8s}  brightness={brightness:.0%}")

async def broadcast_loop():
    global t
    twinkle_state = [None] * num_leds
    last = time.monotonic()

    while True:
        now  = time.monotonic()
        dt   = now - last
        last = now
        t   += dt

        if animate == 'kitt':        pixels = frame_kitt(t)
        elif animate == 'cylon':     pixels = frame_cylon(t)
        elif animate == 'glow':      pixels = frame_glow(t)
        elif animate == 'centerpulse': pixels = frame_centerpulse(t)
        elif animate == 'rainbow':   pixels = frame_rainbow(t)
        elif animate == 'meteor':    pixels = frame_meteor(t)
        elif animate == 'twinkle':   pixels = frame_twinkle(t, twinkle_state)
        elif animate == 'cycle':     pixels = frame_cycle(t)
        elif animate == 'off':       pixels = frame_off()
        else:                        pixels = frame_solid()

        if clients:
            msg = json.dumps({"type": "pixels", "data": pixels})
            websockets.broadcast(clients, msg)

        await asyncio.sleep(0.033)  # ~30fps

async def main():
    print(f"RetroLED mock service  —  {num_leds} LEDs  —  ws://{HOST}:{PORT}")
    print(f"Initial state: animate={animate!r}  color=red  brightness={brightness:.0%}")
    print("Waiting for RetroLED to connect...\n")
    async with websockets.serve(handler, HOST, PORT):
        await broadcast_loop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RetroLED mock LED service')
    parser.add_argument('--leds', type=int, default=14, help='Number of LEDs to simulate')
    args = parser.parse_args()
    num_leds = args.leds
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMock service stopped.")
