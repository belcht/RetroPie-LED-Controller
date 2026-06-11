# PiVert / RetroPie-on-Raspberry-Pi-OS box hardening

System-level configuration that makes a Raspberry Pi 5 arcade box reliable for
RetroPie. Each file here is the exact, proven config from the reference box
(PiVert).

> **You usually don't apply these by hand.** `picadeinstall.sh` (repo root)
> installs them for you: persistent logging, boot tweaks, and the WiFi watchdog
> on by default; the USB-audio pieces with `--usb-audio`. See
> [docs/BUILD.md](../docs/BUILD.md). This file documents what each piece does and
> why, for when you want to understand, tweak, or apply one manually. (`install.sh`
> — the *LED-only* installer — still deliberately applies none of these.)

Order doesn't matter, but do **persistent logging first** — if anything else
misbehaves, you'll then have logs that survive a reboot to diagnose it.

---

## 1. Persistent logging (`40-rpi-volatile-storage.conf`)

**Why:** Raspberry Pi OS ships `/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf`
with `Storage=volatile` — the systemd journal lives in RAM and is **wiped on
every reboot**. That makes intermittent boot problems (no network, failed
service) impossible to diagnose after the fact. This drop-in (same filename, in
`/etc`, so it overrides the stock one) switches logs to persistent on disk.

```bash
sudo cp setup/40-rpi-volatile-storage.conf /etc/systemd/journald.conf.d/
sudo systemctl restart systemd-journald
journalctl --list-boots          # should accumulate >1 boot after a reboot
```

## 2. USB audio stable naming (`asound.conf` + `90-waveshare-usb-audio.rules`)

**Why:** A USB sound card has no fixed ALSA index — depending on boot/enumeration
order it can come up as card 0, 1, or 2, and anything addressing it as `hw:0`
breaks. The udev rule gives the card a **stable name** (`WaveshareUSB`) by
matching its USB VID:PID (`0c76:1203` — the JMTek/Waveshare "USB PnP Audio
Device"), regardless of port or index. `asound.conf` then points the ALSA
default at that **name**. `plug`+`dmix` lets multiple apps share the card.

> If your dongle is a different model, change the `idVendor`/`idProduct` in the
> rule (find them with `lsusb`).

```bash
sudo cp setup/90-waveshare-usb-audio.rules /etc/udev/rules.d/
sudo cp setup/asound.conf                  /etc/asound.conf
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=sound --action=add
cat /proc/asound/card0/id        # -> WaveshareUSB (whatever index it lands on)
aplay -D default /usr/share/sounds/alsa/Front_Center.wav   # should play
```

RetroArch needs no card index — leave `audio_device = ""` so it follows the
ALSA default.

### 2a. Boot-time audio selector (`select-default-audio.{sh,service}`)

**Why:** there's no single "right" default output. The connected HDMI can be
card 0 **or** card 1 depending on which of the Pi's two HDMI ports you used (ALSA's
bare default is always card 0, so the *other* port gives silence), and a USB sound
card — great when present — won't always cold-enumerate (the JMTek `0c76:1203`
dongle fails to on the 7″ ROADOM when that display is powered through the Pi's USB;
full diagnosis in [docs/BUILD-NOTES.md](../docs/BUILD-NOTES.md), real fix is GPIO
5V power). So `picadeinstall` installs this selector on **every** build (not just
`--usb-audio`). This oneshot service runs once at boot, **before** EmulationStation,
and writes `/etc/asound.conf` to whatever's actually available:

- USB card present (`aplay -l` shows `WaveshareUSB`) → default to it (`dmix` so
  apps share it).
- Otherwise → default to the **connected HDMI** output (maps DRM `HDMI-A-1` →
  `vc4hdmi0`, `HDMI-A-2` → `vc4hdmi1`).

So you always get sound — USB when it came up, panel speakers when it didn't.

```bash
sudo cp setup/select-default-audio.sh      /usr/local/bin/
sudo cp setup/select-default-audio.service /etc/systemd/system/
sudo chmod +x /usr/local/bin/select-default-audio.sh
sudo systemctl enable --now select-default-audio.service
journalctl -t select-default-audio         # shows which output it picked
```

> Pairs with the naming rule in §2 — the selector greps for the name
> `WaveshareUSB`, so install them together (the rule is what creates that name).

## 3. WiFi reliability on a mesh / eero network

The Pi 5's onboard `brcmfmac` WiFi intermittently **fails its initial
association** with mesh networks (eero, Google WiFi) — 802.11 `status_code=16`
(auth timeout). Symptom: the box boots fine into EmulationStation but `wlan0`
has **no IP**, ~half the time. A manual reconnect always works. Three layers:

### 3a. `brcmfmac.conf` — disable firmware roaming

```bash
sudo cp setup/brcmfmac.conf /etc/modprobe.d/
# takes effect on next reboot (module reload)
```

### 3b. NetworkManager connection settings

Tune the connection profile (named `RetroPie-WiFi` on the reference box —
substitute your profile name from `nmcli connection show`):

```bash
CON="RetroPie-WiFi"
# Empirically this Pi + eero associates on 5 GHz and gets rejected on 2.4 GHz,
# so pin 5 GHz. (Use 'bg' for 2.4 GHz if YOUR setup is the reverse — check the
# journal for which band actually completes association.)
sudo nmcli connection modify "$CON" 802-11-wireless.band a
sudo nmcli connection modify "$CON" 802-11-wireless.powersave 2          # disable power save
sudo nmcli connection modify "$CON" connection.autoconnect-retries 0     # retry forever
```

Make sure the PSK is **system-owned** (`psk-flags: 0`) so it's available at boot
without a logged-in user:

```bash
sudo nmcli -g 802-11-wireless-security.psk-flags connection show "$CON"   # want 0
```

### 3c. `wifi-watchdog` — the safety net (on by default; self-disabling)

Even with the above, association still misses some boots. The watchdog runs the
same recovery you'd do by hand — reconnect → bounce radio → reload firmware —
until it's online, then idles. On the reference box it brings every boot online
within ~20–80 s, unattended.

It is **safe to install on every build**, so `picadeinstall` enables it by
default (skip with `--no-watchdog`). It's **self-disabling**: "online" means a
global IPv4 on **any** interface (eth0, wlan0, wlan1, …), so on Ethernet or
healthy WiFi it just idles. It only ever acts when there is **no IP anywhere** —
and then it cycles through **every** WiFi device by name discovery (onboard +
any USB adapter), so there's nothing to hardcode or edit. (This is the rewrite —
no `CON`/`IFACE` to tune.)

```bash
sudo install -m 755 setup/wifi-watchdog.sh      /usr/local/bin/wifi-watchdog.sh
sudo install -m 644 setup/wifi-watchdog.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-watchdog.service
journalctl -u wifi-watchdog.service -f           # watch it work
tail -f /var/log/wifi-watchdog.log
```

```bash
sudo install -m 755 setup/wifi-watchdog.sh      /usr/local/bin/wifi-watchdog.sh
sudo install -m 644 setup/wifi-watchdog.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-watchdog.service
journalctl -u wifi-watchdog.service -f           # watch it work
tail -f /var/log/wifi-watchdog.log
```

> Note: `--no-boot-tweaks` and `--no-watchdog` in `picadeinstall` cover 3c–3e
> together (the watchdog plus disabling `wait-online`/`nmbd`); the manual steps
> below are the same actions if you'd rather apply them piecemeal.

### 3d. Don't block boot waiting for WiFi

When WiFi fails to associate at boot, `NetworkManager-wait-online.service` stalls
the boot until its timeout (~100 s) — which delays `multi-user.target` and
everything ordered after it, including `ledcontrol.service` (so the **LED strip
stays dark ~100 s**). Nothing on an arcade box needs to block boot on network —
the watchdog (3c) brings WiFi up asynchronously — so disable it:

```bash
sudo systemctl disable NetworkManager-wait-online.service
```

Boot then proceeds immediately, WiFi connects in the background whenever it
manages to.

### 3e. Disable Samba `nmbd` (90 s boot timeout with no network)

`nmbd.service` (Samba's NetBIOS name daemon) takes **~90 s** to time out at boot
when WiFi isn't up yet, and it sits in the chain to `multi-user.target` — so it
slows the *entire* boot. `nmbd` only provides legacy "Network Neighborhood"
browsing; `smbd` (the actual file server) keeps working via `<host>.local`
(mDNS) or IP. Disable it:

```bash
sudo systemctl disable nmbd        # smbd stays enabled
```

> Note: even with the above, the **LED strip** is kept fast at boot by
> decoupling `ledcontrol.service` from the network chain
> (`After=basic.target`, not `network.target`/`multi-user.target`) — see
> `ledcontrol.service` in the repo root. Without that, any slow unit in the
> `multi-user.target` chain leaves the strip dark until it clears.

---

## Notes

- These are **box/OS** concerns, separate from the LED controller software
  (`install.sh`). They live here because every Pi in the fleet needs them, and
  the release/build doc walks through them.
- The reference box is **PiVert** (RetroPie on Raspberry Pi OS **Trixie / Debian 13, Lite**, Pi 5).
- Verify any service/boot fix by **rebooting**, not just restarting — boot is
  the path that actually matters, and it guarantees a clean process table.
