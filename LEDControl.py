from rpi5_ws2812.ws2812 import WS2812SpiDriver, Color
import argparse
import signal
import time
import random
import sys
from pathlib import Path
import tomllib

# === Module-level config (overwritten from config/CLI in main) ===
NUM_LEDS = 14
SPI_BUS = 0
SPI_DEVICE = 0
global_brightness = 1.0

# Maximum LEDs when powered from the Pi 5V rail.
# Each WS2812 draws up to 60mA at full white; at 80% brightness that is ~48mA per LED.
# 20 LEDs x 48mA = ~960mA — safe headroom on any supply alongside a loaded Pi 5.
# If you are using an external 5V supply with common ground, raise this value freely.
MAX_LEDS = 20

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
def _handle_signal(sig, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# === Helpers ===

def limited_color(color: Color) -> Color:
    """Apply global brightness limit to a Color."""
    if global_brightness >= 1.0:
        return color
    return Color(
        int(color.r * global_brightness),
        int(color.g * global_brightness),
        int(color.b * global_brightness)
    )

def set_pixel(strip, idx: int, color: Color):
    """Set a single LED by index. rpi5-ws2812 has no public set_pixel, so _pixels is used."""
    strip._pixels[idx] = color

def parse_hex_color(hex_str: str) -> Color:
    """Parse a hex color string like '#FF8800' or 'FF8800' into a Color."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        raise ValueError(f"Expected 6 hex digits, got: {hex_str!r}")
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return Color(r, g, b)

def wheel(pos: int) -> Color:
    """Generate rainbow colors across 0–255."""
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
    """
    Return (animate, color_name) for a given system/rom.
    Lookup order: [roms] by filename stem → [systems.<system>] → [systems.default] → general defaults.
    """
    # 1. ROM-level match (filename without extension, case-insensitive)
    if rom_path:
        rom_stem = Path(rom_path).stem.lower()
        for rom_name, settings in config.get('roms', {}).items():
            if rom_name.lower() == rom_stem:
                return settings.get('animate', ''), settings.get('color', 'white')

    # 2. System-level match
    systems = config.get('systems', {})
    if system and system in systems:
        s = systems[system]
        return s.get('animate', ''), s.get('color', 'white')

    # 3. Default system entry
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
        print(f"Error loading config {config_path}: {e}", file=sys.stderr)
        return {}

# ────────────────────────────────────────────────
# Animations
# ────────────────────────────────────────────────

def run_kitt(strip, chase_color, config: dict):
    c = config.get('kitt', {})
    tail_length = c.get('tail_length', 6)
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
                        r = int(chase_color.r * brightness)
                        g = int(chase_color.g * brightness)
                        b = int(chase_color.b * brightness)
                        set_pixel(strip, idx, limited_color(Color(r, g, b)))
                strip.show()
                time.sleep(base_speed)
            for pos in range(NUM_LEDS + tail_length - 2, -tail_length, -1):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        r = int(chase_color.r * brightness)
                        g = int(chase_color.g * brightness)
                        b = int(chase_color.b * brightness)
                        set_pixel(strip, idx, limited_color(Color(r, g, b)))
                strip.show()
                time.sleep(base_speed)
    except (KeyboardInterrupt, SystemExit):
        print("\nKITT stopped")
    finally:
        strip.set_all_pixels(off)
        strip.show()

def run_cylon(strip, color, config: dict):
    c = config.get('cylon', {})
    eye_width = c.get('eye_width', 3)
    speed     = c.get('speed', 0.04)
    min_stare = c.get('min_stare', 0.5)
    max_stare = c.get('max_stare', 3.0)
    half = eye_width // 2
    off  = Color(0, 0, 0)
    print(f"Cylon | eye_width:{eye_width} speed:{speed} stare:{min_stare}-{max_stare}s")

    # End markers: always-on at 30% brightness to frame the strip
    end_color = limited_color(Color(
        int(color.r * 0.3),
        int(color.g * 0.3),
        int(color.b * 0.3),
    ))

    # Eye travels between the two end markers
    left_bound  = 1
    right_bound = NUM_LEDS - 2

    def draw_eye(pos):
        strip.set_all_pixels(off)
        set_pixel(strip, 0,           end_color)
        set_pixel(strip, NUM_LEDS - 1, end_color)
        for i in range(NUM_LEDS):
            dist = abs(i - pos)
            if dist <= half:
                intensity = 1.0 - (dist / (half + 1))
                set_pixel(strip, i, limited_color(Color(
                    int(color.r * intensity),
                    int(color.g * intensity),
                    int(color.b * intensity),
                )))
        strip.show()

    try:
        while True:
            # Roam left to right — "looking around"
            for pos in range(left_bound, right_bound + 1):
                draw_eye(pos)
                time.sleep(speed)

            # Pick a random spot to stare at on the return sweep
            stare_pos = random.randint(left_bound, right_bound)

            # Return right to left, pausing at stare_pos
            for pos in range(right_bound, left_bound - 1, -1):
                draw_eye(pos)
                time.sleep(speed)
                if pos == stare_pos:
                    time.sleep(random.uniform(min_stare, max_stare))

    except (KeyboardInterrupt, SystemExit):
        print("\nCylon stopped")
    finally:
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
                time.sleep(dur / num_steps)
            for step in range(num_steps + 1):
                b = max_b - (max_b - min_b) * (step / num_steps)
                strip.set_all_pixels(limited_color(Color(
                    int(base_color.r * b), int(base_color.g * b), int(base_color.b * b)
                )))
                strip.show()
                time.sleep(dur / num_steps)
    except (KeyboardInterrupt, SystemExit):
        print("\nGlow stopped")

def run_cycle(strip, config: dict, cycle_duration=None, fade_time=None, fade_enabled=None):
    c = config.get('cycle', {})
    cycle_duration = cycle_duration if cycle_duration is not None else c.get('cycle_duration', 10.0)
    fade_time = fade_time if fade_time is not None else c.get('fade_time', 1.5)
    fade_enabled = fade_enabled if fade_enabled is not None else c.get('fade_enabled', True)

    # Optional custom color list; default excludes 'off'
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
            time.sleep(max(0, cycle_duration - fade_time))

            if fade_enabled and fade_time > 0:
                steps = 30
                for s in range(steps + 1):
                    p = s / steps
                    # True crossfade: interpolate directly between cur and nxt
                    r = int(cur.r * (1 - p) + nxt.r * p)
                    g = int(cur.g * (1 - p) + nxt.g * p)
                    b = int(cur.b * (1 - p) + nxt.b * p)
                    strip.set_all_pixels(limited_color(Color(r, g, b)))
                    strip.show()
                    time.sleep(fade_time / steps)
            else:
                time.sleep(fade_time)

            current_idx = next_idx
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
            j = (j + 1) % 256
            time.sleep(speed)
    except (KeyboardInterrupt, SystemExit):
        print("\nRainbow stopped")

def run_meteor(strip, color, config: dict):
    c = config.get('meteor', {})
    tail_length = c.get('tail_length', 8)
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
                        red_val = int(color.r * brightness)
                        green_val = int(color.g * brightness)
                        blue_val = int(color.b * brightness)
                        set_pixel(strip, idx, limited_color(Color(red_val, green_val, blue_val)))
                strip.show()
                time.sleep(speed)
            time.sleep(0.5)
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
                    r = int(s['color'].r * s['bright'])
                    g = int(s['color'].g * s['bright'])
                    b = int(s['color'].b * s['bright'])
                    set_pixel(strip, i, limited_color(Color(r, g, b)))
                    s['bright'] -= fade_speed
                    if s['bright'] <= 0:
                        sparkles[i] = None
            strip.show()
            time.sleep(0.05)
    except (KeyboardInterrupt, SystemExit):
        print("\nTwinkle stopped")

# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

def main():
    global NUM_LEDS, SPI_BUS, SPI_DEVICE, global_brightness

    parser = argparse.ArgumentParser(description='WS2812B LED control on Raspberry Pi 5')
    parser.add_argument('--config', type=Path, default=Path.home() / 'ledcontrol.toml',
                        help='Path to TOML config file')
    parser.add_argument('--color', '-color', default=None,
                        help='Color name (red, green, blue, white, yellow, purple, cyan, orange, pink) or hex (#FF8800)')
    parser.add_argument('--animate', '-animate',
                        choices=['kitt', 'cylon', 'glow', 'cycle', 'rainbow', 'meteor', 'twinkle', 'off'],
                        default=None)
    parser.add_argument('--global-brightness', type=float, default=None,
                        help='Global brightness limit (0.0–1.0)')
    parser.add_argument('--min-brightness', type=float, default=None)
    parser.add_argument('--max-brightness', type=float, default=None)
    parser.add_argument('--duration', type=float, default=None)
    parser.add_argument('--cycle-duration', type=float, default=None)
    parser.add_argument('--fade-time', type=float, default=None)
    parser.add_argument('--no-fade', action='store_true')
    parser.add_argument('--system', default=None,
                        help='RetroPie system name (e.g. arcade, nes, snes) — used by runcommand hooks')
    parser.add_argument('--rom', default=None,
                        help='Full ROM path — used for per-game LED overrides')

    args = parser.parse_args()
    config = load_config(args.config)

    # Hardware: config > hardcoded defaults
    hw = config.get('hardware', {})
    NUM_LEDS = hw.get('num_leds', 14)
    SPI_BUS = hw.get('spi_bus', 0)
    SPI_DEVICE = hw.get('spi_device', 0)
    if NUM_LEDS > MAX_LEDS:
        print(f"Warning: num_leds={NUM_LEDS} exceeds MAX_LEDS={MAX_LEDS} (Pi 5V rail safety limit). "
              f"Clamping to {MAX_LEDS}. Use an external 5V supply to go higher.", file=sys.stderr)
        NUM_LEDS = MAX_LEDS

    # Brightness: CLI > config > 1.0
    global_brightness = (
        args.global_brightness
        if args.global_brightness is not None
        else config.get('general', {}).get('global_brightness', 1.0)
    )
    global_brightness = max(0.0, min(1.0, global_brightness))
    print(f"Brightness:{global_brightness*100:.0f}%  LEDs:{NUM_LEDS}  SPI:{SPI_BUS}/{SPI_DEVICE}")

    # Resolve animation & color — precedence: config defaults → system/rom lookup → CLI args
    gen = config.get('general', {})
    animate = gen.get('default_animate', '')
    color_arg = gen.get('default_color', 'white')

    if args.system is not None:
        sys_animate, sys_color = resolve_for_system(args.system, args.rom, config)
        if sys_animate:
            animate = sys_animate
        if sys_color:
            color_arg = sys_color
        print(f"System:{args.system}  →  animate:{animate}  color:{color_arg}")

    # CLI flags always win
    if args.animate:
        animate = args.animate
    if args.color:
        color_arg = args.color

    # Parse color — named or hex
    if color_arg and color_arg.startswith('#'):
        try:
            color = parse_hex_color(color_arg)
            color_name = color_arg
        except ValueError as e:
            print(f"Invalid hex color: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        color_name = color_arg
        color = COLOR_MAP.get(color_name, Color(255, 255, 255))

    # Early exit for off
    if animate == 'off' or color_name == 'off':
        print("Off mode — clearing LEDs")
        strip = WS2812SpiDriver(spi_bus=SPI_BUS, spi_device=SPI_DEVICE, led_count=NUM_LEDS).get_strip()
        strip.set_all_pixels(Color(0, 0, 0))
        strip.show()
        sys.exit(0)

    # Cycle params
    cycle_c = config.get('cycle', {})
    cycle_duration = args.cycle_duration if args.cycle_duration is not None else cycle_c.get('cycle_duration', 10.0)
    fade_time = 0.0 if args.no_fade else (args.fade_time if args.fade_time is not None else cycle_c.get('fade_time', 1.5))
    fade_enabled = not args.no_fade and cycle_c.get('fade_enabled', True)

    strip = WS2812SpiDriver(spi_bus=SPI_BUS, spi_device=SPI_DEVICE, led_count=NUM_LEDS).get_strip()

    try:
        if animate == 'kitt':
            run_kitt(strip, color, config)
        elif animate == 'cylon':
            run_cylon(strip, color, config)
        elif animate == 'glow':
            run_glow(strip, color, config)
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
            while True:
                time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
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
