from rpi5_ws2812.ws2812 import WS2812SpiDriver, Color
import argparse
import time
import random
import sys
from pathlib import Path
import tomllib

# === Fixed / Hardcoded ===
NUM_LEDS = 14
SPI_BUS = 0
SPI_DEVICE = 0

COLOR_MAP = {
    'red':    Color(255, 0, 0),
    'green':  Color(0, 255, 0),
    'blue':   Color(0, 0, 255),
    'white':  Color(255, 255, 255),
    'yellow': Color(255, 255, 0),
    'purple': Color(128, 0, 128),
    'cyan':   Color(0, 255, 255),
    'off':    Color(0, 0, 0)
}

# === Global Brightness Limiter ===
global_brightness = 1.0  # Will be overwritten by CLI or config

def limited_color(color: Color) -> Color:
    """Apply global brightness limit to a Color object"""
    if global_brightness >= 1.0:
        return color
    return Color(
        int(color.r * global_brightness),
        int(color.g * global_brightness),
        int(color.b * global_brightness)
    )

# Wheel function for rainbow colors
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
# Load config from TOML file
# ────────────────────────────────────────────────

def load_config(config_path: Path) -> dict:
    config = {}
    if not config_path.is_file():
        print(f"Config file not found: {config_path} - using defaults")
        return config

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        print(f"Loaded config from {config_path}")
    except Exception as e:
        print(f"Error loading config {config_path}: {e}", file=sys.stderr)
    return config

# ────────────────────────────────────────────────
# Animations (updated to use limited_color)
# ────────────────────────────────────────────────

def run_kitt(strip, chase_color, config: dict):
    c = config.get('kitt', {})
    tail_length = c.get('tail_length', 6)
    base_speed = c.get('base_speed', 0.04)
    print(f"Starting KITT ({chase_color}) | tail:{tail_length} speed:{base_speed}")
    off = Color(0, 0, 0)
    strip.set_all_pixels(off)
    strip.show()
    try:
        while True:
            # Forward
            for pos in range(-tail_length + 1, NUM_LEDS + tail_length):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        r = int(chase_color.r * brightness)
                        g = int(chase_color.g * brightness)
                        b = int(chase_color.b * brightness)
                        strip._pixels[idx] = limited_color(Color(r, g, b))
                strip.show()
                time.sleep(base_speed)
            # Backward
            for pos in range(NUM_LEDS + tail_length - 2, -tail_length, -1):
                strip.set_all_pixels(off)
                for t in range(tail_length):
                    idx = pos - t
                    if 0 <= idx < NUM_LEDS:
                        brightness = 1.0 - (t / (tail_length - 1))
                        r = int(chase_color.r * brightness)
                        g = int(chase_color.g * brightness)
                        b = int(chase_color.b * brightness)
                        strip._pixels[idx] = limited_color(Color(r, g, b))
                strip.show()
                time.sleep(base_speed)
    except KeyboardInterrupt:
        print("\nKITT stopped")
    finally:
        strip.set_all_pixels(off)
        strip.show()

def run_glow(strip, base_color, config: dict):
    c = config.get('glow', {})
    min_b = c.get('min_brightness', 0.5)
    max_b = c.get('max_brightness', 1.0)
    dur = c.get('duration', 1.0)
    print(f"Starting glow ({base_color}) min:{min_b} max:{max_b} dur:{dur}s")
    strip.set_all_pixels(Color(0,0,0))
    strip.show()
    num_steps = 20
    while True:
        for step in range(num_steps + 1):
            b = min_b + (max_b - min_b) * (step / num_steps)
            col = Color(int(base_color.r * b), int(base_color.g * b), int(base_color.b * b))
            strip.set_all_pixels(limited_color(col))
            strip.show()
            time.sleep(dur / num_steps)
        for step in range(num_steps + 1):
            b = max_b - (max_b - min_b) * (step / num_steps)
            col = Color(int(base_color.r * b), int(base_color.g * b), int(base_color.b * b))
            strip.set_all_pixels(limited_color(col))
            strip.show()
            time.sleep(dur / num_steps)

def run_cycle(strip, config: dict, cycle_duration=None, fade_time=None, fade_enabled=None):
    c = config.get('cycle', {})
    cycle_duration = cycle_duration if cycle_duration is not None else c.get('cycle_duration', 10.0)
    fade_time = fade_time if fade_time is not None else c.get('fade_time', 1.5)
    fade_enabled = fade_enabled if fade_enabled is not None else c.get('fade_enabled', True)
    colors_list = list(COLOR_MAP.values())
    print(f"Cycle: {len(colors_list)} colors, {cycle_duration}s each, fade:{fade_enabled}")
    current_idx = 0
    while True:
        current = limited_color(colors_list[current_idx])
        next_idx = (current_idx + 1) % len(colors_list)
        next_c = limited_color(colors_list[next_idx])
        strip.set_all_pixels(current)
        strip.show()
        time.sleep(max(0, cycle_duration - fade_time))
        if fade_enabled and fade_time > 0:
            steps = 30
            for s in range(steps + 1):
                p = s / steps
                r = int(colors_list[current_idx].r * (1-p))
                g = int(colors_list[current_idx].g * (1-p))
                b = int(colors_list[current_idx].b * (1-p))
                strip.set_all_pixels(limited_color(Color(r, g, b)))
                strip.show()
                time.sleep(fade_time / steps)
            for s in range(steps + 1):
                p = s / steps
                r = int(colors_list[next_idx].r * p)
                g = int(colors_list[next_idx].g * p)
                b = int(colors_list[next_idx].b * p)
                strip.set_all_pixels(limited_color(Color(r, g, b)))
                strip.show()
                time.sleep(fade_time / steps)
        else:
            time.sleep(fade_time)
        current_idx = next_idx

def run_rainbow(strip, config: dict):
    speed = config.get('rainbow', {}).get('speed', 0.02)
    print(f"Rainbow wave (speed: {speed})... Ctrl+C to stop")
    j = 0
    while True:
        for i in range(NUM_LEDS):
            strip._pixels[i] = limited_color(wheel((i * 256 // NUM_LEDS + j) & 255))
        strip.show()
        j = (j + 1) % 256
        time.sleep(speed)

def run_meteor(strip, color, config: dict):
    c = config.get('meteor', {})
    tail_length = c.get('tail_length', 8)
    speed = c.get('speed', 0.05)
    print(f"Meteor ({color}) tail:{tail_length} speed:{speed}")
    off = Color(0,0,0)
    while True:
        for pos in range(-tail_length, NUM_LEDS):
            strip.set_all_pixels(off)
            for t in range(tail_length):
                idx = pos - t
                if 0 <= idx < NUM_LEDS:
                    b = 1.0 - (t / tail_length)
                    r = int(color.r * b)
                    g = int(color.g * b)
                    b = int(color.b * b)
                    strip._pixels[idx] = limited_color(Color(r, g, b))
            strip.show()
            time.sleep(speed)
        time.sleep(0.5)

def run_twinkle(strip, base_color, config: dict):
    c = config.get('twinkle', {})
    num_sparkles = c.get('num_sparkles', 5)
    fade_speed = c.get('fade_speed', 0.04)
    print(f"Twinkle ({base_color}) sparkles:{num_sparkles} fade:{fade_speed}")
    sparkles = [None] * NUM_LEDS
    while True:
        active = sum(1 for x in sparkles if x is not None)
        if active < num_sparkles:
            idx = random.randint(0, NUM_LEDS-1)
            if sparkles[idx] is None:
                rand_factor = random.uniform(0.7, 1.0)
                col = Color(
                    int(base_color.r * rand_factor),
                    int(base_color.g * rand_factor),
                    int(base_color.b * rand_factor)
                )
                sparkles[idx] = {'bright': random.uniform(0.6, 1.0), 'color': col}
        strip.set_all_pixels(Color(0,0,0))
        for i in range(NUM_LEDS):
            if sparkles[i]:
                s = sparkles[i]
                r = int(s['color'].r * s['bright'])
                g = int(s['color'].g * s['bright'])
                b = int(s['color'].b * s['bright'])
                strip._pixels[i] = limited_color(Color(r, g, b))
                s['bright'] -= fade_speed
                if s['bright'] <= 0:
                    sparkles[i] = None
        strip.show()
        time.sleep(0.05)

# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

def main():
    global global_brightness  # Allow modification

    parser = argparse.ArgumentParser(description='WS2812B LED control on Raspberry Pi 5')
    parser.add_argument('--config', type=Path, default=Path.home() / 'ledcontrol.toml',
                        help='Path to TOML config file')
    parser.add_argument('-color', '--color', choices=list(COLOR_MAP.keys()), default=None)
    parser.add_argument('-animate', '--animate', choices=['kitt','glow','cycle','rainbow','meteor','twinkle','off'], default=None)
    parser.add_argument('--global-brightness', type=float, default=None,
                        help='Global brightness limit (0.0–1.0, e.g. 0.8 = 80%)')

    # Glow overrides
    parser.add_argument('--min-brightness', type=float, default=None)
    parser.add_argument('--max-brightness', type=float, default=None)
    parser.add_argument('--duration', type=float, default=None)

    # Cycle overrides
    parser.add_argument('--cycle-duration', type=float, default=None)
    parser.add_argument('--fade-time', type=float, default=None)
    parser.add_argument('--no-fade', action='store_true')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Resolve global brightness: CLI > config > 1.0
    global_brightness = (
        args.global_brightness
        if args.global_brightness is not None
        else config.get('general', {}).get('global_brightness', 1.0)
    )
    global_brightness = max(0.0, min(1.0, global_brightness))
    print(f"Global brightness limit: {global_brightness*100:.0f}%")

    # Resolve animation & color
    animate = args.animate or config.get('general', {}).get('default_animate', '')
    color_name = args.color or config.get('general', {}).get('default_color', 'white')
    color = COLOR_MAP.get(color_name, Color(255, 255, 255))

    # Early exit for off mode
    if animate == 'off' or color_name == 'off':
        print("Off mode requested - clearing LEDs and exiting")
        strip = WS2812SpiDriver(spi_bus=SPI_BUS, spi_device=SPI_DEVICE, led_count=NUM_LEDS).get_strip()
        strip.set_all_pixels(limited_color(Color(0, 0, 0)))
        strip.show()
        sys.exit(0)

    # Glow params
    glow_c = config.get('glow', {})
    min_brightness = args.min_brightness if args.min_brightness is not None else glow_c.get('min_brightness', 0.5)
    max_brightness = args.max_brightness if args.max_brightness is not None else glow_c.get('max_brightness', 1.0)
    duration = args.duration if args.duration is not None else glow_c.get('duration', 1.0)

    # Cycle params
    cycle_c = config.get('cycle', {})
    cycle_duration = args.cycle_duration if args.cycle_duration is not None else cycle_c.get('cycle_duration', 10.0)
    fade_time = 0.0 if args.no_fade else (args.fade_time if args.fade_time is not None else cycle_c.get('fade_time', 1.5))
    fade_enabled = not args.no_fade and cycle_c.get('fade_enabled', True)

    # Initialize strip
    strip = WS2812SpiDriver(spi_bus=SPI_BUS, spi_device=SPI_DEVICE, led_count=NUM_LEDS).get_strip()

    try:
        if animate:
            if animate == 'kitt':
                run_kitt(strip, color, config)
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
            print(f"Setting solid color: {color_name}")
            strip.set_all_pixels(limited_color(color))
            strip.show()
            print("Press Ctrl+C to exit")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error during execution: {e}", file=sys.stderr)
        raise
    finally:
        print("Turning off LEDs...")
        strip.set_all_pixels(limited_color(Color(0,0,0)))
        strip.show()

if __name__ == "__main__":
    main()
