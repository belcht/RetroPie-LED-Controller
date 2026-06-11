# Arcade Build Guide

Building a Raspberry Pi 5 arcade cabinet running RetroPie, with reliable USB
audio and WS2812B LED lighting.

> This guide is intentionally **light on the generic steps** (flashing the OS,
> the stock RetroPie install — those are well documented elsewhere and change
> over time) and **deep on the parts specific to this build**: the recommended
> hardware, the audio + LED setup, and the box hardening that makes it boot fast
> and run reliably.
>
> Hardware bill-of-materials and OS-imaging sections are added separately; this
> file currently starts at first contact with a freshly-imaged, booted Pi.

---

## Step 1 — Reach your Pi and log in

At this point you've flashed Raspberry Pi OS, booted the Pi, and it has joined
your network. Before anything else, confirm you can reach it and log in over SSH
from your computer.

> **SSH must be enabled on the Pi.** The easiest way is in **Raspberry Pi
> Imager** before flashing: click the gear/⚙ (advanced options) and *Enable SSH*,
> set the **username + password**, and (optionally) the **hostname**. If you
> didn't, enable it on the Pi itself with `sudo raspi-config` →
> *Interface Options → SSH*.

Throughout this guide, substitute your own values:
- **`<host>`** — the Pi's hostname you set in the imager, e.g. `pi2` (reachable as `pi2.local`)
- **`<user>`** — the username you set in the imager, e.g. `pi`

### 1a. Is the Pi reachable on the network?

```bash
ping <host>.local           # e.g. ping pi2.local
```

You want replies like `64 bytes from 192.168.x.x ...`. Press `Ctrl-C` to stop.

- **If `ping` can't resolve `<host>.local`** (common on some Windows setups, or
  if mDNS is flaky), find the Pi's IP address instead — check your router's
  device list, or the Raspberry Pi Imager hostname you set — and use that IP in
  place of `<host>.local` everywhere below.

### 1b. Log in over SSH (first time, with your password)

```bash
ssh <user>@<host>.local     # e.g. ssh pi@pi2.local
```

- The **first** connection asks to trust the Pi's identity:
  `Are you sure you want to continue connecting (yes/no/[fingerprint])?` —
  type **`yes`** and press Enter. (This is normal and only happens once per Pi.)
- Enter the **password** you set in the imager when prompted.
- Success looks like a new prompt such as `pi@pi2:~ $`. You're now on the Pi.

A successful first login looks like this:

```text
$ ssh pi@pi2.local
pi@pi2.local's password:
Linux Pi2 6.12.75+rpt-rpi-2712 #1 SMP PREEMPT Debian ... aarch64

The programs included with the Debian GNU/Linux system are free software;
...
Last login: Wed Jun 10 09:14:32 2026 from 192.168.4.57
pi@Pi2:~ $
```

Type `exit` (or `Ctrl-D`) to return to your own computer.

**Troubleshooting**
| Symptom | Fix |
|---|---|
| `Could not resolve hostname <host>.local` | Use the Pi's IP address instead (see 1a). |
| `Connection refused` | SSH isn't enabled on the Pi — enable it (see the note above) and reboot. |
| `Permission denied (...password)` | Wrong username or password. The username is what you set in the imager, not necessarily `pi`. |

Once you can log in with your password, you have everything you need. The next
step just makes future logins effortless — it's **optional**.

---

## Step 2 — (Optional) Passwordless login with an SSH key

This saves you from typing the Pi's password every time, and is required if you
want to automate or script anything against the Pi. It's a one-time setup that
copies a small public "key" from your computer to the Pi. **Skip this if you'll
only ever work at the cabinet directly.**

> Run these on **your computer**, not on the Pi.

### 2a. Do you already have an SSH key?

```bash
ls ~/.ssh/id_ed25519.pub        # macOS / Linux
# Windows (PowerShell):  dir $env:USERPROFILE\.ssh\id_ed25519.pub
```

- **If it prints a path** — you already have a key, skip to **2c**.
- **If it says "No such file"** — make one in **2b**.

### 2b. Create a key (only if you don't have one)

```bash
ssh-keygen -t ed25519 -C "arcade"
```

- Press **Enter** to accept the default location (`~/.ssh/id_ed25519`).
- It asks for a passphrase. For a fully hands-off login, press **Enter** twice
  to leave it empty. (A passphrase is more secure but you'll be asked for it —
  not the Pi's password — on use.)

### 2c. Copy your key to the Pi

**macOS / Linux (easiest):**
```bash
ssh-copy-id <user>@<host>.local        # e.g. ssh-copy-id pi@pi2.local
```
Enter the Pi's password **one last time**. Done.

**If `ssh-copy-id` isn't available** (or on Windows PowerShell), do it manually —
this appends your public key to the Pi's authorized list:

```bash
# macOS / Linux
cat ~/.ssh/id_ed25519.pub | ssh <user>@<host>.local \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

```powershell
# Windows PowerShell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh <user>@<host>.local "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```
(Enter the Pi's password once when prompted.)

### 2d. Test it

```bash
ssh <user>@<host>.local
```

It should drop you straight to the Pi's prompt **with no password**. That's it —
passwordless login is set up.

---

## Step 3 — (Optional) Passwordless `sudo`

On a fresh **Desktop** image, the user you created needs to type a password for
`sudo`. That's fine if you'll always run admin commands by hand, but it blocks
unattended/remote management. (The RetroPie SD image and the Lite-based setups
already have passwordless `sudo`; the Desktop image just doesn't.)

To enable it, run these **two commands** on the Pi (you'll enter your password
once, for the first one):

```bash
echo "$USER ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/010-nopasswd-$USER
```
```bash
sudo chmod 0440 /etc/sudoers.d/010-nopasswd-$USER
```

After this, `sudo` no longer prompts for a password. **Skip this** if you prefer
to keep the password prompt for safety.

---

## Step 4 — Update the system and firmware

Bring the freshly-imaged OS fully up to date *before* installing anything else.

```bash
sudo apt update
sudo apt full-upgrade -y
```

> Use **`full-upgrade`**, not `upgrade` — a fresh image often needs dependency
> changes that plain `upgrade` won't do. On this build it pulled ~227 packages,
> including a newer kernel.

Update the Raspberry Pi 5 bootloader/firmware:

```bash
sudo rpi-eeprom-update -a
```

Confirm your locale is valid — RetroPie's installer scripts fail on a broken one:

```bash
locale
```

You want a `LANG=…UTF-8` line set and **no** "cannot set locale" warnings. The
imager's default (e.g. `en_GB.UTF-8` or `en_US.UTF-8`) is fine as-is. To change
it: `sudo raspi-config` → *Localisation Options → Locale*.

Reboot to load the new kernel and apply the firmware:

```bash
sudo reboot
```

When it comes back, confirm the update took:

```bash
uname -r                 # should show the new kernel
sudo rpi-eeprom-update   # CURRENT firmware date should be recent
```

> **On WiFi?** If your Pi is on WiFi and it comes back *without* an IP after a
> reboot (you can reach the desktop but not SSH), you may be hitting an
> association issue common on mesh networks (e.g. eero) — see the **optional
> WiFi reliability** section later. On a wired connection this won't happen.

---

## Step 5 — Install everything with `picadeinstall`

From here, one script installs RetroPie, the LED controller, the box hardening,
and (optionally) USB audio. Clone the repo and run it:

```bash
git clone https://github.com/belcht/RetroPie-LED-Controller.git
cd RetroPie-LED-Controller
sudo ./picadeinstall.sh
```

It prompts for the one thing that's truly per-cabinet — **how many LEDs** are in
your strip — and otherwise uses sensible defaults. On a fresh box this does the
full install:

- **RetroPie** (Core + Main packages) and boot-to-EmulationStation.
- **LED controller** — the WS2812B software and its `ledcontrol.service`.
- **Box hardening (on by default):** persistent logging (`journald`), boot-speed
  tweaks (disabling `systemd-networkd-wait-online` and `nmbd`), and a
  self-disabling WiFi watchdog.

### Options

```text
--leds N          number of WS2812B LEDs (prompted if omitted)
--auto            non-interactive (needs --leds); use defaults, no prompts
--update          re-apply ONLY the LED software + audio + watchdog (fast, safe)
--reset           full install AND reset ledcontrol.toml to defaults
--usb-audio       install USB sound-card support (see Step 6)
--usbromservice   RetroPie USB ROM service (load ROMs from a USB stick)
--samba           RetroPie Samba ROM shares (load ROMs over the network)
--no-upgrade      skip 'apt full-upgrade' (you did it in Step 4)
--no-retropie     skip the RetroPie install
--no-autostart    don't boot straight into EmulationStation
--no-journald / --no-boot-tweaks / --no-watchdog   skip a hardening piece
```

### Re-running it later

The script is **idempotent** — safe to run again. It manages its own
marker-bounded blocks in `config.txt`/`cmdline.txt` (rewritten, not duplicated),
and it **never touches your config, ROMs, or saves** unless you pass `--reset`.

For routine "pull the latest LED software" updates, use **`--update`**: it
re-applies only the LED controller, audio selector, and watchdog — fast, and it
doesn't touch the OS or RetroPie.

After a successful full install it records the kernel and RetroPie versions. If
you later run a **full** install again and those have moved on (a kernel update,
etc.), it **warns you and offers to drop to `--update`** instead — so a routine
re-run can't surprise you by rebuilding on top of a changed system.

---

## Step 6 — Audio

This build has three audio options, simplest first. **Pick one** — you don't need
the USB sound card unless you want it.

### Option A (default, simplest): the monitor's HDMI speakers

Do nothing. If your display has speakers (the 7″/8″/10″ panels in the BOM do),
`picadeinstall` installs a boot-time **audio selector** on every build that sets
the default output to **whichever HDMI port the monitor is actually connected
to** — so it works whether you used HDMI0 or HDMI1 on the Pi. This is the right
choice for most builds.

> Why this matters: with no selector, ALSA defaults to card 0 (the HDMI port
> nearest the USB-C power jack). If your cable is in the *other* port, you'd get
> silence. The selector detects the connected port and avoids that entirely.

### Option B (recommended upgrade, ~$25): a USB sound card + small amp/speaker

Louder and clearer than panel speakers, and rock-solid on the 8″/10″ monitors.
Install it with:

```bash
sudo ./picadeinstall.sh --update --usb-audio   # or include --usb-audio on a full run
```

This adds a udev rule that names the card **`WaveshareUSB`** no matter which port
it's on and raises the USB current cap. The **boot-time audio selector** (always
installed — see Option A) then prefers that USB card when it's present and falls
back to the connected HDMI when it isn't. So there's always sound either way.

### Option C (advanced): USB sound card on the 7″ ROADOM panel

The 7″ ROADOM has a quirk: **powering it through the Pi's USB port stops the USB
sound card from enumerating at boot** (a cold-start USB conflict — see
[BUILD-NOTES.md](BUILD-NOTES.md) for the full diagnosis). The fix is to **power
the display from the Pi's GPIO 5V rail** (header **pin 2 or 4 = 5V**, **pin 6 =
GND**; the ROADOM ships a cable for this) and run HDMI to the Pi. Then the
monitor's power never touches USB and the sound card enumerates cleanly.

If powering both the display **and** the LED strip from GPIO 5V is too much for
the rail, move the **LED strip's 5V/GND to a USB port** (keep its data wire on
GPIO 10). That's safe: the strip is dark at boot and only draws current once the
LED controller lights it a few seconds in — well after audio has come up.
