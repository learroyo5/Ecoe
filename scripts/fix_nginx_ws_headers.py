#!/usr/bin/env python3
"""Ensure the WebSocket upgrade headers are present in every nginx block that
proxies ECOE's `/api/` to the backend (127.0.0.1:8000).

Without `proxy_set_header Upgrade $http_upgrade;` + `proxy_set_header Connection
"upgrade";` in the `location /api/` block, nginx forces `Connection: close` and
the `/api/ws/live/{id}` handshake (OPT-20 F1: live timer for kiosk / evaluator /
student screens) never reaches the backend.

Covers BOTH real config files on the current server:
  - /etc/nginx/sites-available/drnotus-multisite   (ecoe.drnotus.cl — staging/dev)
  - /etc/nginx/sites-available/ecoe-domains         (app.ecoe.cl   — production)
A file that does not exist is skipped (e.g. a server without the ecoe.cl domains).

Usage:
  sudo python3 fix_nginx_ws_headers.py            # patch what's missing, then nginx -t + reload
  sudo python3 fix_nginx_ws_headers.py --check    # report only, change nothing, exit 1 if a patch is needed
  sudo python3 fix_nginx_ws_headers.py --dry-run  # show the diff, change nothing

Behaviour:
  1. For every `location /api/` block proxying to 127.0.0.1:8000 that lacks the
     Upgrade header, insert the two lines right after the `proxy_pass` line
     (matching indent).
  2. Back up each modified file to <path>.bak-YYYYMMDD-HHMMSS
  3. `nginx -t`; only if valid, `systemctl reload nginx`.
  4. On any failure, restore every backup and exit non-zero without reloading.
  5. Idempotent: nothing missing -> "nothing to do", exit 0, no reload.
"""
from __future__ import annotations

import datetime
import re
import shutil
import subprocess
import sys

TARGETS = [
    "/etc/nginx/sites-available/drnotus-multisite",
    "/etc/nginx/sites-available/ecoe-domains",
]
BACKEND_HINT = "127.0.0.1:8000"
UPGRADE_MARKER = "Upgrade $http_upgrade"
NEW_LINES = [
    "proxy_set_header Upgrade $http_upgrade;",
    'proxy_set_header Connection "upgrade";',
]


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _code(line: str) -> str:
    """The line with any `#` comment stripped (so braces in comments don't count)."""
    return line.split("#", 1)[0]


def block_end(lines: list[str], anchor: int) -> int:
    """Index of the `}` that closes the `location` block containing line `anchor`.

    `anchor` is a line *inside* the block (its `proxy_pass`), so we walk backwards
    to the opening `{` first, then forward tracking brace depth.
    """
    open_idx = anchor
    for i in range(anchor, -1, -1):
        if "{" in _code(lines[i]):
            open_idx = i
            break
    depth = 0
    for i in range(open_idx, len(lines)):
        depth += _code(lines[i]).count("{")
        depth -= _code(lines[i]).count("}")
        if depth <= 0 and i >= open_idx:
            return i
    return len(lines) - 1


def patch_file(path: str) -> tuple[list[str] | None, list[str]]:
    """Return (new_lines_or_None, notes). None means no change needed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None, [f"{path}: no existe — se omite"]

    notes: list[str] = []
    # proxy_pass lines that point at the ECOE backend
    anchors = [
        i for i, ln in enumerate(lines)
        if "proxy_pass" in ln and BACKEND_HINT in ln
    ]
    if not anchors:
        return None, [f"{path}: sin bloque que apunte a {BACKEND_HINT} — se omite"]

    inserts: list[tuple[int, str]] = []  # (line_index_to_insert_after, indent)
    for a in anchors:
        end = block_end(lines, a)
        if any(UPGRADE_MARKER in lines[j] for j in range(a, end + 1)):
            notes.append(f"{path}:{a+1}: ya tiene los headers de Upgrade — ok")
            continue
        # Insert after the X-Forwarded-For line if it's in this block, else after proxy_pass.
        after = a
        for j in range(a + 1, end + 1):
            if "X-Forwarded-For" in lines[j]:
                after = j
                break
        indent = re.match(r"\s*", lines[after]).group(0)
        inserts.append((after, indent))
        notes.append(f"{path}:{a+1}: FALTAN los headers de Upgrade — se insertarán tras la línea {after+1}")

    if not inserts:
        return None, notes

    # Apply inserts from the bottom up so earlier indices stay valid.
    new_lines = list(lines)
    for after, indent in sorted(inserts, key=lambda t: t[0], reverse=True):
        block = [f"{indent}# WebSocket del panel en vivo (OPT-20 F1): sin esto nginx cierra el upgrade\n"]
        block += [f"{indent}{ln}\n" for ln in NEW_LINES]
        new_lines[after + 1 : after + 1] = block
    return new_lines, notes


def main() -> None:
    mode = "apply"
    if "--check" in sys.argv:
        mode = "check"
    elif "--dry-run" in sys.argv:
        mode = "dry-run"

    if mode == "apply" and subprocess.run(
        ["id", "-u"], capture_output=True, text=True
    ).stdout.strip() != "0":
        fail("Debe correr como root: sudo python3 fix_nginx_ws_headers.py")

    pending: list[tuple[str, list[str]]] = []
    all_notes: list[str] = []
    for path in TARGETS:
        new_lines, notes = patch_file(path)
        all_notes += notes
        if new_lines is not None:
            pending.append((path, new_lines))

    for n in all_notes:
        print(n)

    if not pending:
        print("\nNada que hacer: todos los bloques /api/ ya reenvían el upgrade de WebSocket.")
        sys.exit(0)

    if mode == "check":
        print(f"\n{len(pending)} archivo(s) necesitan el parche. Correr sin --check para aplicarlo.")
        sys.exit(1)

    if mode == "dry-run":
        for path, new_lines in pending:
            print(f"\n----- {path} (nuevo contenido, extracto) -----")
            with open(path, encoding="utf-8") as f:
                old = f.readlines()
            import difflib
            sys.stdout.writelines(difflib.unified_diff(old, new_lines, path, path + " (patched)", n=2))
        print("\n--dry-run: no se escribió nada.")
        sys.exit(0)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backups: list[tuple[str, str]] = []
    for path, new_lines in pending:
        backup = f"{path}.bak-{ts}"
        shutil.copy2(path, backup)
        backups.append((path, backup))
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Parcheado {path} (respaldo: {backup})")

    def restore_all() -> None:
        for path, backup in backups:
            shutil.copy2(backup, path)
        subprocess.run(["nginx", "-t"], capture_output=True, text=True)

    test = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    print(test.stdout, test.stderr)
    if test.returncode != 0:
        restore_all()
        fail("`nginx -t` falló; se restauraron los archivos originales. Nada se recargó.")

    reload = subprocess.run(["systemctl", "reload", "nginx"], capture_output=True, text=True)
    if reload.returncode != 0:
        print(reload.stdout, reload.stderr)
        restore_all()
        fail("`systemctl reload nginx` falló; se restauraron los archivos originales.")

    print("\nListo: nginx recargado con los headers de WebSocket en todos los bloques /api/.")


if __name__ == "__main__":
    main()
