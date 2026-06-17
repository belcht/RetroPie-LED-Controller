# Manual Install — doing every step by hand

This is the **manual counterpart** to the one-command installer. `picadeinstall.sh`
(see [BUILD.md](BUILD.md) Step 5) automates everything here; this document walks
through the *same* steps by hand, so you can follow, understand, and adapt each
one without the script.

The order matches the installer. Steps 1–4 (reach the Pi, SSH key, passwordless
`sudo`, OS update) are already manual in [BUILD.md](BUILD.md) — start there, then
come back here for RetroPie, the box hardening, audio, and the LED controller.

> Throughout: `<user>` is your login (default `pi`), and paths assume `/home/pi`.

---

## A. RetroPie (Core + Main) by hand

RetroPie isn't apt-installable; you clone its setup repo and run its installer.

### A1. Get RetroPie-Setup

Clone it **as your login user** (not root) — RetroPie runs its own git/file
operations as that user, and modern git refuses to touch a repo owned by someone
else ("dubious ownership"):

```bash
sudo apt install -y git dialog xmlstarlet joystick
cd ~
git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git
```

### A2. Basic install (Core + Main) — the menu way

This is the human-friendly path:

```bash
sudo ~/RetroPie-Setup/retropie_setup.sh
```

In the menu: **Manage packages → Basic install** → confirm. RetroPie installs the
**Core** packages (EmulationStation, RetroArch, runcommand) and the **Main**
packages (the well-supported emulator cores). On a Pi 5 it builds several cores
from source (RetroArch, SDL2, lr-fbneo, …) so it takes a while.

- **Core** = the frontend + RetroArch + runcommand (the things everything needs).
- **Main** = the curated, well-supported emulators. (Optional / Experimental tiers
  exist for everything else — install those later, per-system, from the same menu.)

### A3. Basic install — the headless/scriptable way

The exact same action without the dialog UI (this is what `picadeinstall` calls):

```bash
sudo __nodialog=1 ~/RetroPie-Setup/retropie_packages.sh setup basic_install
```

> Note the two entry points: `retropie_setup.sh` is the **dialog GUI**;
> `retropie_packages.sh` + `__nodialog=1` is the **non-interactive backend** that
> actually runs an action. Using the first with arguments just opens the menu.

### A4. Boot straight into EmulationStation (autostart)

Menu way: `sudo ~/RetroPie-Setup/retropie_setup.sh` → **Configuration / tools →
autostart → Start EmulationStation at boot**. Headless equivalent:

```bash
sudo __nodialog=1 ~/RetroPie-Setup/retropie_packages.sh autostart enable
```

Reboot; you should land in EmulationStation.

---

## B. Box hardening by hand

These make the box boot fast and stay reliable. Each is documented in full, with
the *why*, in **[../setup/README.md](../setup/README.md)** — do them in this order:

1. **Persistent logging** (setup/README §1) — keystone; do it first so later
   problems leave a trace across reboots. (`install -D` the journald drop-in.)
2. **Boot-speed tweaks** (setup/README §3d, §3e) — disable
   `NetworkManager-wait-online` and Samba `nmbd`.
3. **WiFi watchdog** (setup/README §3c) — only matters on flaky mesh WiFi; it
   self-disables otherwise, so it's safe to install on every build.

Each is one or two `cp`/`systemctl` commands; setup/README has them verbatim.

### B1. USB power budget (set by default)

Raise the Pi 5's USB current budget so USB-powered devices (monitor, touchscreen,
joystick, case extension, audio dongle) have headroom. The installer sets this on
every build; by hand it's one line in `config.txt` (then reboot):

```bash
echo "usb_max_current_enable=1" | sudo tee -a /boot/firmware/config.txt
```

Needs a 5 A / 27 W PSU (the official Pi 5 supply). On an underpowered supply, skip
it (`--no-usb-power`).

---

## C. Audio by hand

Pick the tier that matches your build (full rationale in [BUILD.md](BUILD.md)
Step 6 and the diagnosis in [BUILD-NOTES.md](BUILD-NOTES.md)).

### C1. HDMI / monitor speakers (default, no dongle)

The catch: ALSA's bare default is **card 0**, which is the HDMI port nearest the
USB-C jack. If your monitor is on the *other* HDMI port you'll get silence. The
boot **audio selector** fixes this by detecting the *connected* HDMI and pointing
the default there. Install it by hand (setup/README §2a):

```bash
sudo install -m 755 setup/select-default-audio.sh      /usr/local/bin/
sudo install -m 644 setup/select-default-audio.service /etc/systemd/system/
sudo systemctl enable --now select-default-audio.service
journalctl -t select-default-audio        # shows which output it chose
```

To skip the selector entirely, just make sure the monitor is on the HDMI port
**nearest the USB-C power jack** (HDMI0), and audio works with no config.

### C2. USB sound card (auto-enabled when present)

The stable-naming udev rule is **harmless without a dongle** (it only matches the
dongle's USB ID), so the installer drops it on every build by default — meaning a
plugged-in USB sound card is auto-named and the selector from C1 prefers it, with
HDMI as the fallback. To do it by hand:

```bash
sudo cp setup/90-waveshare-usb-audio.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=sound --action=add
```

The USB current cap (`usb_max_current_enable=1`) is covered in §B1. See also the
**GPIO-5V monitor-power** requirement in section E if you're on the 7″ ROADOM
panel. (To force HDMI even with a dongle plugged in, just skip the udev rule.)

### C3. Volume control on a *desktop* image (mask PipeWire)

Only needed if you imaged a **desktop** Raspberry Pi OS (it runs **PipeWire**,
which breaks RetroPie's ALSA volume control — the RetroPie audio menu says
"pulseaudio is running"). The RetroPie/Lite image has no PipeWire and needs none
of this. **Mask** the per-user PipeWire services (reversible; never `apt remove`
them — that cascades out the whole Pi Desktop core):

```bash
systemctl --user mask pipewire.service pipewire.socket \
  pipewire-pulse.service pipewire-pulse.socket wireplumber.service
# reboot. revert anytime with: systemctl --user unmask <same units>
```

Then point EmulationStation's volume slider at the control that actually works —
`Speaker` on the WaveShare USB card (its `Master` is inert), or `Master` over a
softvol for HDMI (the selector in §C1 sets this up). In ES: **Sound Settings →
AUDIO CARD = default, AUDIO DEVICE = Speaker** (the installer's audio selector
sets these for you).

---

## D. LED controller by hand

This is what `install.sh` automates. Do it from the repo checkout (`~/picade-src`
or wherever you cloned it). Every path below is hard-coded to `/home/pi`.

### D1. Python environment

```bash
mkdir -p /home/pi/LEDControl && cd /home/pi/LEDControl
python3 -m venv venv
source venv/bin/activate && pip install --upgrade pip -q && pip install rpi5-ws2812 -q && deactivate
```

### D2. Copy the code + config

```bash
cp -f LEDControl.py update_config.py led-ws-cmd.py led-game-start.sh led-game-end.sh /home/pi/LEDControl/
chmod +x /home/pi/LEDControl/led-*.sh /home/pi/LEDControl/led-ws-cmd.py
# Config — copy once, then EDIT num_leds to match your strip (MAX 20):
cp -n ledcontrol.toml /home/pi/ledcontrol.toml      # -n = don't clobber an existing one
# the RetroLED pygame UI + its vendored websockets:
mkdir -p /home/pi/LEDControl/retro-led/vendor
cp -f retro-led/retro-led.py /home/pi/LEDControl/retro-led/
cp -rf retro-led/vendor/. /home/pi/LEDControl/retro-led/vendor/
```

Set your LED count: edit `/home/pi/ledcontrol.toml`, `[hardware] num_leds = N`.

### D3. Enable SPI (the LED data bus)

The strip's data line is driven over SPI MOSI. Enable SPI and reboot:

```bash
sudo raspi-config nonint do_spi 0     # or: raspi-config -> Interface Options -> SPI -> enable
```

After a reboot you should have `/dev/spidev0.0`.

### D4. Services (auto-start + clean shutdown)

```bash
sudo cp -f ledcontrol.service leds-off.service /etc/systemd/system/
sudo cp -f leds-off-on-shutdown.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/leds-off-on-shutdown.sh
# let the pi user restart the service without a password:
echo "pi ALL=(ALL) NOPASSWD: /bin/systemctl start ledcontrol.service, /bin/systemctl stop ledcontrol.service, /bin/systemctl restart ledcontrol.service" | sudo tee /etc/sudoers.d/ledcontrol >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now ledcontrol.service leds-off.service
```

`ledcontrol.service` runs `LEDControl.py` (the long-running LED service);
`leds-off.service` blanks the strip on shutdown.

### D5. Per-game LED reactions (RunCommand hooks)

RetroPie fires these scripts when a game launches/exits:

```bash
# append the LED hooks to RetroPie's runcommand scripts:
echo '/home/pi/LEDControl/led-game-start.sh "$@"' | sudo tee -a /opt/retropie/configs/all/runcommand-onstart.sh
echo '/home/pi/LEDControl/led-game-end.sh "$@"'   | sudo tee -a /opt/retropie/configs/all/runcommand-onend.sh
```

(They fire-and-forget a WebSocket command to the already-running service — nothing
is started or killed per game.)

### D6. The RetroLED UI in the Ports menu

```bash
sudo apt install -y python3-pygame
mkdir -p /home/pi/RetroPie/roms/ports
cat > /home/pi/RetroPie/roms/ports/RetroLED.sh <<'EOF'
#!/bin/bash
cd /home/pi/LEDControl/retro-led
python3 /home/pi/LEDControl/retro-led/retro-led.py
EOF
chmod +x /home/pi/RetroPie/roms/ports/RetroLED.sh
```

Drop the cover art at
`/home/pi/.emulationstation/gamelists/ports/images/retro-led.png` and add a
`<game>` entry for `./RetroLED.sh` to
`/home/pi/.emulationstation/gamelists/ports/gamelist.xml`. RetroLED then appears
under **Ports → RetroLED** after you restart EmulationStation. (On a fresh box,
`es_systems.cfg` doesn't exist until ES first runs — RetroPie generates it and
shows Ports automatically because `roms/ports` now has a launcher.)

### D7. Quick test

```bash
/home/pi/LEDControl/venv/bin/python3 /home/pi/LEDControl/LEDControl.py --animate kitt --color red
```

---

## E. Wiring by hand

Full reasoning and the power math are in [BUILD-NOTES.md](BUILD-NOTES.md). The
essentials:

- **LED data:** GPIO 10 = **physical pin 19** (SPI MOSI) → the strip's **DIN**
  (data-*in*; the arrows on the strip point away from this end). A common mistake
  is pin **21** (GPIO 9 / SPI MISO, an input) — the strip then gets power but no
  data and stays dark.
- **LED 5V/GND:** off the Pi 5V (GPIO rail or a USB port). The strip is dark at
  boot and only draws once the service lights it (~5s in), so USB power is fine.
- **Monitor power — only matters with a USB sound card:** powering the 7″ ROADOM
  through the Pi's USB stops the dongle cold-enumerating at boot. Power the
  display from **GPIO 5V (pins 2/4 = 5V, 6 = GND)** instead. With **no** USB
  dongle, this doesn't apply — the monitor can take power (and touch) over USB.
```
