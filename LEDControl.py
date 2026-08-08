from rpi5_ws2812.ws2812 import WS2812SpiDriver, Color
import argparse
import signal
import time
import random
import sys
import re
from pathlib import Path
import tomllib
import threading
import queue

# Optional WebSocket support — prefer system install, fall back to vendored copy
import sys as _sys
from pathlib import Path as _Path
_vendor = _Path(__file__).parent / 'retro-led' / 'vendor'
if _vendor.exists() and str(_vendor) not in _sys.path:
    _sys.path.insert(0, str(_vendor))

try:
    import asyncio
    import websockets
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False
    print("websockets not available — RetroLED visualization disabled", file=sys.stderr)

# === Module-level config (overwritten from config/CLI in main) ===
NUM_LEDS = 14
SPI_BUS = 0
SPI_DEVICE = 0
global_brightness = 1.0

MAX_LEDS = 21  # power-safety clamp for the Pi 5V rail; to run a longer strip, raise this manually AND power it from an external 5V supply

COLOR_MAP = {
    'red':    Color(255, 0, 0),
    'green':  Color(0, 255, 0),
    'blue':   Color(0, 0, 255),
    'white':  Color(255, 255, 255),
    'yellow': Color(255, 255, 0),
    'purple': Color(128, 0, 128),
    'cyan':   Color(0, 255, 255),
    'orange': Color(255, 100, 0),
    'pink':   Color(255, 20, 147),
    'off':    Color(0, 0, 0),
}

# === Signal handling — systemd sends SIGTERM, not SIGINT ===
# _Shutdown subclasses BaseException (not Exception) so the per-animation
# `except (KeyboardInterrupt, SystemExit)` / `except Exception` handlers can't
# swallow it. It propagates straight to main()'s `finally`, which blanks the
# strip and exits cleanly. (If we raise SystemExit here it gets caught
# mid-animation, main()'s `while True` restarts the animation, the process
# never exits, and systemd SIGKILLs us — LEDs never blank, reboots stall, and
# leds-off.service times out waiting on us.)
class _Shutdown(BaseException):
    pass

def _handle_signal(sig, frame):
    raise _Shutdown()

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ────────────────────────────────────────────────
# WebSocket server
# ────────────────────────────────────────────────

# Bounded so a dead consumer (e.g. WS thread crashed on a port conflict) can't
# eat memory forever — only the latest frame matters anyway.
_ws_pixel_queue = queue.Queue(maxsize=4)   # main thread writes, asyncio reads
_ws_command_queue = queue.SimpleQueue()    # asyncio writes, main thread reads
_ws_clients = set()
WS_PORT = 8765

class AnimationSwitch(Exception):
    """Raised by check_commands() to switch animation mid-loop."""
    def __init__(self, animate: str, color: str, save: bool = False, brightness: float = None,
                 system: str = None, clear: bool = False):
        self.animate = animate
        self.color = color
        self.save = save
        self.brightness = brightness
        self.system = system    # if set, a save targets [systems].<system> not [general]
        self.clear = clear      # with system+save: remove that override (revert to default)

def broadcast_pixels(strip):
    """Capture current strip state and queue for WebSocket broadcast."""
    if not WS_ENABLED:
        return
    try:
        pixels = [[strip._pixels[i].r, strip._pixels[i].g, strip._pixels[i].b]
                  for i in range(NUM_LEDS)]
        _ws_pixel_queue.put_nowait(pixels)
    except queue.Full:
        # Consumer is behind or the WS thread has died — drop this frame.
        pass
    except Exception:
        pass

def check_commands():
    """Check for incoming WebSocket commands. Raises AnimationSwitch if one arrived."""
    if not WS_ENABLED:
        return
    try:
        cmd = _ws_command_queue.get_nowait()
    except queue.Empty:
        return
    if cmd.get('cmd') == 'set':
        raise AnimationSwitch(
            cmd.get('animate', ''),
            cmd.get('color', 'white'),
            cmd.get('save', False),
            cmd.get('brightness', None),
            cmd.get('system', None),
            cmd.get('clear', False),
        )

def _update(filepath, section, key, value):
    """Surgically set `key = value` inside [section] (add/replace; create section if needed).
    Preserves user comments and other keys — do not replace with a full TOML dump."""
    with open(filepath, 'r') as f:
        content = f.read()
    section_re = re.compile(r'(\[' + re.escape(section) + r'\].*?)(?=\n\[|\Z)', re.DOTALL)
    key_re = re.compile(r'^' + re.escape(key) + r'\s*=.*$', re.MULTILINE)
    match = section_re.search(content)
    if match:
        sec = match.group(1)
        new_sec = key_re.sub(lambda _: f'{key} = {value}', sec) if key_re.search(sec) \
                  else sec.rstrip('\n') + f'\n{key} = {value}'
        content = content[:match.start()] + new_sec + content[match.end():]
    else:
        content = content.rstrip('\n') + f'\n\n[{section}]\n{key} = {value}\n'
    with open(filepath, 'w') as f:
        f.write(content)

def _remove_key(filepath, section, key):
    """Delete the `key = ...` line inside [section] (no-op if absent)."""
    with open(filepath, 'r') as f:
        content = f.read()
    section_re = re.compile(r'(\[' + re.escape(section) + r'\].*?)(?=\n\[|\Z)', re.DOTALL)
    match = section_re.search(content)
    if not match:
        return
    sec = re.sub(r'^' + re.escape(key) + r'\s*=.*\n?', '', match.group(1), flags=re.MULTILINE)
    content = content[:match.start()] + sec + content[match.end():]
    with open(filepath, 'w') as f:
        f.write(content)

def _save_config(config_path: Path, animate: str, color: str, brightness: float = None):
    """Write the GLOBAL default animation/color/brightness back to [general]."""
    try:
        _update(config_path, 'general', 'default_animate', f'"{animate}"')
        _update(config_path, 'general', 'default_color', f'"{color}"')
        if brightness is not None:
            _update(config_path, 'general', 'global_brightness', str(round(brightness, 2)))
        print(f"Config saved: animate={animate} color={color}" +
              (f" brightness={brightness}" if brightness is not None else ""))
    except Exception as e:
        print(f"Failed to save config: {e}", file=sys.stderr)

def _save_system(config_path: Path, system: str, animate: str, color: str):
    """Write a per-system override: [systems].<system> = { animate, color }."""
    try:
        _update(config_path, 'systems', system, f'{{ animate = "{animate}", color = "{color}" }}')
        print(f"Config saved: systems.{system} = {{ animate={animate} color={color} }}")
    except Exception as e:
        print(f"Failed to save system config: {e}", file=sys.stderr)

def _clear_system(config_path: Path, system: str):
    """Remove a per-system override so the system falls back to the default."""
    try:
        _remove_key(config_path, 'systems', system)
        print(f"Config cleared: systems.{system} (now uses default)")
    except Exception as e:
        print(f"Failed to clear system config: {e}", file=sys.stderr)

if WS_ENABLED:
    async def _ws_handler(websocket):
        _ws_clients.add(websocket)
        try:
            async for message in websocket:
                try:
                    _ws_command_queue.put(json.loads(message))
                except Exception:
                    pass
        finally:
            _ws_clients.discard(websocket)

    async def _pixel_broadcast_task():
        while True:
            await asyncio.sleep(0.016)  # ~60 fps broadcast cap
            latest = None
            while not _ws_pixel_queue.empty():
                try:
                    latest = _ws_pixel_queue.get_nowait()
                except Exception:
                    break
            if latest and _ws_clients:
                try:
                    msg = json.dumps({"type": "pixels", "data": latest})
                    websockets.broadcast(_ws_clients, msg)
                except Exception:
                    pass

    async def _ws_main():
        async with websockets.serve(_ws_handler, "127.0.0.1", WS_PORT):
            print(f"WebSocket server listening on ws://127.0.0.1:{WS_PORT}")
            await _pixel_broadcast_task()

    def _ws_thread_main():
        try:
            import json as _json
            globals()['json'] = _json
            asyncio.run(_ws_main())
        except Exception as e:
            print(f"WebSocket server error: {e}", file=sys.stderr)

    # Thread is started by main() so --once can skip it
    import json
else:
    import json

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def limited_color(color: Color) -> Color:
    if global_brightness >= 1.0:
        return color
    return Color(
        int(color.r * global_brightness),
        int(color.g * global_brightness),
        int(color.b * global_brightness)
    )

def set_pixel(strip, idx: int, color: Color):
    strip._pixels[idx] = color

def parse_hex_color(hex_str: str) -> Color:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        raise ValueError(f"Expected 6 hex digits, got: {hex_str!r}")
    return Color(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

def wheel(pos: int) -> Color:
    pos = pos & 255
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

# ────────────────────────────────────────────────
# System/ROM lookup (runcommand integration)
# ────────────────────────────────────────────────

def resolve_for_system(system: str, rom_path: str | None, config: dict) -> tuple[str, str]:
    if rom_path:
        rom_stem = Path(rom_path).stem.lower()
        for rom_name, settings in config.get('roms', {}).items():
            if rom_name.lower() == rom_stem:
                return settings.get('animate', ''), settings.get('color', 'white')
    systems = config.get('systems', {})
    if system and system in systems:
        s = systems[system]
        return s.get('animate', ''), s.get('color', 'white')
    default = systems.get('default', {})
    gen = config.get('general', {})
    return (
        default.get('animate', gen.get('default_animate', '')),
        default.get('color', gen.get('default_color', 'white'))
    )

# ────────────────────────────────────────────────
# Config loader
# ────────────────────────────────────────────────

def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        print(f"Config file not found: {config_path} — using defaults")
        return {}
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        print(f"Loaded config from {config_path}")
        return config
    except Exception as e:
        # Don't silently fall back — running with defaults (num_leds=14 etc.)
        # when the user has a real config is more confusing than crashing.
        bar = "=" * 60
        print(bar, file=sys.stderr)
        print(f"FATAL: Failed to parse {config_path}", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        print("Fix the syntax error, or delete the file to use defaults.", file=sys.stderr)
        print(bar, file=sys.stderr)
        sys.exit(1)

# ────────────────────────────────────────────────
# Animations
# ────────────────────────────────────────────────

def run_kitt(strip, chase_color, config: dict):
    c = config.get('kitt', {})
    tail_length = max(2, c.get('tail_length', 6))   # divide-by-zero guard
    base_speed = c.get('base_speed', 0.04)
    print(f"KITT | color:{chase_color} tail:{tail_length} speed:{base_speed}")
    off = Color(0, 0, 0)
    strip.set_all_pixels(off)
    strip.show()
    try:
        while True:
            for pos in range(-tail_length + 1, NUM_LEDS + tail_length):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        set_pixel(strip, idx, limited_color(Color(
                            int(chase_color.r * brightness),
                            int(chase_color.g * brightness),
                            int(chase_color.b * brightness),
                        )))
                strip.show()
                broadcast_pixels(strip)
                time.sleep(base_speed)
                check_commands()
            for pos in range(NUM_LEDS + tail_length - 2, -tail_length, -1):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        set_pixel(strip, idx, limited_color(Color(
                            int(chase_color.r * brightness),
                            int(chase_color.g * brightness),
                            int(chase_color.b * brightness),
                        )))
                strip.show()
                broadcast_pixels(strip)
                time.sleep(base_speed)
                check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nKITT stopped")
        strip.set_all_pixels(off)
        strip.show()

def run_cylon(strip, color, config: dict):
    c = config.get('cylon', {})
    speed     = c.get('speed', 0.04)
    min_stare = c.get('min_stare', 0.5)
    max_stare = c.get('max_stare', 3.0)
    eye_width = 3 if NUM_LEDS % 2 == 1 else 4
    off = Color(0, 0, 0)
    print(f"Cylon | eye_width:{eye_width} speed:{speed} stare:{min_stare}-{max_stare}s")
    end_color = limited_color(Color(int(color.r * 0.3), int(color.g * 0.3), int(color.b * 0.3)))
    left_bound  = 1
    right_bound = NUM_LEDS - 2
    half = eye_width / 2.0

    def draw_eye(pos):
        strip.set_all_pixels(off)
        set_pixel(strip, 0, end_color)
        set_pixel(strip, NUM_LEDS - 1, end_color)
        for i in range(NUM_LEDS):
            dist = abs(i - pos)
            if dist < half:
                intensity = 1.0 - (dist / half)
                set_pixel(strip, i, limited_color(Color(
                    int(color.r * intensity), int(color.g * intensity), int(color.b * intensity),
                )))
        strip.show()
        broadcast_pixels(strip)

    try:
        while True:
            for pos in range(left_bound, right_bound + 1):
                draw_eye(pos)
                time.sleep(speed)
                check_commands()
            stare_pos = random.randint(left_bound, right_bound)
            for pos in range(right_bound, left_bound - 1, -1):
                draw_eye(pos)
                time.sleep(speed)
                check_commands()
                if pos == stare_pos:
                    stare_dur = random.uniform(min_stare, max_stare)
                    stare_end = time.monotonic() + stare_dur
                    while time.monotonic() < stare_end:
                        time.sleep(0.05)
                        check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nCylon stopped")
        strip.set_all_pixels(off)
        strip.show()

def run_glow(strip, base_color, config: dict):
    c = config.get('glow', {})
    min_b = c.get('min_brightness', 0.5)
    max_b = c.get('max_brightness', 1.0)
    dur = c.get('duration', 1.0)
    print(f"Glow | min:{min_b} max:{max_b} dur:{dur}s")
    num_steps = 20
    try:
        while True:
            for step in range(num_steps + 1):
                b = min_b + (max_b - min_b) * (step / num_steps)
                strip.set_all_pixels(limited_color(Color(
                    int(base_color.r * b), int(base_color.g * b), int(base_color.b * b)
                )))
                strip.show()
                broadcast_pixels(strip)
                time.sleep(dur / num_steps)
                check_commands()
            for step in range(num_steps + 1):
                b = max_b - (max_b - min_b) * (step / num_steps)
                strip.set_all_pixels(limited_color(Color(
                    int(base_color.r * b), int(base_color.g * b), int(base_color.b * b)
                )))
                strip.show()
                broadcast_pixels(strip)
                time.sleep(dur / num_steps)
                check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nGlow stopped")

def run_centerpulse(strip, base_color, config: dict):
    c = config.get('centerpulse', {})
    base_speed = c.get('base_speed', 0.04)
    pause_at_full = c.get('pause_at_full', 0.2)
    print(f"CenterPulse | speed:{base_speed} pause:{pause_at_full}s")
    off = Color(0, 0, 0)
    full_color = limited_color(base_color)
    # For odd strips: single center LED (e.g. 14 LEDs → center=6.5, inner pair: 6 and 7)
    # For even strips: two center LEDs light together at side=0
    even = (NUM_LEDS % 2 == 0)
    # left/right anchors for side=0
    center_l = NUM_LEDS // 2 - 1 if even else NUM_LEDS // 2
    center_r = NUM_LEDS // 2
    max_radius = NUM_LEDS // 2 - (1 if even else 0)

    def lit_indices(side):
        """Return (left_idx, right_idx) for a given side offset."""
        return center_l - side, center_r + side

    try:
        while True:
            for radius in range(0, max_radius + 1):
                strip.set_all_pixels(off)
                for side in range(radius + 1):
                    il, ir = lit_indices(side)
                    if 0 <= il < NUM_LEDS:
                        set_pixel(strip, il, full_color)
                    if 0 <= ir < NUM_LEDS:
                        set_pixel(strip, ir, full_color)
                strip.show()
                broadcast_pixels(strip)
                time.sleep(base_speed)
                check_commands()
            pause_end = time.monotonic() + pause_at_full
            while time.monotonic() < pause_end:
                time.sleep(0.02)
                check_commands()
            for radius in range(max_radius, -1, -1):
                strip.set_all_pixels(off)
                for side in range(radius + 1):
                    il, ir = lit_indices(side)
                    brightness = 1.0 - (side / max(max_radius, 1)) if side > 0 else 1.0
                    c_dim = limited_color(Color(
                        int(base_color.r * brightness),
                        int(base_color.g * brightness),
                        int(base_color.b * brightness),
                    ))
                    if 0 <= il < NUM_LEDS:
                        set_pixel(strip, il, c_dim)
                    if 0 <= ir < NUM_LEDS:
                        set_pixel(strip, ir, c_dim)
                strip.show()
                broadcast_pixels(strip)
                time.sleep(base_speed)
                check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nCenterPulse stopped")
        strip.set_all_pixels(off)
        strip.show()

def run_cycle(strip, config: dict, cycle_duration=None, fade_time=None, fade_enabled=None):
    c = config.get('cycle', {})
    cycle_duration = cycle_duration if cycle_duration is not None else c.get('cycle_duration', 10.0)
    fade_time = fade_time if fade_time is not None else c.get('fade_time', 1.5)
    fade_enabled = fade_enabled if fade_enabled is not None else c.get('fade_enabled', True)
    color_names = c.get('colors', None)
    if color_names:
        colors_list = [COLOR_MAP[n] for n in color_names if n in COLOR_MAP]
    else:
        colors_list = [v for k, v in COLOR_MAP.items() if k != 'off']
    print(f"Cycle | {len(colors_list)} colors, {cycle_duration}s each, crossfade:{fade_enabled}")
    current_idx = 0
    try:
        while True:
            next_idx = (current_idx + 1) % len(colors_list)
            cur = colors_list[current_idx]
            nxt = colors_list[next_idx]
            strip.set_all_pixels(limited_color(cur))
            strip.show()
            broadcast_pixels(strip)
            hold = max(0, cycle_duration - fade_time)
            hold_end = time.monotonic() + hold
            while time.monotonic() < hold_end:
                time.sleep(0.05)
                check_commands()
            if fade_enabled and fade_time > 0:
                steps = 30
                for s in range(steps + 1):
                    p = s / steps
                    r = int(cur.r * (1 - p) + nxt.r * p)
                    g = int(cur.g * (1 - p) + nxt.g * p)
                    b = int(cur.b * (1 - p) + nxt.b * p)
                    strip.set_all_pixels(limited_color(Color(r, g, b)))
                    strip.show()
                    broadcast_pixels(strip)
                    time.sleep(fade_time / steps)
                    check_commands()
            else:
                time.sleep(fade_time)
                check_commands()
            current_idx = next_idx
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nCycle stopped")

def run_rainbow(strip, config: dict):
    speed = config.get('rainbow', {}).get('speed', 0.02)
    print(f"Rainbow | speed:{speed}")
    j = 0
    try:
        while True:
            for i in range(NUM_LEDS):
                set_pixel(strip, i, limited_color(wheel((i * 256 // NUM_LEDS + j) & 255)))
            strip.show()
            broadcast_pixels(strip)
            j = (j + 1) % 256
            time.sleep(speed)
            check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nRainbow stopped")

def run_meteor(strip, color, config: dict):
    c = config.get('meteor', {})
    tail_length = max(1, c.get('tail_length', 8))   # divide-by-zero guard
    speed = c.get('speed', 0.05)
    print(f"Meteor | tail:{tail_length} speed:{speed}")
    off = Color(0, 0, 0)
    try:
        while True:
            for pos in range(-tail_length, NUM_LEDS):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / tail_length)
                        set_pixel(strip, idx, limited_color(Color(
                            int(color.r * brightness),
                            int(color.g * brightness),
                            int(color.b * brightness),
                        )))
                strip.show()
                broadcast_pixels(strip)
                time.sleep(speed)
                check_commands()
            time.sleep(0.5)
            check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nMeteor stopped")

def run_twinkle(strip, base_color, config: dict):
    c = config.get('twinkle', {})
    num_sparkles = c.get('num_sparkles', 5)
    fade_speed = c.get('fade_speed', 0.04)
    print(f"Twinkle | sparkles:{num_sparkles} fade:{fade_speed}")
    sparkles = [None] * NUM_LEDS
    try:
        while True:
            active = sum(1 for x in sparkles if x is not None)
            if active < num_sparkles:
                idx = random.randint(0, NUM_LEDS - 1)
                if sparkles[idx] is None:
                    rand_factor = random.uniform(0.7, 1.0)
                    col = Color(
                        int(base_color.r * rand_factor),
                        int(base_color.g * rand_factor),
                        int(base_color.b * rand_factor)
                    )
                    sparkles[idx] = {'bright': random.uniform(0.6, 1.0), 'color': col}
            strip.set_all_pixels(Color(0, 0, 0))
            for i in range(NUM_LEDS):
                if sparkles[i]:
                    s = sparkles[i]
                    set_pixel(strip, i, limited_color(Color(
                        int(s['color'].r * s['bright']),
                        int(s['color'].g * s['bright']),
                        int(s['color'].b * s['bright']),
                    )))
                    s['bright'] -= fade_speed
                    if s['bright'] <= 0:
                        sparkles[i] = None
            strip.show()
            broadcast_pixels(strip)
            time.sleep(0.05)
            check_commands()
    except AnimationSwitch:
        raise
    except (KeyboardInterrupt, SystemExit):
        print("\nTwinkle stopped")

# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

def main():
    global NUM_LEDS, SPI_BUS, SPI_DEVICE, global_brightness

    parser = argparse.ArgumentParser(description='WS2812B LED control on Raspberry Pi 5')
    parser.add_argument('--config', type=Path, default=Path.home() / 'ledcontrol.toml')
    parser.add_argument('--color', '-color', default=None)
    parser.add_argument('--animate', '-animate',
                        choices=['kitt', 'cylon', 'glow', 'centerpulse', 'cycle', 'rainbow', 'meteor', 'twinkle', 'off'],
                        default=None)
    parser.add_argument('--global-brightness', type=float, default=None)
    parser.add_argument('--min-brightness', type=float, default=None)
    parser.add_argument('--max-brightness', type=float, default=None)
    parser.add_argument('--duration', type=float, default=None)
    parser.add_argument('--cycle-duration', type=float, default=None)
    parser.add_argument('--fade-time', type=float, default=None)
    parser.add_argument('--no-fade', action='store_true')
    parser.add_argument('--system', default=None)
    parser.add_argument('--rom', default=None)
    parser.add_argument('--once', action='store_true',
                        help='Set the requested state and exit (no animation loop, no WS server)')

    args = parser.parse_args()
    config = load_config(args.config)

    hw = config.get('hardware', {})
    NUM_LEDS = hw.get('num_leds', 14)
    SPI_BUS = hw.get('spi_bus', 0)
    SPI_DEVICE = hw.get('spi_device', 0)
    if NUM_LEDS > MAX_LEDS:
        print(f"Warning: num_leds={NUM_LEDS} exceeds MAX_LEDS={MAX_LEDS}. Clamping.", file=sys.stderr)
        NUM_LEDS = MAX_LEDS

    global_brightness = (
        args.global_brightness if args.global_brightness is not None
        else config.get('general', {}).get('global_brightness', 1.0)
    )
    global_brightness = max(0.0, min(1.0, global_brightness))
    print(f"Brightness:{global_brightness*100:.0f}%  LEDs:{NUM_LEDS}  SPI:{SPI_BUS}/{SPI_DEVICE}")

    gen = config.get('general', {})
    animate = gen.get('default_animate', '')
    color_arg = gen.get('default_color', 'white')

    if args.system is not None:
        sys_animate, sys_color = resolve_for_system(args.system, args.rom, config)
        if sys_animate: animate = sys_animate
        if sys_color: color_arg = sys_color
        print(f"System:{args.system}  →  animate:{animate}  color:{color_arg}")

    if args.animate: animate = args.animate
    if args.color: color_arg = args.color

    def parse_color(color_arg):
        if color_arg and color_arg.startswith('#'):
            return parse_hex_color(color_arg), color_arg
        return COLOR_MAP.get(color_arg, Color(255, 255, 255)), color_arg or 'white'

    try:
        color, color_name = parse_color(color_arg)
    except ValueError as e:
        print(f"Invalid hex color: {e}", file=sys.stderr)
        sys.exit(1)

    cycle_c = config.get('cycle', {})
    cycle_duration = args.cycle_duration if args.cycle_duration is not None else cycle_c.get('cycle_duration', 10.0)
    fade_time = 0.0 if args.no_fade else (args.fade_time if args.fade_time is not None else cycle_c.get('fade_time', 1.5))
    fade_enabled = not args.no_fade and cycle_c.get('fade_enabled', True)

    strip = WS2812SpiDriver(spi_bus=SPI_BUS, spi_device=SPI_DEVICE, led_count=NUM_LEDS).get_strip()

    # One-shot mode: set the strip and exit. Skips the WS server entirely so
    # this can run alongside a live service without fighting for port 8765.
    if args.once:
        if animate == 'off' or color_name == 'off':
            strip.set_all_pixels(Color(0, 0, 0))
        else:
            strip.set_all_pixels(limited_color(color))
        strip.show()
        print(f"One-shot: animate={animate} color={color_name} — exiting")
        return

    if WS_ENABLED:
        threading.Thread(target=_ws_thread_main, daemon=True).start()

    try:
        while True:
            try:
                if animate == 'off' or color_name == 'off':
                    print("LEDs off — waiting for commands")
                    strip.set_all_pixels(Color(0, 0, 0))
                    strip.show()
                    broadcast_pixels(strip)
                    while True:
                        time.sleep(0.1)
                        check_commands()
                elif animate == 'kitt':
                    run_kitt(strip, color, config)
                elif animate == 'cylon':
                    run_cylon(strip, color, config)
                elif animate == 'glow':
                    run_glow(strip, color, config)
                elif animate == 'centerpulse':
                    run_centerpulse(strip, color, config)
                elif animate == 'cycle':
                    run_cycle(strip, config, cycle_duration, fade_time, fade_enabled)
                elif animate == 'rainbow':
                    run_rainbow(strip, config)
                elif animate == 'meteor':
                    run_meteor(strip, color, config)
                elif animate == 'twinkle':
                    run_twinkle(strip, color, config)
                else:
                    print(f"Solid color: {color_name}")
                    strip.set_all_pixels(limited_color(color))
                    strip.show()
                    broadcast_pixels(strip)
                    while True:
                        time.sleep(0.1)
                        check_commands()

            except AnimationSwitch as sw:
                print(f"Switch → animate={sw.animate!r} color={sw.color!r} save={sw.save}"
                      + (f" system={sw.system!r}" if sw.system else "")
                      + (" clear" if sw.clear else ""))
                animate = sw.animate
                color_name = sw.color
                if sw.brightness is not None:
                    global_brightness = max(0.0, min(1.0, sw.brightness))
                try:
                    color, color_name = parse_color(color_name)
                except ValueError:
                    color = Color(255, 255, 255)
                    color_name = 'white'
                if sw.save:
                    if sw.system:
                        _clear_system(args.config, sw.system) if sw.clear \
                            else _save_system(args.config, sw.system, animate, color_name)
                    else:
                        _save_config(args.config, animate, color_name,
                                     sw.brightness if sw.brightness is not None else None)

    except (KeyboardInterrupt, SystemExit, _Shutdown):
        print("\nStopped")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        print("Turning off LEDs...")
        strip.set_all_pixels(Color(0, 0, 0))
        strip.show()

if __name__ == "__main__":
    main()
