#!/bin/bash
# wifi-watchdog.sh — keep the box online when its network comes over WiFi.
#
# Self-disabling by design, so it's safe to install on EVERY build:
#   * "Online" means a global IPv4 on ANY interface (eth0, wlan0, wlan1, ...).
#   * If anything has an IP, it does nothing but idle.
#   * Only when there is NO IP anywhere does it try to recover — and it cycles
#     through EVERY WiFi device (onboard + any USB adapter), no hardcoded names.
#
# Net effect: on Ethernet it idles, on healthy WiFi it idles, on a box with no
# WiFi it idles. It only ever acts on a genuinely-offline WiFi box — which is
# the flaky-mesh (e.g. eero) case it exists for. Installed by the installer as
# wifi-watchdog.service.
set -u
LOG=/var/log/wifi-watchdog.log
log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

# Real-uplink IPv4? EXCLUDE virtual interfaces (docker/veth/bridge/VPN) — otherwise a
# box running Docker (docker0=172.17.0.1) or Tailscale looks permanently "online" and
# this watchdog never fires. Only physical uplinks (eth*, end*, wlan*, wlx*, ...) count.
_real_ips(){ ip -4 -o addr show scope global 2>/dev/null \
    | awk '$2 !~ /^(docker|veth|br-|virbr|tailscale|tun|tap|wg|zt|cni|flannel|dummy|lo)/'; }
have_ip(){ _real_ips | grep -q inet; }
# all WiFi interface names (wlan0, wlan1, wlx..., etc.)
wifi_devs(){ for d in /sys/class/net/*/wireless; do [ -e "$d" ] && basename "$(dirname "$d")"; done; }
ips(){ _real_ips | awk '{print $2"="$4}' | tr '\n' ' '; }

[ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 1000000 ] && : > "$LOG"
log "watchdog started; wifi devices: $(wifi_devs | tr '\n' ' ')"

# Grace period: let NetworkManager bring things up on its own first.
for _ in $(seq 1 20); do systemctl is-active --quiet NetworkManager && break; sleep 1; done
for _ in $(seq 1 25); do have_ip && break; sleep 1; done
have_ip && log "online during grace period ($(ips))"

fails=0
while true; do
    if have_ip; then
        if [ "$fails" -ne 0 ]; then log "ONLINE ($(ips))"; fails=0; fi
        sleep 20
        continue
    fi

    # No IP on any interface — try to bring up each WiFi device.
    fails=$((fails + 1))
    log "no IP on any interface (consecutive failures: $fails) — recovering WiFi"
    for dev in $(wifi_devs); do
        log "  trying device $dev"
        timeout 30 nmcli device connect "$dev" >>"$LOG" 2>&1
        have_ip && { log "recovered via $dev ($(ips))"; break; }
    done
    have_ip && continue

    # Escalate every 3rd failure — bounce the radios.
    if [ $((fails % 3)) -eq 0 ]; then
        log "escalate: radio off/on"
        nmcli radio wifi off >>"$LOG" 2>&1; sleep 3
        nmcli radio wifi on  >>"$LOG" 2>&1; sleep 8
    fi
    # NOTE: we deliberately do NOT reload the brcmfmac module here.
    # A `modprobe -r brcmfmac` reload is unsafe and ineffective as a recovery step:
    #   * It almost always fails with "Module brcmfmac is in use" (NetworkManager /
    #     the netdev hold it open), so it does nothing — confirmed in the field.
    #   * When it *does* unload, a reload at a bad moment is a known way to leave the
    #     onboard chip half-wedged (deaf RX / no association) until a COLD power-cycle
    #     — a soft reboot won't fully re-init it. Net negative.
    # The reconnect + radio off/on steps above are the safe recovery. For a box that
    # must stay reliable under sustained load, the real fix is a USB WiFi adapter or
    # Ethernet (bypasses the onboard SDIO WiFi) — see README §3. (removed 2026-06-15)

    sleep 8
done
