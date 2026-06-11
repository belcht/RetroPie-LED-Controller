# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two Python programs that drive WS2812B LED strips on a Raspberry Pi 5, plus the glue to ship them onto **RetroPie** and **Batocera** arcade-cabinet OSes from a single source tree. There is no test suite, no linter config, and no package manifest — everything is plain Python scripts plus shell installers.

## Architecture — the one thing to internalize

Three components talk over a single localhost WebSocket on `ws://127.0.0.1:8765`:

```
LEDControl.py (long-running service)  ──┐
  drives the SPI LEDs, runs animations  │  ws://127.0.0.1:8765
                                        │  ├─ "pixels" frames (~60fps) →
retro-led/retro-led.py (pygame UI)  ────┤  └─ "set" commands ←
  shows virtual strip, sends commands   │
                                        │
led-ws-cmd.py (one-shot CLI sender)  ───┘
  used by RunCommand / gameStart hooks
```

The service is the single source of truth for the physical LEDs. The UI and the game hooks never touch the LEDs directly — they send a `{"cmd":"set", "animate":..., "color":..., "save":...}` message, which the service receives in [LEDControl.py:check_commands](LEDControl.py#L84) and uses to raise an `AnimationSwitch` exception that unwinds whichever animation loop is currently running. New animation loops resume from `main()`'s outer `while True`.

### RetroPie vs Batocera — the fork that matters

There are **two copies of `LEDControl.py`**:
- [LEDControl.py](LEDControl.py) — RetroPie. Uses `rpi5_ws2812` and its `Color` objects. Talks to the strip via `strip._pixels[i] = Color(r,g,b)` then `strip.show()`.
- [batocera/LEDControl.py](batocera/LEDControl.py) — Batocera. Uses `adafruit-blinka` + `neopixel_spi`, and pixels are plain `(r, g, b)` tuples assigned by index on a `NeoPixel_SPI` object.

The two files have the same animations, the same config schema, the same WebSocket protocol, the same `AnimationSwitch` flow, the same `--system`/`--rom` resolution. **When you change one, you almost always need to change the other.** Diff them after every animation/protocol edit.

Everything else is shared from the repo root and installed identically on both targets:
- [led-ws-cmd.py](led-ws-cmd.py), [update_config.py](update_config.py), [ledcontrol.toml](ledcontrol.toml)
- [retro-led/retro-led.py](retro-led/retro-led.py) — single pygame UI that auto-detects platform via [retro-led.py:detect_platform](retro-led/retro-led.py#L46) (looks for `/userdata/system` vs `/home/pi/LEDControl`).

### Vendored websockets

[retro-led/vendor/](retro-led/vendor/) holds a pure-Python copy of `websockets` 13.1. Both `LEDControl.py` variants and `led-ws-cmd.py` prepend this path to `sys.path` before importing, so the code runs on Batocera (where you can't `pip install`) without any extra setup. If you add new imports from `websockets`, check they exist in the vendored copy.

### Per-system / per-ROM resolution

`resolve_for_system(system, rom_path, config)` is duplicated in [LEDControl.py:210](LEDControl.py#L210), [batocera/LEDControl.py](batocera/LEDControl.py), and [led-ws-cmd.py:40](led-ws-cmd.py#L40). ROM-stem match (case-insensitive) wins over system match wins over `systems.default` wins over `general.default_*`. Keep these three implementations in sync.

### Game-launch flow (why `resolve_for_system` is duplicated)

RetroPie's runcommand and Batocera's `gameStart.sh` both fire `led-ws-cmd.py --system X --rom Y` when a game launches, and `--restore` on exit. `led-ws-cmd.py` reads `ledcontrol.toml`, resolves the system/ROM to an `(animate, color)` pair via its own copy of `resolve_for_system`, and sends a single `{"cmd":"set"}` over the WebSocket. The service is already running — nothing is started or killed per game; the hook is fire-and-forget. The install scripts ([install.sh](install.sh), [batocera/install.sh](batocera/install.sh)) are what plant the hook scripts into the right OS-specific locations (`/opt/retropie/configs/all/runcommand-*.sh` on RetroPie, `/userdata/system/scripts/gameStart.sh` and `gameStop.sh` on Batocera).

## Common commands

**Desktop development (no Pi needed)** — run the mock service and UI in two terminals:
```bash
cd retro-led
python3 mock-service.py --leds 14    # terminal 1
python3 retro-led/retro-led.py       # terminal 2 (from repo root)
```

**Deploy to a Pi from your Mac** ([deploy.sh](deploy.sh) — rsync + run installer):
```bash
bash deploy.sh pivert.local                # RetroPie (auto-detected by name)
bash deploy.sh batocera bat1.local         # Batocera
bash deploy.sh pivert.local --sync-only    # sync only, skip running install.sh
```
Deploy is incremental and logs to `deploy.log` (gitignored). First-time auth: `ssh-copy-id pi@host` (RetroPie, pw `raspberry`) or `ssh-copy-id root@host` (Batocera, pw `linux`).

**On the Pi — restart the service** after editing config or pushing new code:
```bash
sudo systemctl restart ledcontrol.service                       # RetroPie
batocera-services stop ledcontrol && batocera-services start ledcontrol   # Batocera
```

**Send an ad-hoc command** (useful for debugging on the Pi):
```bash
python3 /home/pi/LEDControl/led-ws-cmd.py --animate rainbow --color blue        # RetroPie
python3 /userdata/system/LEDControl/led-ws-cmd.py --restore                     # Batocera
```

## Conventions baked into the code

- **`AnimationSwitch` is the only legitimate way to change animations mid-run.** Every animation loop catches `(KeyboardInterrupt, SystemExit)` for clean shutdown but re-raises `AnimationSwitch` so `main()` can pick up the new state. Don't swallow it.
- **`check_commands()` must be called once per visible frame** in every animation. If you forget, the WebSocket will appear to hang.
- **`broadcast_pixels(strip)` must follow every `strip.show()`** for the UI to stay in sync.
- **`global_brightness` is a module-level global** (separately in each `LEDControl.py`). Every pixel write goes through `limited_color(...)` to apply it. New animations must too.
- **`MAX_LEDS = 20`** is a hard clamp in both services. Higher strip counts are deliberately rejected — power-draw safety, not a software limit.
- **Config writes are surgical, not full rewrites.** `_save_config()` uses regex to patch one key inside a `[section]` so user comments in `ledcontrol.toml` survive. Don't replace it with a `tomli_w`-style dump.
- **Animation choices live in `argparse`** at [LEDControl.py:585](LEDControl.py#L585) and the matching line in `batocera/LEDControl.py`. When you add an animation, update both `argparse` lists, the `if animate == ...` ladder in `main()`, the `COLOR_MAP`-adjacent docs in [README.md](README.md), and the UI's animation list in `retro-led.py`.

## Things that aren't in the repo

No tests, no CI, no formatter config, no `requirements.txt` (the installers `pip install` the few deps directly). If you want to lint, just run `python3 -m py_compile` on the changed file — that's the only check the codebase relies on.
