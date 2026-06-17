# Build doc — working notes

Raw notes/decisions to fold into `docs/BUILD.md` later. Not the final doc.

---

## LED power: direct off the Pi GPIO (this build) — for later discussion

**What this build actually does:** the WS2812B strip is powered **directly from
the Raspberry Pi 5 GPIO header** — no separate 5 V supply:
- **5 V** → Pi 5V pin (header pin 2/4)
- **GND** → Pi GND
- **Data** → GPIO 10 (MOSI, header pin 19)
- **No series resistor**, **no external supply**, ~**16–17 LEDs**.

**Why it's acceptable at this scale (the math):**
- WS2812B ≈ **60 mA/LED** at full white, 100 % brightness.
- Firmware caps brightness at **80 %** → ≈ **48 mA/LED**.
- 17 LEDs × 48 mA ≈ **0.82 A** worst case (full white).
- `MAX_LEDS = 20` hard clamp → absolute ceiling ≈ 20 × 48 mA ≈ **0.96 A**.
- All **< 1 A**, well within the Pi 5's 5V rail headroom **when using the
  official 27 W (5 V/5 A) PSU** — and that PSU choice matters precisely because
  the LEDs share the Pi's rail.

**Why you would NOT scale this up (the "proper way" note):**
- ~30 LEDs ≈ 1.4 A (capped) / 1.8 A (full) → the Pi's 5V rail sags, you get
  **voltage drop along the strip** (undervolt / color shift toward the far end)
  and risk **brownout / instability**.
- Proper approach for any sizable strip: **external 5 V supply**, **shared
  ground** with the Pi, **330–470 Ω** series resistor on the data line, and a
  **1000 µF** capacitor across 5V/GND at the strip. (Already in the repo README.)

**Disclaimer to include verbatim-ish in the doc:**
> I have run this direct-from-GPIO configuration for months with no issues at
> this LED count and brightness cap. It is deliberately kept small and
> current-limited. Powering an LED strip directly from the Pi's 5V rail is
> outside the strictly "proper" externally-powered approach — **do this at your
> own risk.** If you increase the LED count or remove the brightness cap, switch
> to an external 5 V supply as described above.

**Also:** `ledcontrol.toml` `num_leds` MUST match the physical strip length
(reference box currently set to 14; actual strip ~16–17 — confirm and update).

---

## Recommended hardware — Bill of Materials

Major components for the new build. Links are the author's Amazon **associate
links** — keep the `amzn.to/...` short URLs verbatim in the doc (affiliate
tracking lives in them; do not expand to canonical Amazon URLs).

| Component | Product | Link |
|-----------|---------|------|
| Pi 5 (8GB) kit | RasTech Raspberry Pi 5 8GB — incl. case, active cooler, screwdriver | https://amzn.to/4unSpwf |
| microSD card | SanDisk 256GB microSDXC (+ adapter). Author uses 512GB; **256GB suggested minimum** for a reasonable collection. | https://amzn.to/4w0225R |
| USB audio | USB Sound Card **with 8Ω 5W speaker** (driver-free; Pi/Jetson). Chip enumerates as JMTek `0c76:1203` → named `WaveshareUSB` by our udev rule. Drives the 5W speaker directly (no separate amp). | https://amzn.to/4vDAXoH |
| Arcade controls | EG STARTS 1-Player Joystick + 5V LED arcade buttons DIY kit | https://amzn.to/4xm7vVT |
| Display | ROADOM 7″ IPS 1024×600 touch, HDMI input, dual built-in speakers, Pi 5/4/3 | https://amzn.to/4uWtMrD |

**Author specs:** Pi 5 **8GB RAM**; **5V/5A** power supply (LEDs share the Pi
rail — see LED power note above); strip ~16–17 WS2812B LEDs.

**Optional hardware:**
- **TP-Link Archer T2U Nano (AC600)** USB WiFi adapter — https://amzn.to/4uUWjOm
  - For users on **eero / mesh networks** who hit the Pi onboard-WiFi association
    problem. Different chipset (Realtek RTL8811AU) sidesteps the `brcmfmac`/eero
    bug entirely; author reports it "greatly improves WiFi on the Pi on this
    network." Costs one USB port (Pi 5 has 4, no splitter needed).
  - Caveat for doc: RTL8811AU may need a Linux driver (not always plug-and-play).
  - This is the **hardware** alternative to the software WiFi watchdog — present
    both as options for eero users. **pi2 itself uses the Pi's onboard adapter.**

**Not yet linked (author to provide):**
- 5V/5A power supply (Amazon link TBD).
- WS2812B LED strip (Amazon link TBD).
- "Other monitors, cables, adapters" — author will add.

---

## OS + order decisions
- **OS:** Raspberry Pi OS **Trixie (Debian 13)** is fine for RetroPie — the
  reference box PiVert runs RetroPie on **Trixie Lite** with no issues. (Earlier
  Bookworm assumption was wrong; corrected.)
- **Lite vs Desktop:** PiVert is **Lite**, but **pi2 (this build) uses the full
  Desktop image — by choice.** Rationale: the user wants to drop out of
  EmulationStation to the PIXEL desktop + keyboard and use it as a general
  computer. RetroPie installs fine on Desktop; set **autostart → boot to
  EmulationStation**, and exit ES to reach the desktop when wanted. (Trade-off:
  more bloat than Lite; can't run PIXEL and ES simultaneously.) Doc should
  present this as the recommended "dual-purpose" path AND note Lite as the
  leaner arcade-only option.
- **WiFi hardening is OPTIONAL** — only recommended for eero/mesh users who
  actually have onboard-WiFi trouble. Don't impose it on users whose WiFi is
  fine. Offer two routes: software (watchdog + roamoff/band/powersave) or
  hardware (TP-Link T2U Nano above).
- **Order (approved):** OS prep → box hardening (journald → audio → *optional*
  WiFi) → RetroPie → **LEDs last** (RetroLED Ports UI needs EmulationStation
  installed first) → reboot-verify.

## Boot fix: disable the plymouth splash (pi2 Desktop: 2–3 min → 17s)

On pi2 (Pi 5, Trixie **Desktop**, 7″ HDMI touch display) the boot stalled
**~133 s in initramfs** before mounting root — total 2–3 minutes. Root cause:
**`plymouth`** (the graphical boot splash) hanging while waiting on the
display/DRM. It logs nothing, so it masqueraded as a USB/SD problem — the
USB-audio and touchscreen enumeration failures nearby were **red herrings**.

Fix — drop the splash from the kernel cmdline:
```bash
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo sed -i "s/ quiet splash plymouth.ignore-serial-consoles//" /boot/firmware/cmdline.txt
sudo reboot
```
Result: root mounts ~4 s, total boot ~17 s. (Optional: re-add just `quiet` for a
silent boot — keep `splash` OFF, that's the offender.) Likely a **Desktop-image**
issue; Lite has no plymouth splash.

> Diagnostic worth documenting: when boot hangs behind the splash, remove
> `quiet splash` from cmdline and watch the console — the stalling step's message
> stays on screen for the whole hang.

## SOLVED: USB audio fails to enumerate at boot — the *monitor's USB power* is the cause

**The multi-day mystery, resolved.** The JMTek `0c76:1203` dongle would not
enumerate at boot on pi2 (`invalid context state for evaluate context command` /
`device descriptor read … error -71` / `unable to enumerate`), but **always**
worked on a warm physical replug.

**What it was NOT** (each empirically ruled out, not guessed):
- Not the dongle — PiVert's known-good unit fails the same way on pi2.
- Not the USB port — fails on every black/blue port, both controllers.
- Not HDMI audio config (`dtparam=audio=off`, `vc4-kms-v3d,noaudio`) — no effect.
- Not the touchscreen — fails with it fully disconnected.
- Not the PSU — fails with a known-good supply; `throttled=0x0`.
- Not USB power budget — `usb_max_current_enable=1` is effectively on; **Bat1's
  10″ monitor draws more and works**, so it isn't raw current.
- Not the firmware (May→Feb downgrade) — no effect on enumeration (it only
  affected the *boot stall*: newer firmware's "attempt power cycle" retry on the
  failed device dragged boot to ~100s; Feb fails faster).
- Not the kernel — version (6.18.33 **and** 6.12.75) and flavor (v8 + 2712) all fail.
- Not USB-controller sharing — audio + joystick share a controller fine *with no
  monitor*.
- Not a hub or software replug — passive hub doesn't help; a "VBUS cut" via
  uhubctl on the RTS5411 hub **or the Pi's own root port** only toggles the data
  port (the dongle's LED stays lit), so it can't replicate the physical replug.

**What it IS:** **powering the 7″ ROADOM monitor through the Pi's USB port
disrupts the dongle's *cold* enumeration** — globally (even on the other
controller), HDMI disconnected or not. A warm replug works because by then the
monitor's already up. Proven by: **monitor unplugged → dongle enumerates, 0
errors**; **monitor's USB power back → fails**. This also resolves the Bat1
paradox — its monitor isn't powered through the Pi's USB.

### The fix (one supply, no hub, no GPIO juggling of the dongle)
**Power the display from the GPIO 5V rail (header pins 2/4 = 5V, pin 6 = GND),
HDMI to the Pi.** Then the monitor's power never touches the Pi's USB, and the
dongle enumerates cleanly at boot. Verified on pi2: card 2 `WaveshareUSB`, HDMI
connected, all on the single PSU. (The ROADOM ships a GPIO-power cable for this.)

If the LED strip + monitor both on GPIO 5V is too much for the rail, **move the
LED strip's 5V/GND to a USB port** (data stays on GPIO 10) — safe because the
strip is OFF at boot (~20 mA, no inrush) and only draws once `ledcontrol` lights
it at ~5s, well after the dongle enumerates. (USB→2-pin 5V cable, 22 AWG.)

### Doc framing (tiered, simplest first)
1. **Default / simplest:** no dongle — use the **monitor's HDMI speakers**
   (works on the 7″/8″/10″). Zero audio config.
2. **Recommended ~$25 upgrade:** the USB sound card — louder/better, rock-solid
   on the 8″/10″ monitors.
3. **Advanced (this 7″ + dongle):** power the display from **GPIO 5V**, LEDs on USB.

The **audio auto-selector** (`setup/select-default-audio.{sh,service}`) makes the
flaky case graceful: at boot it sets the ALSA default to `WaveshareUSB` if present,
else the connected HDMI output — so there's always sound, dongle or not.

## picadeinstall — the one-command installer (design, as built)
`picadeinstall.sh` (repo root) sets up a blank-ish Pi OS box end-to-end:
`git clone … && sudo ./picadeinstall.sh`.
- **Modes:** full (default), `--update` (LED + audio + watchdog only — fast/safe,
  kernel-agnostic), `--reset` (also regenerate `ledcontrol.toml` from defaults).
- **On-by-default (opt-out):** persistent journald, boot-speed tweaks
  (`wait-online`/`nmbd`), WiFi watchdog (self-disabling).
- **Opt-in:** `--usb-audio`, `--usbromservice`, `--samba`.
- **Idempotent:** marker-bounded `config.txt`/`cmdline.txt` blocks (rewritten, not
  appended); user content (`ledcontrol.toml`, ROMs, saves) never touched without
  `--reset`.
- **Drift:** on a full re-run, compares current kernel/RetroPie to the stamp from
  the last success (`/etc/picadeinstall/state`); if they moved, **warns and offers
  to drop to `--update`** (the safe path) rather than hard-failing.
- **No forced regression-avoidance:** the upgrade isn't dangerous (the audio issue
  was the monitor, not the upgrade); we still do `apt full-upgrade` on full runs.
- `--leds N` (prompted if omitted) is the one genuinely per-cabinet value.

**TODO when integrating with install.sh:** wire `num_leds` from picadeinstall into
the LED install / `ledcontrol.toml` on first install only.

## SOLVED: volume control on a PipeWire image (RetroPie audio menu says "pulseaudio is running")

**Symptom:** on some boxes the RetroPie audio menu refuses ("pulseaudio is
running, can't do anything") and EmulationStation's volume slider doesn't change
anything — yet the desktop volume control works and persists.

**Why it happens — and why most cabinets never see it:** these boxes were imaged
from a **desktop-flavored Raspberry Pi OS**, which runs **PipeWire** (with the
`pipewire-pulse` shim) as the audio server. Almost nobody hits this because the
standard build uses the **RetroPie image** or **RPi OS Lite** — pure ALSA, no
sound server — where RetroPie/ES volume "just works." *It is not a Pi 5 / HDMI
problem; it's a "PipeWire got installed alongside RetroPie" problem.* **Prefer
the RetroPie / Lite image and this never comes up.**

On a PipeWire box, RetroPie's ALSA volume tooling is fighting PipeWire (which owns
the cards). Layers of the diagnosis:
- PipeWire is **per-user services** (`pipewire`, `pipewire-pulse`, `wireplumber`),
  *not* a system service — so it's maskable. The danger is **removing** the
  packages: `apt remove pipewire …` cascades out `rpd-x-core` / the whole
  Raspberry Pi Desktop core (this is what has crippled boxes before). **Never
  remove — only mask.**
- With PipeWire masked, raw ALSA returns, and the USB card exposes its full mixer
  including a **`Master`** that PipeWire had been abstracting away.
- But on the WaveShare/JMTek USB card, **`Master` is inert — `Speaker` is the real
  volume control.** EmulationStation defaults to driving `Master`, so the slider
  moved nothing. Pointing ES at `Speaker` fixes it.
- **HDMI has no hardware volume control at all**, so for the HDMI fallback we wrap
  it in an ALSA **`softvol`** that exposes a software `Master`, and point ES there.

**The fix (all automated now):**
1. `picadeinstall` **masks PipeWire** when present (`m_no_pipewire`; reversible,
   removes no packages; `--keep-pipewire` to skip).
2. The boot **audio selector** sets EmulationStation `AudioCard=default` and
   `AudioDevice=Speaker` for the USB card (or `Master` over softvol for HDMI).
3. Revert PipeWire anytime: `systemctl --user unmask pipewire.service
   pipewire.socket pipewire-pulse.service pipewire-pulse.socket wireplumber.service`.
