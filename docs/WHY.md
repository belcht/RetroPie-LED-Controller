# Why this works — what we had to solve

The [Quick Start](QUICKSTART.md) gets you running without reading any of this.
This page is the *why*: the non-obvious things a Pi 5 arcade build runs into, and
what `picadeinstall` does about each one — so you can trust it, adapt it, or use
it to troubleshoot your own box. Every fix here is also a **manual step** in the
[Manual install](MANUAL-INSTALL.md).

The single most useful thing to internalize: **most of the pain comes from the OS
image, not the Pi.** Use **RPi OS Lite** and almost none of the audio section
below ever applies to you.

---

## 1. The OS image (and PipeWire)

Raspberry Pi Imager's top default, *"Raspberry Pi OS (64-bit)"*, is the **Desktop**
image — and it runs **PipeWire** as the system sound server. PipeWire *owns* the
audio cards, which breaks the way RetroPie expects to control audio (the RetroPie
audio menu literally refuses with *"pulseaudio is running"*, and EmulationStation's
volume slider does nothing). Almost nobody building a cabinet hits this, because
the standard build uses the **RetroPie image or RPi OS Lite** — pure ALSA, no
sound server. **It is not a Pi 5 / HDMI problem; it's a "PipeWire got installed"
problem.**

**What the installer does:** if it detects PipeWire, it **masks** the per-user
PipeWire services (`pipewire`, `pipewire-pulse`, `wireplumber`). Critically it
*masks* — it never `apt remove`s them, because removing the packages cascades out
`rpd-x-core` / the entire Raspberry Pi Desktop core (a real way to brick a box).
Masking is reversible (`systemctl --user unmask …`) and removes nothing. On a Lite
image there's no PipeWire, so this step does nothing.

## 2. The USB sound card is finicky — taming it took real work

A cheap USB sound card is the recommended audio upgrade, but the JMTek/Waveshare
dongle (`0c76:1203`) fought us on two separate fronts. Both took a lot of
troubleshooting; both are now handled for you.

**It never keeps the same ALSA card number.** Depending on boot timing and which
USB port it's in, the dongle comes up as card 0, 1, *or* 2 — so anything that
addresses it as `hw:0`/`hw:1` works one boot and breaks the next. The fix is to
**virtualize its name**: a udev rule matches the dongle's USB VID:PID (`0c76:1203`)
and renames the card to a fixed **`WaveshareUSB`**, *regardless of port or index*.
Everything downstream — the ALSA default, the boot selector, the volume control —
then refers to that stable name, never a number. That one rule is the difference
between "audio works this boot" and "audio works **every** boot."

**With the 7″ ROADOM screen, it gets booted off the USB bus entirely.** When the
ROADOM panel is **powered through the Pi's USB**, the dongle **fails to enumerate at
cold boot** — the kernel logs `device descriptor read … error -71` / `unable to
enumerate` and the device is effectively *evicted from the bus*. It works fine on a
warm replug, and on a different monitor — which is exactly what made it so
maddening to chase. We ruled out, **empirically** (not by guessing): the dongle,
the port, *both* USB controllers, the PSU, the USB power budget, the firmware, and
the kernel. The actual culprit was **the monitor's USB power disrupting the
dongle's cold enumeration.** The fix: **power the display from the Pi's GPIO 5V
rail** (header pin 2/4 = 5V, pin 6 = GND; the ROADOM ships a cable for it) and run
HDMI for video — then the dongle enumerates clean on every cold boot. *(No USB
sound card → neither problem applies.)*

## 3. Audio output: USB sound card *or* the connected HDMI

There's no single "right" default output, and ALSA's bare default (card 0) is the
HDMI port nearest the USB-C jack — so a monitor on the *other* HDMI port gives
silence. A boot-time **selector** (`select-default-audio`) handles it: it sets the
default to the **USB sound card** (by the stable `WaveshareUSB` name from §2) if one
is present, otherwise the **connected** HDMI output. Plug the dongle in — now or
later — and it just becomes the default; pull it and it falls back to HDMI. No flags.

## 4. Audio volume control (the long one)

Getting the *volume* adjustable took untangling several layers — worth knowing if
you ever debug audio on one of these:

- With PipeWire masked (§1), raw ALSA returns and the USB card exposes a full
  mixer. But on the WaveShare/JMTek card, **`Master` is inert — `Speaker` is the
  real control.** EmulationStation defaults to driving `Master`, so the slider
  moved nothing. The selector points ES at the right control instead.
- **HDMI has *no* hardware volume control at all.** For the HDMI path we wrap it in
  an ALSA `softvol` that exposes a software `Master`, so the slider has something
  to turn. (dmix won't initialize on the vc4 HDMI device — `softvol` over `plughw`
  is what works.)
- **In EmulationStation → Sound Settings:** `AUDIO CARD = default`, and
  `AUDIO DEVICE = Speaker` (USB) or `Master` (HDMI). Must be `default`, *not*
  `hw`/`plughw`, or the choice won't stick. The selector sets these for you.

**Dual-purpose (also a desktop):** masking PipeWire silences the PIXEL desktop. So
on a Desktop image the installer also drops in a **`startx` wrapper** that turns
PipeWire on for the duration of a desktop session and off (re-masks) when you
leave — both worlds get sound, automatically. One gotcha it also handles:
`fluidsynth` (a MIDI-synth user service some packages pull in) opens and *holds*
the USB card, locking PipeWire out of it, so the installer masks that too.

## 5. LED power — direct off the GPIO (kept deliberately small)

This build powers the WS2812B strip **directly from the Pi 5 GPIO 5V** (data on
GPIO 10 / pin 19), no separate supply. That's only safe because it's kept small and
current-limited:
- ~60 mA/LED at full white; the firmware caps brightness at 80 % → ~48 mA/LED.
- 17 LEDs ≈ 0.82 A worst case; `MAX_LEDS = 20` hard-caps it at ~0.96 A — all under
  1 A, within the rail's headroom **on the official 27 W (5 V/5 A) PSU**.

> **Do this at your own risk, and don't scale it up.** Past ~20 LEDs or without the
> brightness cap, the rail sags (color shift / brownout). For any larger strip, use
> an external 5 V supply with a shared ground, a 330–470 Ω data resistor, and a
> 1000 µF cap — the standard WS2812B wiring.

## 6. Boot speed

A few RPi OS defaults stall an arcade boot, so the installer disables them:
- **Plymouth splash** (Desktop images) can hang ~2 min waiting on the display —
  drop `splash` from `cmdline.txt`.
- **`NetworkManager-wait-online`** blocks `multi-user.target` ~100 s when WiFi is
  slow to associate (so the LED strip stays dark that whole time) — disabled.
- **Samba `nmbd`** times out ~90 s at boot with no network — disabled (`smbd`
  stays).

## 7. WiFi resilience

The Pi 5's onboard WiFi (Broadcom CYW43455) talks to the SoC over an **SDIO bus**
that's fine for light use but bites under real load. It is **not** power or heat —
`vcgencmd get_throttled` reads `0x0` throughout — and shows up as three distinct,
all field-observed failure modes:

- **Association roulette on mesh networks (eero, Google WiFi).** The radio misses
  its initial 802.11 association on roughly *half* of boots — `status_code=16`
  (auth timeout). The box boots into EmulationStation fine, but `wlan0` has **no
  IP**; a manual reconnect always works (which is what makes it so easy to miss).
- **SDIO halt under sustained transmit.** A long upload — say a multi-GB ROM copy —
  wedges the bus: `brcmf_sdio_txfail` → *"failed backplane access over SDIO,
  halting operation."* The radio stays *associated* but moves ~0 data until a
  reboot.
- **Degraded receive after a kernel bump.** Occasionally it comes up seeing only a
  handful of APs — not even its own — with nothing logged to explain it.

**What the installer does (mitigate):** disables firmware roaming (`brcmfmac.conf`),
pins the band that actually associates and turns off power-save in NetworkManager,
makes the PSK system-owned so WiFi is up *before* login, and (optionally) frees the
chip's shared radio resources with `dtoverlay=disable-bt` — these cabinets don't use
Bluetooth. On top of that, a self-disabling **watchdog**: it only acts when *no*
interface has an IP, then reconnects and bounces the radio — cycling through every
WiFi device by name, so there's nothing to hardcode — until it's online, then idles.
It deliberately **does not** reload the `brcmfmac` driver: the unload almost always
fails (*"Module brcmfmac is in use"* — NetworkManager holds it), and on the rare
time it succeeds, reloading can leave the chip **half-wedged** (interface present
but RX-deaf) until a **cold power-cycle** — a soft reboot won't re-init it.
Reconnect + radio-bounce are the only *safe* recoveries.

**The real cure (for a box that must stay reliable under load):** bypass the onboard
radio entirely — a **USB WiFi adapter** (TP-Link Archer, driver `rtw88_8821au`) or
**wired Ethernet**. On the reference box, a USB adapter took a **79 GB transfer with
0 drops**, versus **554** on the onboard radio. The band-tuning commands and full
diagnosis are in [setup/README.md](../setup/README.md) and
[BUILD-NOTES.md](BUILD-NOTES.md).

---

*See also: [Quick Start](QUICKSTART.md) · [Manual install / troubleshooting](MANUAL-INSTALL.md) · recommended hardware + the full empirical diagnostics live in [BUILD-NOTES.md](BUILD-NOTES.md).*
