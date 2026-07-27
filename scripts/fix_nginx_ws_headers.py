#!/usr/bin/env python3
"""One-shot, precise fix for the missing WebSocket headers in the ecoe.drnotus.cl
nginx block, inside the shared /etc/nginx/sites-available/drnotus-multisite file.

Usage: sudo python3 fix_nginx_ws_headers.py

What it does, in order:
  1. Backs up the file to drnotus-multisite.bak-YYYYMMDD-HHMMSS
  2. Inserts the two missing proxy_set_header lines right after the unique
     anchor line "proxy_pass http://127.0.0.1:8000/api/;" (only ecoe's block
     proxies to that address, so nothing else in the file is touched)
  3. Runs "nginx -t" to validate syntax
  4. Only if valid: runs "systemctl reload nginx"
  5. If anything fails, restores the backup automatically and exits non-zero
     without touching nginx further.
"""
import datetime
import shutil
import subprocess
import sys

CONFIG_PATH = "/etc/nginx/sites-available/drnotus-multisite"
ANCHOR = "proxy_pass http://127.0.0.1:8000/api/;"
NEW_LINES = [
    "proxy_set_header Upgrade $http_upgrade;",
    'proxy_set_header Connection "upgrade";',
]


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        original_lines = f.readlines()

    anchor_indexes = [i for i, line in enumerate(original_lines) if ANCHOR in line]
    if len(anchor_indexes) != 1:
        fail(
            f"Expected exactly 1 occurrence of the anchor line, found {len(anchor_indexes)}. "
            "Aborting without changing anything — the file may have changed since this "
            "script was written."
        )
    anchor_index = anchor_indexes[0]

    # Find the "X-Forwarded-For" line within the next few lines of the same block.
    insert_after = None
    for offset in range(1, 8):
        idx = anchor_index + offset
        if idx >= len(original_lines):
            break
        if "X-Forwarded-For" in original_lines[idx]:
            insert_after = idx
            break
    if insert_after is None:
        fail("Could not find the X-Forwarded-For line near the anchor. Aborting.")

    indent = original_lines[insert_after][: len(original_lines[insert_after]) - len(original_lines[insert_after].lstrip())]
    already_present = any(
        "Upgrade $http_upgrade" in original_lines[i]
        for i in range(anchor_index, min(anchor_index + 12, len(original_lines)))
    )
    if already_present:
        print("Nothing to do: the Upgrade header is already present near this block.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{CONFIG_PATH}.bak-{timestamp}"
    shutil.copy2(CONFIG_PATH, backup_path)
    print(f"Backup written to {backup_path}")

    new_lines = (
        original_lines[: insert_after + 1]
        + [f"{indent}{line}\n" for line in NEW_LINES]
        + original_lines[insert_after + 1 :]
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"Inserted {len(NEW_LINES)} lines after line {insert_after + 1}.")

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    print(test.stdout)
    print(test.stderr)
    if test.returncode != 0:
        shutil.copy2(backup_path, CONFIG_PATH)
        fail("nginx -t failed; restored the original file. Nothing was reloaded.")

    reload = subprocess.run(["systemctl", "reload", "nginx"], capture_output=True, text=True)
    if reload.returncode != 0:
        print(reload.stdout)
        print(reload.stderr)
        shutil.copy2(backup_path, CONFIG_PATH)
        subprocess.run(["nginx", "-t"], capture_output=True, text=True)
        fail("systemctl reload failed; restored the original file (re-test the config manually).")

    print("Done: nginx reloaded successfully with the WebSocket headers fix.")


if __name__ == "__main__":
    if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
        fail("Must run as root: sudo python3 fix_nginx_ws_headers.py")
    main()
