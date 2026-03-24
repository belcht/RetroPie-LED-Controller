import board
import busio
from neopixel_spi import NeoPixel_SPI
import argparse
import signal
import time
import random
import sys
from pathlib import Path
import tomllib

# === Module-level config (overwritten from config/CLI in main) ===
NUM_LEDS = 14
global_brightness = 1.0

# Maximum LEDs when powered from the Pi 5V rail.
# Each WS2812 draws up to 60mA at full white; at 80% brightness that is ~48mA per LED.
# 20 LEDs x 48mA = ~960mA — safe headroom on any supply alongside a loaded Pi 5.
# If you are using an external 5V supply with common ground, raise this value freely.
MAX_LEDS = 20

# Colors as (r, g, b) tuples — neopixel_spi uses tuples, not Color objects
COLOR_MAP = {
    'red':    (255, 0, 0),
    'green':  (0, 255, 0),
    'blue':   (0, 0, 255),
    'white':  (255, 255, 255),
    'yellow': (255, 255, 0),
    'purple': (128, 0, 128),
    'cyan':   (0, 255, 255),
    'orange': (255, 100, 0),
    'pink':   (255, 20, 147),
    'off':    (0, 0, 0),
}

# === Signal handling — custom.sh background process needs SIGTERM caught ===
def _handle_signal(sig, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# === Helpers ===

def limited_color(color: tuple) -> tuple:
    """Apply global brightness limit to an (r, g, b) tuple."""
    if global_brightness >= 1.0:
        return color
    r, g, b = color
    return (int(r * global_brightness), int(g * global_brightness), int(b * global_brightness))

def parse_hex_color(hex_str: str) -> tuple:
    """Parse '#FF8800' or 'FF8800' into an (r, g, b) tuple."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        raise ValueError(f"Expected 6 hex digits, got: {hex_str!r}")
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

def wheel(pos: int) -> tuple:
    """Generate rainbow colors across 0–255."""
    pos = pos & 255
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

# ────────────────────────────────────────────────
# System/ROM lookup (gameStart/gameStop integration)
# ────────────────────────────────────────────────

def resolve_for_system(system: str, rom_path: str | None, config: dict) -> tuple[str, str]:
    """
    Return (animate, color_name) for a given system/rom.
    Lookup order: [roms] by filename stem → [systems.<system>] → [systems.default] → general defaults.
    """
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
        print(f"Error loading config {config_path}: {e}", file=sys.stderr)
        return {}

# ────────────────────────────────────────────────
# Animations
# ────────────────────────────────────────────────

def run_kitt(pixels, chase_color: tuple, config: dict):
    c = config.get('kitt', {})
    tail_length = c.get('tail_length', 6)
    base_speed = c.get('base_speed', 0.04)
    print(f"KITT | tail:{tail_length} speed:{base_speed}")
    off = (0, 0, 0)
    pixels.fill(off)
    pixels.show()
    try:
        while True:
            for pos in range(-tail_length + 1, NUM_LEDS + tail_length):
                pixels.fill(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        r = int(chase_color[0] * brightness)
                        g = int(chase_color[1] * brightness)
                        b = int(chase_color[2] * brightness)
                        pixels[idx] = limited_color((r, g, b))
                pixels.show()
                time.sleep(base_speed)
            for pos in range(NUM_LEDS + tail_length - 2, -tail_length, -1):
                pixels.fill(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        r = int(chase_color[0] * brightness)
                        g = int(chase_color[1] * brightness)
                        b = int(chase_color[2] * brightness)
                        pixels[idx] = limited_color((r, g, b))
                pixels.show()
                time.sleep(base_speed)
    except (KeyboardInterrupt, SystemExit):
        print("\nKITT stopped")
    finally:
        pixels.fill(off)
        pixels.show()

def run_cylon(pixels, color: tuple, config: dict):
    c = config.get('cylon', {})
    speed     = c.get('speed', 0.04)
    min_stare = c.get('min_stare', 0.5)
    max_stare = c.get('max_stare', 3.0)

    # Eye width: 3 LEDs for odd strip lengths, 4 for even — stares symmetrically either way
    eye_width = 3 if NUM_LEDS % 2 == 1 else 4
    off = (0, 0, 0)
    print(f"Cylon | eye_width:{eye_width} (auto) speed:{speed} stare:{min_stare}-{max_stare}s")

    end_color = limited_color((int(color[0] * 0.3), int(color[1] * 0.3), int(color[2] * 0.3)))

    left_bound  = 1
    right_bound = NUM_LEDS - 2
    half = eye_width / 2.0

    def draw_eye(pos):
        pixels.fill(off)
        pixels[0] = end_color
        pixels[NUM_LEDS - 1] = end_color
        for i in range(NUM_LEDS):
            dist = abs(i - pos)
            if dist < half:
                intensity = 1.0 - (dist / half)
                pixels[i] = limited_color((
                    int(color[0] * intensity),
                    int(color[1] * intensity),
                    int(color[2] * intensity),
                ))
        pixels.show()

    try:
        while True:
            for pos in range(left_bound, right_bound + 1):
                draw_eye(pos)
                time.sleep(speed)

            stare_pos = random.randint(left_bound, right_bound)

            for pos in range(right_bound, left_bound - 1, -1):
                draw_eye(pos)
                time.sleep(speed)
                if pos == stare_pos:
                    time.sleep(random.uniform(min_stare, max_stare))

    except (KeyboardInterrupt, SystemExit):
        print("\nCylon stopped")
    finally:
        pixels.fill(off)
        pixels.show()

def run_glow(pixels, base_color: tuple, config: dict):
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
                pixels.fill(limited_color((
                    int(base_color[0] * b), int(base_color[1] * b), int(base_color[2] * b)
                )))
                pixels.show()
                time.sleep(dur / num_steps)
            for step in range(num_steps + 1):
                b = max_b - (max_b - min_b) * (step / num_steps)
                pixels.fill(limited_color((
                    int(base_color[0] * b), int(base_color[1] * b), int(base_color[2] * b)
                )))
                pixels.show()
                time.sleep(dur / num_steps)
    except (KeyboardInterrupt, SystemExit):
        print("\nGlow stopped")

def run_centerpulse(pixels, color: tuple, config: dict):
    """Batocera-exclusive: pulse expands from center outward."""
    c = config.get('centerpulse', {})
    base_speed = c.get('base_speed', 0.04)
    pause_at_full = c.get('pause_at_full', 0.2)
    print(f"CenterPulse | speed:{base_speed} pause:{pause_at_full}s")
    off = (0, 0, 0)
    full_color = limited_color(color)
    center = NUM_LEDS // 2
    max_radius = center
    try:
        while True:
            for radius in range(0, max_radius + 1):
                pixels.fill(off)
                for side in range(radius + 1):
                    idx_left  = center - side
                    idx_right = center + side
                    if 0 <= idx_left < NUM_LEDS:
                        pixels[idx_left] = full_color
                    if 0 <= idx_right < NUM_LEDS:
                        pixels[idx_right] = full_color
                pixels.show()
                time.sleep(base_speed)
            time.sleep(pause_at_full)
            for radius in range(max_radius, -1, -1):
                pixels.fill(off)
                for side in range(radius + 1):
                    idx_left  = center - side
                    idx_right = center + side
                    brightness = 1.0 - (side / max(max_radius, 1)) if side > 0 else 1.0
                    c_dim = limited_color((
                        int(color[0] * brightness),
                        int(color[1] * brightness),
                        int(color[2] * brightness),
                    ))
                    if 0 <= idx_left < NUM_LEDS:
                        pixels[idx_left] = c_dim
                    if 0 <= idx_right < NUM_LEDS:
                        pixels[idx_right] = c_dim
                pixels.show()
                time.sleep(base_speed)
    except (KeyboardInterrupt, SystemExit):
        print("\nCenterPulse stopped")

def run_cycle(pixels, config: dict, cycle_duration=None, fade_time=None, fade_enabled=None):
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

            pixels.fill(limited_color(cur))
            pixels.show()
            time.sleep(max(0, cycle_duration - fade_time))

            if fade_enabled and fade_time > 0:
                steps = 30
                for s in range(steps + 1):
                    p = s / steps
                    r = int(cur[0] * (1 - p) + nxt[0] * p)
                    g = int(cur[1] * (1 - p) + nxt[1] * p)
                    b = int(cur[2] * (1 - p) + nxt[2] * p)
                    pixels.fill(limited_color((r, g, b)))
                    pixels.show()
                    time.sleep(fade_time / steps)
            else:
                time.sleep(fade_time)

            current_idx = next_idx
    except (KeyboardInterrupt, SystemExit):
        print("\nCycle stopped")

def run_rainbow(pixels, config: dict):
    speed = config.get('rainbow', {}).get('speed', 0.02)
    print(f"Rainbow | speed:{speed}")
    j = 0
    try:
        while True:
            for i in range(NUM_LEDS):
                pixels[i] = limited_color(wheel((i * 256 // NUM_LEDS + j) & 255))
            pixels.show()
            j = (j + 1) % 256
            time.sleep(speed)
    except (KeyboardInterrupt, SystemExit):
        print("\nRainbow stopped")

def run_meteor(pixels, color: tuple, config: dict):
    c = config.get('meteor', {})
    tail_length = c.get('tail_length', 8)
    speed = c.get('speed', 0.05)
    print(f"Meteor | tail:{tail_length} speed:{speed}")
    off = (0, 0, 0)
    try:
        while True:
            for pos in range(-tail_length, NUM_LEDS):
                pixels.fill(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / tail_length)
                        red_val   = int(color[0] * brightness)
                        green_val = int(color[1] * brightness)
                        blue_val  = int(color[2] * brightness)
                        pixels[idx] = limited_color((red_val, green_val, blue_val))
                pixels.show()
                time.sleep(speed)
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        print("\nMeteor stopped")

def run_twinkle(pixels, base_color: tuple, config: dict):
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
                    col = (
                        int(base_color[0] * rand_factor),
                        int(base_color[1] * rand_factor),
                        int(base_color[2] * rand_factor),
                    )
                    sparkles[idx] = {'bright': random.uniform(0.6, 1.0), 'color': col}
            pixels.fill((0, 0, 0))
            for i in range(NUM_LEDS):
                if sparkles[i]:
                    s = sparkles[i]
                    r = int(s['color'][0] * s['bright'])
                    g = int(s['color'][1] * s['bright'])
                    b = int(s['color'][2] * s['bright'])
                    pixels[i] = limited_color((r, g, b))
                    s['bright'] -= fade_speed
                    if s['bright'] <= 0:
                        sparkles[i] = None
            pixels.show()
            time.sleep(0.05)
    except (KeyboardInterrupt, SystemExit):
        print("\nTwinkle stopped")

# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

def main():
    global NUM_LEDS, global_brightness

    parser = argparse.ArgumentParser(description='WS2812B LED control on Batocera')
    parser.add_argument('--config', type=Path, default=Path('/userdata/system/ledcontrol.toml'),
                        help='Path to TOML config file')
    parser.add_argument('--color', '-color', default=None,
                        help='Color name (red, green, blue, white, yellow, purple, cyan, orange, pink) or hex (#FF8800)')
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
    parser.add_argument('--system', default=None,
                        help='Batocera system name (e.g. mame, snes) — used by gameStart hooks')
    parser.add_argument('--rom', default=None,
                        help='Full ROM path — used for per-game LED overrides')

    args = parser.parse_args()
    config = load_config(args.config)

    # Hardware from config
    hw = config.get('hardware', {})
    NUM_LEDS = hw.get('num_leds', 14)
    if NUM_LEDS > MAX_LEDS:
        print(f"Warning: num_leds={NUM_LEDS} exceeds MAX_LEDS={MAX_LEDS}. "
              f"Clamping to {MAX_LEDS}. Use an external 5V supply to go higher.", file=sys.stderr)
        NUM_LEDS = MAX_LEDS

    # Brightness
    global_brightness = (
        args.global_brightness
        if args.global_brightness is not None
        else config.get('general', {}).get('global_brightness', 1.0)
    )
    global_brightness = max(0.0, min(1.0, global_brightness))
    print(f"Brightness:{global_brightness*100:.0f}%  LEDs:{NUM_LEDS}")

    # Resolve animation & color
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

    if args.animate:
        animate = args.animate
    if args.color:
        color_arg = args.color

    # Parse color
    if color_arg and color_arg.startswith('#'):
        try:
            color = parse_hex_color(color_arg)
            color_name = color_arg
        except ValueError as e:
            print(f"Invalid hex color: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        color_name = color_arg
        color = COLOR_MAP.get(color_name, (255, 255, 255))

    # Initialise hardware
    try:
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        pixels = NeoPixel_SPI(spi, NUM_LEDS, pixel_order="GRB", auto_write=False)
    except Exception as e:
        print(f"Failed to initialise SPI/NeoPixel: {e}", file=sys.stderr)
        print("Is SPI enabled? Check /userdata/system/config.txt for dtparam=spi=on", file=sys.stderr)
        sys.exit(1)

    # Early exit for off
    if animate == 'off' or color_name == 'off':
        print("Off mode — clearing LEDs")
        pixels.fill((0, 0, 0))
        pixels.show()
        sys.exit(0)

    # Cycle params
    cycle_c = config.get('cycle', {})
    cycle_duration = args.cycle_duration if args.cycle_duration is not None else cycle_c.get('cycle_duration', 10.0)
    fade_time = 0.0 if args.no_fade else (args.fade_time if args.fade_time is not None else cycle_c.get('fade_time', 1.5))
    fade_enabled = not args.no_fade and cycle_c.get('fade_enabled', True)

    try:
        if animate == 'kitt':
            run_kitt(pixels, color, config)
        elif animate == 'cylon':
            run_cylon(pixels, color, config)
        elif animate == 'glow':
            run_glow(pixels, color, config)
        elif animate == 'centerpulse':
            run_centerpulse(pixels, color, config)
        elif animate == 'cycle':
            run_cycle(pixels, config, cycle_duration, fade_time, fade_enabled)
        elif animate == 'rainbow':
            run_rainbow(pixels, config)
        elif animate == 'meteor':
            run_meteor(pixels, color, config)
        elif animate == 'twinkle':
            run_twinkle(pixels, color, config)
        else:
            print(f"Solid color: {color_name}")
            pixels.fill(limited_color(color))
            pixels.show()
            while True:
                time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\nStopped")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        print("Turning off LEDs...")
        pixels.fill((0, 0, 0))
        pixels.show()

if __name__ == "__main__":
    main()
