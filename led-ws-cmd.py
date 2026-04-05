#!/usr/bin/env python3
"""
led-ws-cmd.py — Send a one-shot command to the running LEDControl WebSocket service.

Usage:
  python3 led-ws-cmd.py --system arcade --rom /path/to/dkong.zip
  python3 led-ws-cmd.py --restore
  python3 led-ws-cmd.py --animate kitt --color red
"""

import sys
import json
import argparse
from pathlib import Path

# Vendored websockets (pure Python, no install needed)
sys.path.insert(0, str(Path(__file__).parent / 'retro-led' / 'vendor'))

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

WS_PORT = 8765


def load_config(config_path: Path) -> dict:
    if tomllib is None or not config_path.is_file():
        return {}
    try:
        with open(config_path, 'rb') as f:
            return tomllib.load(f)
    except Exception:
        return {}


def resolve_for_system(system, rom_path, config):
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
        default.get('animate', gen.get('default_animate', 'kitt')),
        default.get('color',   gen.get('default_color',   'white')),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--animate',  default=None)
    parser.add_argument('--color',    default=None)
    parser.add_argument('--system',   default=None)
    parser.add_argument('--rom',      default=None)
    parser.add_argument('--restore',  action='store_true',
                        help='Restore default animation from config')
    parser.add_argument('--config',   type=Path,
                        default=Path.home() / 'ledcontrol.toml')
    args = parser.parse_args()

    config = load_config(args.config)
    gen    = config.get('general', {})

    if args.restore:
        animate = gen.get('default_animate', 'kitt')
        color   = gen.get('default_color',   'white')
    elif args.system:
        animate, color = resolve_for_system(args.system, args.rom, config)
    else:
        animate = args.animate or gen.get('default_animate', 'kitt')
        color   = args.color   or gen.get('default_color',   'white')

    try:
        from websockets.sync.client import connect
        with connect(f'ws://127.0.0.1:{WS_PORT}', open_timeout=3) as ws:
            ws.send(json.dumps({'cmd': 'set', 'animate': animate, 'color': color}))
    except Exception as e:
        print(f"LED command failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
