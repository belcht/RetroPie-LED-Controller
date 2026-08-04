# RetroPie LED Controller — Quick Start

Turn a Raspberry Pi 5 into an arcade cabinet: **RetroPie** + **WS2812B LED control**
(RetroLED) + reliable audio and WiFi, from one command.

> **The fast path is below.** Want to understand *why* each piece exists, or do
> any of it by hand? See **[Why this works](WHY.md)** and the
> **[Manual install](MANUAL-INSTALL.md)**. You don't need either to get running.

---

## Step 0 — Pick the right OS image (this is the important one)

In **Raspberry Pi Imager**, the option at the top — *"Raspberry Pi OS (64-bit)"* —
is the **full Desktop** image, and it ships **PipeWire**, which fights RetroPie's
audio. **You almost certainly want Lite instead**, and it's one menu deeper:

> **Choose OS → "Raspberry Pi OS (other)" → "Raspberry Pi OS Lite (64-bit)."**

| Your goal | Flash this | Why |
|---|---|---|
| **Arcade cabinet** (recommended) | **RPi OS Lite (64-bit)** | clean, no sound-server conflicts — everything below "just works" |
| **Also a desktop** (dual-purpose) | RPi OS Desktop (64-bit) | the installer handles the extra audio juggling for you (PipeWire, etc.) |

This is **RPi OS Lite**, *not* the prebuilt RetroPie image — the installer puts
RetroPie on for you.

## Step 1 — Flash it and set it up headless

In Raspberry Pi Imager, after picking Lite, click the **gear / ⚙ (Edit Settings)**
before writing and set:
- **Hostname** (e.g. `retropie`)
- **Username + password** — use **`pi`** as the username (a few scripts assume `/home/pi`)
- **Enable SSH** (password or your key)
- **WiFi** (SSID + password) and your **locale/Wi‑Fi country**

Write the card (or NVMe), put it in the Pi, and power on. Give it a minute to boot
and join your network.

## Step 2 — SSH in

From your computer:

```bash
ssh pi@retropie.local
```

If `.local` won't resolve, use the Pi's IP (check your router). Once you're at the
`pi@retropie:~ $` prompt, you're ready.

## Step 3 — Run the installer

```bash
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller
sudo ./picadeinstall.sh --leds 14
```

- Replace **`14`** with the number of LEDs in your strip.
- That's it — no other flags needed. USB audio, the volume fix, WiFi resilience,
  and (on a Desktop image) the PipeWire handling are all automatic.

> **Running it unattended / from another machine?** A background install can't
> stop to type a password, so first enable passwordless sudo:
> ```bash
> echo "$USER ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/010-nopasswd-$USER
> sudo chmod 0440 /etc/sudoers.d/010-nopasswd-$USER
> ```

## What it does (≈30–60 min, mostly RetroPie compiling)

1. Brings the OS fully up to date.
2. Installs **RetroPie** (Core + Main) and sets it to boot into EmulationStation.
3. Installs the **RetroLED** controller (the LED service + the on-screen UI under
   **Ports → RetroLED**) and sets your LED count.
4. Hardening: persistent logs, fast boot, a self-disabling WiFi watchdog, audio
   auto-selection (USB sound card if present, else the connected HDMI), and a
   working volume control.

## Done

Reboot when it finishes:

```bash
sudo reboot
```

It should come up straight into **EmulationStation**, your **LEDs** light, and
**sound works** (with a volume slider that actually moves — Sound Settings).

### Re-running / updating later

`picadeinstall.sh` is safe to re-run. For a quick "pull the latest LED + audio +
fixes" pass that **doesn't** touch RetroPie, your ROMs, or your config:

```bash
cd ~/RetroPie-LED-Controller && git pull && sudo ./picadeinstall.sh --update
```

---

*Next: [Why this works / what we had to solve](WHY.md) ·
[Do it by hand / troubleshoot](MANUAL-INSTALL.md)*
