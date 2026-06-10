# PiVert / RetroPie-on-Raspberry-Pi-OS box hardening

System-level configuration that makes a Raspberry Pi 5 arcade box reliable for
RetroPie. These are **manual, documented steps** — `install.sh` (the LED
software installer) deliberately does **not** apply them. Each file here is the
exact, proven config from the reference box (PiVert). Copy the ones you need.

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

### 3c. `wifi-watchdog` — the safety net (OPT-IN, not in install.sh)

Even with the above, association still misses some boots. The watchdog detects
"no IP on wlan0" and runs the same recovery you'd do by hand — reconnect →
bounce radio → reload firmware — until it's online, then idles. On the reference
box it brings every boot online within ~20–80 s, unattended.

> Edit `CON`/`IFACE` at the top of `wifi-watchdog.sh` if your profile/interface
> names differ.

```bash
sudo install -m 755 setup/wifi-watchdog.sh      /usr/local/bin/wifi-watchdog.sh
sudo install -m 644 setup/wifi-watchdog.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-watchdog.service
journalctl -u wifi-watchdog.service -f           # watch it work
tail -f /var/log/wifi-watchdog.log
```

---

## Notes

- These are **box/OS** concerns, separate from the LED controller software
  (`install.sh`). They live here because every Pi in the fleet needs them, and
  the release/build doc walks through them.
- The reference box is **PiVert** (RetroPie on Raspberry Pi OS Bookworm, Pi 5).
- Verify any service/boot fix by **rebooting**, not just restarting — boot is
  the path that actually matters, and it guarantees a clean process table.
