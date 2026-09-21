#!/usr/bin/env python3
# Save as: crack7z.py
# Location: ~/Desktop/crack7z.py
# Run: python3 ~/Desktop/crack7z.py

import subprocess
import itertools
import string
import os
import sys
import time
import threading

# ── CONFIG ────────────────────────────────────────────────────────────────────
ARCHIVE_PATH = os.path.expanduser("~/Desktop/Access_To_Security_code.7z")
OUTPUT_DIR   = os.path.expanduser("~/Desktop/cracked_output")
WORDLIST     = "/usr/share/wordlists/rockyou.txt"   # Kali mein built-in hai
HASH_FILE    = os.path.expanduser("~/Desktop/hash.txt")
MAX_BF_LEN   = 6
CHARSET      = string.ascii_lowercase + string.digits + "!@#$_"
FOUND        = threading.Event()
RESULT       = [None]
COUNT        = [0]
START        = time.time()
LOCK         = threading.Lock()

# ── STEP 1 — EXTRACT HASH FOR HASHCAT ────────────────────────────────────────
def extract_hash():
    print("\n[*] Extracting 7z hash for hashcat...")
    try:
        result = subprocess.run(
            ["7z2hashcat.pl", ARCHIVE_PATH],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            with open(HASH_FILE, "w") as f:
                f.write(result.stdout.strip())
            print(f"[+] Hash saved: {HASH_FILE}")
            return True
    except FileNotFoundError:
        pass

    # fallback — use python hash extractor
    try:
        result = subprocess.run(
            ["python3", "-c",
             f"""
import struct, sys
with open('{ARCHIVE_PATH}', 'rb') as f:
    data = f.read(32)
print(data.hex())
"""],
            capture_output=True, text=True
        )
        print(f"[*] Raw header: {result.stdout.strip()}")
    except Exception as e:
        print(f"[-] Hash extract failed: {e}")
    return False

# ── STEP 2 — HASHCAT ATTACK (GPU accelerated) ────────────────────────────────
def hashcat_attack():
    print("\n[*] Trying hashcat GPU attack...")
    if not os.path.exists(HASH_FILE):
        print("[-] No hash file, skipping hashcat")
        return False

    # mode 11600 = 7-Zip
    cmd = [
        "hashcat",
        "-m", "11600",
        "-a", "0",
        "--status",
        "--status-timer=5",
        HASH_FILE,
        WORDLIST
    ]
    print(f"[CMD] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode == 0:
            print("[+] Hashcat finished — check .hashcat/hashcat.potfile")
            # read potfile
            potfile = os.path.expanduser("~/.local/share/hashcat/hashcat.potfile")
            if os.path.exists(potfile):
                with open(potfile) as f:
                    lines = f.readlines()
                if lines:
                    last = lines[-1].strip()
                    pwd = last.split(":")[-1]
                    print(f"[✓] PASSWORD: {pwd}")
                    RESULT[0] = pwd
                    FOUND.set()
                    return True
    except Exception as e:
        print(f"[-] Hashcat error: {e}")
    return False

# ── STEP 3 — 7Z NATIVE BRUTE (no py7zr needed) ───────────────────────────────
def try_7z_password(password: str) -> bool:
    if FOUND.is_set():
        return False
    try:
        result = subprocess.run(
            ["7z", "t", f"-p{password}", ARCHIVE_PATH],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def extract_with_password(password: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    subprocess.run([
        "7z", "e",
        f"-p{password}",
        f"-o{OUTPUT_DIR}",
        "-y",
        ARCHIVE_PATH
    ])

# ── PROGRESS THREAD ───────────────────────────────────────────────────────────
def progress():
    while not FOUND.is_set():
        elapsed = time.time() - START
        with LOCK:
            c = COUNT[0]
        rate = c / elapsed if elapsed > 0 else 0
        sys.stdout.write(
            f"\r[*] Tried: {c:,} | Rate: {rate:,.0f}/s | Time: {elapsed:.0f}s   "
        )
        sys.stdout.flush()
        time.sleep(1)

# ── MUTATION GEN ──────────────────────────────────────────────────────────────
MUTATIONS = [
    lambda w: w,
    lambda w: w.capitalize(),
    lambda w: w.upper(),
    lambda w: w + "1", lambda w: w + "123",
    lambda w: w + "!", lambda w: w + "@123",
    lambda w: w + "2024", lambda w: w + "2025",
    lambda w: w[::-1],
    lambda w: w.capitalize() + "123",
    lambda w: w.replace("a","@").replace("e","3").replace("i","1").replace("o","0"),
]

def run_wordlist_attack():
    print(f"\n[+] Wordlist attack: {WORDLIST}")

    # gunzip rockyou if needed
    gz = WORDLIST + ".gz"
    if not os.path.exists(WORDLIST) and os.path.exists(gz):
        print("[*] Decompressing rockyou.txt.gz...")
        subprocess.run(["gunzip", gz])

    if not os.path.exists(WORDLIST):
        print("[-] rockyou.txt not found")
        return

    with open(WORDLIST, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if FOUND.is_set():
                break
            word = line.strip()
            for fn in MUTATIONS:
                if FOUND.is_set():
                    break
                pwd = fn(word)
                with LOCK:
                    COUNT[0] += 1
                if try_7z_password(pwd):
                    FOUND.set()
                    RESULT[0] = pwd
                    return

def run_brute_attack():
    print(f"\n[+] Brute force (max_len={MAX_BF_LEN})")
    for length in range(1, MAX_BF_LEN + 1):
        for combo in itertools.product(CHARSET, repeat=length):
            if FOUND.is_set():
                return
            pwd = "".join(combo)
            with LOCK:
                COUNT[0] += 1
            if try_7z_password(pwd):
                FOUND.set()
                RESULT[0] = pwd
                return

# ── CHECK NO PASSWORD ─────────────────────────────────────────────────────────
def check_no_pass():
    print("\n[*] Trying without password first...")
    result = subprocess.run(
        ["7z", "t", ARCHIVE_PATH],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("[+] No password needed!")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        subprocess.run(["7z", "e", f"-o{OUTPUT_DIR}", "-y", ARCHIVE_PATH])
        print(f"[✓] Extracted to: {OUTPUT_DIR}")
        return True
    return False

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 52)
    print("  7Z CRACKER — Kali Linux Native Edition")
    print(f"  File: {ARCHIVE_PATH}")
    print("=" * 52)

    if not os.path.exists(ARCHIVE_PATH):
        print(f"\n[!] File not found: {ARCHIVE_PATH}")
        print("    → File ko ~/Desktop/ mein rakh boss man")
        sys.exit(1)

    # Phase 0
    if check_no_pass():
        return

    # Phase 1 — hashcat
    extract_hash()
    hashcat_attack()

    if not FOUND.is_set():
        # Phase 2 — wordlist + mutations
        t = threading.Thread(target=progress, daemon=True)
        t.start()
        run_wordlist_attack()

    if not FOUND.is_set():
        # Phase 3 — brute
        run_brute_attack()

    FOUND.set()
    print()

    if RESULT[0]:
        print(f"\n[✓] PASSWORD FOUND: {RESULT[0]}")
        extract_with_password(RESULT[0])
        print(f"[✓] Extracted to  : {OUTPUT_DIR}")
        print(f"[✓] Total attempts: {COUNT[0]:,}")
        print(f"[✓] Time taken    : {time.time()-START:.1f}s")
    else:
        print(f"\n[✗] Not cracked. Tried: {COUNT[0]:,}")
        print("    → MAX_BF_LEN badhao ya better wordlist use karo")

if __name__ == "__main__":
    main()
