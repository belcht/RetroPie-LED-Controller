# Build review — cathypi (full Desktop image) + doc/installer notes

Notes from validating the installer end-to-end on **cathypi** — the first box built on
the **64-bit Full (Desktop) image**, on **Trixie/Wayland**. Captured here so the docs and
installer stay accurate and *generic* (not tied to our specific network/audio/monitor).

## The box
- Raspberry Pi 5 (8 GB), **Debian 13 Trixie, 64-bit Full/Desktop** (labwc/Wayland + PipeWire).
- **NVMe SSD** boot (PCIe, not USB) — root on `nvme0n1p2`.
- **Onboard WiFi** (`brcmfmac`, wlan0) on the new **UniFi** network — *not* a USB adapter.
- 10" panel at **1280×800** (landscape, auto-detected — no forced mode).
- **11-LED** marquee.

## Install + result (`sudo ./picadeinstall.sh --leds 11 --auto`)
Ran clean in ~35 min (Result: success). Verified **after a real reboot**:
- Boots to **EmulationStation** — the installer correctly flipped the Desktop image from
  `graphical.target` to `multi-user.target` + autostart.
- `ledcontrol.service` active, driving **11 LEDs** (kitt + rainbow test commands applied).
- **Onboard WiFi survived the reboot** on UniFi (same IP, `brcmfmac`). Watching for stability
  — the eero-era association failures may simply not recur on UniFi.
- 1280×800 panel, PipeWire masked for clean arcade ALSA audio.

## Findings / changes
1. **QUICKSTART.md — fixed.** It used a stray project name `pi5cade`: the clone URL
   (`belcht/pi5cade.git`) and `cd pi5cade` were wrong (real repo: `RetroPie-LED-Controller`),
   so a copy-paster got "repository not found." Retitled + corrected; file was also untracked.
2. **deploy.sh — clarified.** `deploy.sh retropie` runs the **LED-only** `install.sh`, not the
   full installer. Added a header note pointing first-time/full builds at `picadeinstall.sh`.
3. **Desktop audio on Wayland — OPEN ISSUE.** The installer masks PipeWire for the arcade and
   re-enables it for desktop sessions via a **`startx` (X11) wrapper**. Trixie's desktop is
   **labwc/Wayland**, so that wrapper won't fire for a Wayland session → a Wayland desktop
   session would have no audio. **TODO:** a Wayland-aware equivalent (re-enable PipeWire when a
   labwc/wayfire session starts) for the "also a desktop" path. Pure-arcade boxes are unaffected.
4. **Genericity check (must not bake in our hardware):**
   - **Network:** installer default is generic — just the self-disabling WiFi watchdog. The
     eero/band-pinning tuning lives only in the *optional* `setup/` manual notes, framed as
     "for mesh/eero users." ✓ (cathypi runs onboard WiFi with none of it.)
   - **Audio:** generic — auto-selects USB sound card *if present*, else connected HDMI. The
     `WaveshareUSB` udev rule (VID:PID `0c76:1203`) is our **reference dongle only**; it's a
     no-op if absent, and the docs already say to change the VID:PID for a different card. ✓
   - **Monitor:** auto-detected (no forced resolution/rotation); our panels are documented as
     examples, not requirements. ✓

## Emulators — basic_install gap + Trixie mGBA build (2026-08-05)
RetroPie `basic_install` (Core+Main) leaves several emulators UNINSTALLED that a configured fleet
box (pi4/PiVert) has. On cathypi this broke **arcade**: arcade defaults to `lr-mame2010`, an
*optional* package that basic_install never installs — so every arcade launch hit a missing
emulator. Installed to match pi4 via `retropie_packages.sh <pkg> _source_`:
`lr-mame2010`, `lr-mame2003-plus`, `advmame` (arcade), `lr-desmume` (NDS), `lr-vice` (C64),
`amiberry` (Amiga), `atari800`, `hypseus` (Daphne).
- **`lr-mgba` will NOT build on Trixie** — recent mGBA dropped `Makefile.libretro`, so RetroPie's
  module errors (`make: Makefile.libretro: No such file or directory`). Workaround: copy a prebuilt
  `mgba_libretro.so` from another Trixie box (e.g. PiVert) into `/opt/retropie/libretrocores/lr-mgba/`
  and verify `ldd … | grep -c 'not found'` == 0. GBA otherwise falls back to `lr-vba-next` (base).
- **Installer/docs takeaway:** after a fresh full build, reconcile the emulator set against the
  reference box, or per-system defaults (esp. arcade `lr-mame2010`) will point at missing cores.
