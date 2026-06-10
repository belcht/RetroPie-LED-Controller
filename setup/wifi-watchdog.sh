#!/bin/bash
# wifi-watchdog.sh — keep wlan0 online on flaky brcmfmac + mesh (eero) setups.
#
# The Raspberry Pi's onboard brcmfmac WiFi intermittently fails its INITIAL
# association at boot (802.11 status_code=16 = auth timeout), leaving the Pi
# with the interface up but NO IP address. A manual reconnect always succeeds
# (warm radio + persistent retry), so this service automates that recovery:
# it watches for "no IPv4 on wlan0" and escalates reconnect → radio bounce →
# firmware reload until a lease appears, then idles and monitors.
#
# Installed by install.sh as a systemd service (wifi-watchdog.service).
set -u

CON="RetroPie-WiFi"     # NetworkManager connection profile name
IFACE="wlan0"
LOG="/var/log/wifi-watchdog.log"

log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
have_ip(){ ip -4 addr show "$IFACE" 2>/dev/null | grep -q 'inet '; }

# keep the log from growing unbounded across reboots
[ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 1000000 ] && : > "$LOG"
log "watchdog started (con=$CON iface=$IFACE)"

# Grace period: let NetworkManager finish initializing and try its own
# autoconnect first, so we don't fight it during early boot (which throws
# spurious 'Secrets were required' / device-mismatch errors). Only after this
# do we start forcing reconnects.
for _ in $(seq 1 20); do systemctl is-active --quiet NetworkManager && break; sleep 1; done
for _ in $(seq 1 25); do have_ip && break; sleep 1; done
have_ip && log "online during grace period (NM connected on its own)"

fails=0
while true; do
    if have_ip; then
        if [ "$fails" -ne 0 ]; then
            log "ONLINE: $(ip -4 -br addr show "$IFACE" | awk '{print $3}')"
            fails=0
        fi
        sleep 20
        continue
    fi

    fails=$((fails + 1))
    log "no IP on $IFACE (consecutive failures: $fails) — recovering"

    # Step 1 — full connection down/up. Resets wpa_supplicant's SSID auth-failure
    # backoff (the SSID-TEMP-DISABLED state), exactly like a manual reconnect.
    timeout 30 nmcli connection up "$CON" ifname "$IFACE" >>"$LOG" 2>&1
    have_ip && { log "recovered via 'nmcli connection up'"; continue; }

    # Step 2 (every 3rd failure) — bounce the radio.
    if [ $((fails % 3)) -eq 0 ]; then
        log "escalate: radio off/on"
        nmcli radio wifi off >>"$LOG" 2>&1; sleep 3
        nmcli radio wifi on  >>"$LOG" 2>&1; sleep 8
        timeout 30 nmcli connection up "$CON" ifname "$IFACE" >>"$LOG" 2>&1
        have_ip && { log "recovered via radio bounce"; continue; }
    fi

    # Step 3 (every 6th failure) — reload the firmware/driver to clear a wedged adapter.
    if [ $((fails % 6)) -eq 0 ]; then
        log "escalate: reload brcmfmac"
        modprobe -r brcmfmac >>"$LOG" 2>&1; sleep 2
        modprobe    brcmfmac >>"$LOG" 2>&1; sleep 10
        timeout 30 nmcli connection up "$CON" ifname "$IFACE" >>"$LOG" 2>&1
        have_ip && { log "recovered via brcmfmac reload"; continue; }
    fi

    sleep 8
done
