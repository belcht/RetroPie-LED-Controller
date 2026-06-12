#!/usr/bin/env bash
# picadeinstall — one-command setup for a RetroPie arcade cabinet (Raspberry Pi 5)
# with the WS2812B LED controller and reliability hardening.
#
#   blank SD -> flash Raspberry Pi OS -> boot -> git clone -> sudo ./picadeinstall.sh
#
# Idempotent: safe to re-run. System config is written in marked blocks that are
# rewritten (never appended); user content (ledcontrol.toml, ROMs, saves) is never
# touched except with --reset. See docs/BUILD.md for what each piece does and why.
set -uo pipefail

# ───────────────────────── locations ─────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$REPO_DIR/setup"
STATE_DIR="/etc/picadeinstall"
STATE_FILE="$STATE_DIR/state"
BOOT_CFG="/boot/firmware/config.txt";   [ -f "$BOOT_CFG" ]     || BOOT_CFG="/boot/config.txt"
BOOT_CMDLINE="/boot/firmware/cmdline.txt"; [ -f "$BOOT_CMDLINE" ] || BOOT_CMDLINE="/boot/cmdline.txt"
MARK_BEGIN="# >>> picadeinstall (managed) >>>"
MARK_END="# <<< picadeinstall <<<"

# user that owns the install (the non-root login, e.g. 'pi')
TARGET_USER="${SUDO_USER:-pi}"
TARGET_HOME="$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)"; TARGET_HOME="${TARGET_HOME:-/home/$TARGET_USER}"

# ───────────────────────── defaults ─────────────────────────
MODE="full"            # full | update | reset
AUTO=0
DO_UPGRADE=1
DO_RETROPIE=1
DO_AUTOSTART=1
DO_JOURNALD=1
DO_BOOT_TWEAKS=1
DO_USB_POWER=1         # raise USB current budget (default on; --no-usb-power to skip)
DO_WATCHDOG=1
DO_USB_AUDIO=0         # opt-in
DO_USBROMSERVICE=0     # opt-in
DO_SAMBA=0             # opt-in
NUM_LEDS=""

# ───────────────────────── pretty output ─────────────────────────
b(){ printf '\033[1m%s\033[0m' "$*"; }
step(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok(){   printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn(){ printf '    \033[33m!\033[0m %s\n' "$*"; }
info(){ printf '      %s\n' "$*"; }
die(){  printf '\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

usage(){ cat <<EOF
$(b picadeinstall) — set up a RetroPie arcade box (Pi 5) + LED controller.

  sudo ./picadeinstall.sh [options]

Modes:
  (default)         full install: OS update, RetroPie, hardening, LED software
  --update          re-apply ONLY LED software + audio + watchdog (fast, safe re-run)
  --reset           full install AND reset user config (ledcontrol.toml) to defaults

Options:
  --leds N          number of WS2812B LEDs in the strip (prompted if omitted)
  --auto            non-interactive: use defaults, no prompts (needs --leds)
  --no-upgrade      skip 'apt full-upgrade'
  --no-retropie     skip the RetroPie install
  --no-autostart    don't set boot-to-EmulationStation
  --no-journald     skip persistent logging
  --no-boot-tweaks  skip boot-speed tweaks (disable wait-online / nmbd)
  --no-usb-power    don't set usb_max_current_enable=1 (default sets it; needs 5A/27W PSU)
  --no-watchdog     skip the WiFi watchdog (it self-disables anyway)
  --usb-audio       add USB sound-card support (stable naming + max USB current).
                    The boot audio auto-selector is installed either way; this
                    just lets it prefer the USB card when one is plugged in.
  --usbromservice   install RetroPie USB ROM service
  --samba           install RetroPie Samba ROM shares
  -h, --help        show this help
EOF
}

# ───────────────────────── arg parsing ─────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --update) MODE="update" ;;
    --reset)  MODE="reset" ;;
    --auto)   AUTO=1 ;;
    --leds)   NUM_LEDS="${2:-}"; shift ;;
    --no-upgrade) DO_UPGRADE=0 ;;
    --no-retropie) DO_RETROPIE=0 ;;
    --no-autostart) DO_AUTOSTART=0 ;;
    --no-journald) DO_JOURNALD=0 ;;
    --no-boot-tweaks) DO_BOOT_TWEAKS=0 ;;
    --no-usb-power) DO_USB_POWER=0 ;;
    --no-watchdog) DO_WATCHDOG=0 ;;
    --usb-audio) DO_USB_AUDIO=1 ;;
    --usbromservice) DO_USBROMSERVICE=1 ;;
    --samba) DO_SAMBA=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

[ "$(id -u)" -eq 0 ] || die "run with sudo:  sudo ./picadeinstall.sh"
[ -d "$SETUP_DIR" ]   || die "setup/ not found next to this script — run from the repo checkout"

# ───────────────────────── state / drift ─────────────────────────
cur_kernel(){ uname -r; }
cur_retropie(){ local d="$TARGET_HOME/RetroPie-Setup"; [ -d "$d" ] && git -C "$d" -c safe.directory="$d" rev-parse --short HEAD 2>/dev/null || echo "none"; }

read_state(){ [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || true; }
write_state(){
  install -d "$STATE_DIR"
  cat > "$STATE_FILE" <<EOF
# Written by picadeinstall on success. Used to detect drift on re-run.
picadeinstall_date=$(date '+%Y-%m-%d %H:%M:%S')
kernel=$(cur_kernel)
retropie=$(cur_retropie)
EOF
}

# Compare current kernel/RetroPie to the last successful install; on a full run,
# if they moved, warn and offer to drop to --update instead.
drift_gate(){
  [ -f "$STATE_FILE" ] || return 0    # first install, nothing to compare
  local old_k old_r; old_k="$(sed -n 's/^kernel=//p' "$STATE_FILE")"; old_r="$(sed -n 's/^retropie=//p' "$STATE_FILE")"
  local new_k new_r; new_k="$(cur_kernel)"; new_r="$(cur_retropie)"
  [ "$old_k" = "$new_k" ] && [ "$old_r" = "$new_r" ] && return 0
  step "Heads up — your system changed since the last install"
  [ "$old_k" != "$new_k" ] && info "kernel:   $old_k  →  $new_k"
  [ "$old_r" != "$new_r" ] && info "RetroPie: $old_r  →  $new_r"
  info "A full re-install on a changed base is heavy and rarely what you want."
  info "If something hardware-level (USB audio, etc.) misbehaves, see docs/BUILD.md."
  [ "$AUTO" = 1 ] && { warn "--auto: proceeding with full install anyway"; return 0; }
  local ans; read -rp "    [U] Update only (recommended) / [F] Full install anyway? [U/f] " ans
  case "${ans:-U}" in
    [Ff]*) info "proceeding with full install" ;;
    *) info "switching to --update"; MODE="update" ;;
  esac
}

# ───────────────────────── config helpers ─────────────────────────
# Replace our marked block in a file (idempotent; never duplicates).
write_managed_block(){   # $1=file  $2=block-body
  local f="$1" body="$2" tmp; tmp="$(mktemp)"
  [ -f "$f" ] && sed "/^${MARK_BEGIN}$/,/^${MARK_END}$/d" "$f" > "$tmp" || true
  { printf '%s\n%s\n%s\n' "$MARK_BEGIN" "$body" "$MARK_END"; } >> "$tmp"
  install -m "$(stat -c %a "$f" 2>/dev/null || echo 644)" "$tmp" "$f"; rm -f "$tmp"
}
backup_once(){ [ -f "$1" ] && [ ! -f "$1.picadeinstall.bak" ] && cp "$1" "$1.picadeinstall.bak" || true; }

# ───────────────────────── modules ─────────────────────────
m_upgrade(){
  [ "$DO_UPGRADE" = 1 ] || { info "skipped (--no-upgrade)"; return; }
  step "Updating the OS (apt)"
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get -y \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade
  ok "OS up to date"
}

# Drive RetroPie's NON-interactive backend. retropie_setup.sh is the dialog GUI;
# retropie_packages.sh + __nodialog=1 is what actually runs an action headless
# (this is exactly how RetroPie's own image builder installs unattended).
# SUDO_USER points it at the login user (so it installs to that user's home and
# runs git on the repo as that user — the repo is owned by them).
rsetup(){ HOME=/root SUDO_USER="$TARGET_USER" __nodialog=1 "$TARGET_HOME/RetroPie-Setup/retropie_packages.sh" "$@"; }

m_retropie(){
  [ "$DO_RETROPIE" = 1 ] || { info "skipped (--no-retropie)"; return; }
  step "Installing RetroPie (Core + Main)"
  apt-get install -y git dialog xmlstarlet joystick lsb-release
  local rps="$TARGET_HOME/RetroPie-Setup"
  # RetroPie-Setup runs its git/file ops as the login user (via SUDO_USER), so
  # the repo must be owned by that user or git aborts with "dubious ownership".
  if [ ! -d "$rps" ]; then
    sudo -u "$TARGET_USER" git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git "$rps"
  else
    chown -R "$TARGET_USER":"$TARGET_USER" "$rps" 2>/dev/null || true   # heal ownership from an earlier run
    info "RetroPie-Setup already present — updating"
    sudo -u "$TARGET_USER" git -C "$rps" pull --ff-only || true
  fi
  rsetup setup basic_install
  [ "$DO_AUTOSTART" = 1 ] && { rsetup autostart enable; ok "boot-to-EmulationStation enabled"; }
  [ "$DO_USBROMSERVICE" = 1 ] && rsetup usbromservice || true
  [ "$DO_SAMBA" = 1 ] && { rsetup samba depends; rsetup samba install_shares; } || true
  ok "RetroPie installed"
}

m_journald(){
  [ "$DO_JOURNALD" = 1 ] || { info "skipped (--no-journald)"; return; }
  step "Persistent logging"
  # -D creates /etc/systemd/journald.conf.d/ — it doesn't exist on a fresh image.
  install -D -m 644 "$SETUP_DIR/40-rpi-volatile-storage.conf" /etc/systemd/journald.conf.d/40-rpi-volatile-storage.conf
  systemctl restart systemd-journald; journalctl --flush 2>/dev/null || true
  ok "journald -> persistent"
}

m_boot_tweaks(){
  [ "$DO_BOOT_TWEAKS" = 1 ] || { info "skipped (--no-boot-tweaks)"; return; }
  step "Boot-speed tweaks"
  systemctl disable NetworkManager-wait-online.service 2>/dev/null && ok "disabled wait-online" || true
  systemctl disable nmbd 2>/dev/null && ok "disabled Samba nmbd (90s boot stall)" || info "nmbd not present"
}

# Raise the Pi 5 USB current budget (default on). Useful for ANY USB-powered
# device — monitor, touchscreen, joystick, case extension, audio dongle — and
# harmless on the official 27W PSU. Opt out with --no-usb-power.
m_usb_power(){
  [ "$DO_USB_POWER" = 1 ] || { info "skipped (--no-usb-power)"; return; }
  step "USB power budget (usb_max_current_enable=1)"
  backup_once "$BOOT_CFG"
  write_managed_block "$BOOT_CFG" "# Raise USB current budget for downstream devices (needs a 5A / 27W PSU).
usb_max_current_enable=1"
  ok "usb_max_current_enable=1 set in $(basename "$BOOT_CFG")"
}

# USB-audio-specific bits (opt-in): stable name for the dongle. The USB current
# cap is handled by m_usb_power (default on). Runs BEFORE m_audio so the
# selector's one-shot run sees the named card.
m_usb_audio(){
  [ "$DO_USB_AUDIO" = 1 ] || { info "USB audio not selected — selector will default to the connected HDMI/monitor speakers"; return; }
  step "USB sound-card support (stable naming)"
  install -m 644 "$SETUP_DIR/90-waveshare-usb-audio.rules" /etc/udev/rules.d/90-waveshare-usb-audio.rules
  udevadm control --reload; udevadm trigger --subsystem-match=sound --action=add 2>/dev/null || true
  ok "USB audio: stable name 'WaveshareUSB'"
  warn "If powering the display through the Pi's USB, the dongle may not enumerate at boot."
  info "  -> power the display from the GPIO 5V rail instead. See docs/BUILD.md (USB audio)."
}

# Audio selector (ALWAYS): at boot, default ALSA to the USB card if present
# (named by --usb-audio), else the *connected* HDMI output — so there is always
# sound, on whichever HDMI port the monitor is actually plugged into.
m_audio(){
  step "Audio output auto-selector (connected HDMI, or USB card when present)"
  install -m 755 "$SETUP_DIR/select-default-audio.sh" /usr/local/bin/select-default-audio.sh
  install -m 644 "$SETUP_DIR/select-default-audio.service" /etc/systemd/system/select-default-audio.service
  systemctl daemon-reload; systemctl enable select-default-audio.service >/dev/null 2>&1
  /usr/local/bin/select-default-audio.sh || true
  ok "audio selector installed + enabled (picks the connected output at boot)"
}

m_watchdog(){
  [ "$DO_WATCHDOG" = 1 ] || { info "skipped (--no-watchdog)"; return; }
  step "WiFi watchdog (self-disabling — no-op unless WiFi is the only path and it's down)"
  install -m 755 "$SETUP_DIR/wifi-watchdog.sh" /usr/local/bin/wifi-watchdog.sh
  install -m 644 "$SETUP_DIR/wifi-watchdog.service" /etc/systemd/system/wifi-watchdog.service
  systemctl daemon-reload; systemctl enable --now wifi-watchdog.service >/dev/null 2>&1
  ok "watchdog installed (idles when any interface has an IP)"
}

m_leds(){
  step "LED controller software"
  if [ -z "$NUM_LEDS" ]; then
    if [ "$AUTO" = 1 ]; then die "--auto needs --leds N (LED count is per-cabinet)"; fi
    read -rp "    How many WS2812B LEDs in your strip? [14] " NUM_LEDS; NUM_LEDS="${NUM_LEDS:-14}"
  fi
  [[ "$NUM_LEDS" =~ ^[0-9]+$ ]] || die "--leds must be a number"
  [ "$NUM_LEDS" -le 20 ] || warn "MAX_LEDS=20 (power safety) — the service will clamp to 20"
  # --reset: move the existing config aside so install.sh regenerates defaults.
  local toml="$TARGET_HOME/ledcontrol.toml"
  local had_toml=0; [ -f "$toml" ] && had_toml=1
  if [ "$MODE" = "reset" ] && [ "$had_toml" = 1 ]; then
    mv "$toml" "$toml.bak" 2>/dev/null && had_toml=0
    warn "ledcontrol.toml moved aside (.bak) — defaults will be regenerated"
  elif [ "$had_toml" = 1 ]; then
    info "leaving existing ledcontrol.toml untouched (use --reset to regenerate)"
  fi
  # hand the LED software install to the existing installer (idempotent there;
  # it copies the default ledcontrol.toml only when one isn't already present)
  if [ -x "$REPO_DIR/install.sh" ]; then
    bash "$REPO_DIR/install.sh"
  else
    warn "install.sh not found — LED software not installed"
  fi
  # Only set num_leds when we created the config this run (fresh box or --reset);
  # never clobber a user's existing tuned value. Patch only the [hardware] line.
  if [ "$had_toml" = 0 ] && [ -f "$toml" ]; then
    awk -v n="$NUM_LEDS" '!d && /^num_leds[ \t]*=/ {print "num_leds = " n; d=1; next} {print}' \
      "$toml" > "$toml.tmp" && mv "$toml.tmp" "$toml"
    chown "$TARGET_USER": "$toml" 2>/dev/null || true
    ok "LED software installed; num_leds set to $NUM_LEDS"
  else
    ok "LED software installed (num_leds left at the existing config value)"
  fi
}

# ───────────────────────── flows ─────────────────────────
run_full(){
  step "picadeinstall — full install for $TARGET_USER"
  drift_gate
  if [ "$MODE" = "update" ]; then run_update; return; fi
  m_upgrade
  m_journald
  m_boot_tweaks
  m_usb_power
  m_usb_audio
  m_audio
  m_watchdog
  m_retropie
  m_leds
  write_state
  step "Done — reboot to bring it all up cleanly:  sudo reboot"
}

run_update(){
  step "picadeinstall --update (LED + audio + watchdog only)"
  m_usb_audio
  m_audio
  m_watchdog
  m_leds
  write_state
  step "Update complete. Reboot if the kernel/services changed."
}

case "$MODE" in
  update) run_update ;;
  reset)  warn "--reset: user config (ledcontrol.toml) will be regenerated from defaults"; run_full ;;
  full)   run_full ;;
esac
