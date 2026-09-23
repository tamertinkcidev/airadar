#!/usr/bin/env python3
"""Prüft nach dem git push, ob die Chart-Bilder öffentlich erreichbar sind (Gmail lädt sie beim Öffnen).

Aufruf:
    python verify_urls.py --meta out/2026-09-27/meta.json

Exit-Codes: 0 alle erreichbar, 1 mindestens eine URL nicht erreichbar, 4 Netzwerk gesperrt (weiche Warnung).
Bei Exit 4 nicht abbrechen: Die Cloud-Umgebung erlaubt evtl. keinen Zugriff auf raw.githubusercontent.com,
die Bilder sind trotzdem öffentlich, sobald der Push auf main durch ist.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True)
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()
    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)
    urls = meta.get("image_urls", [])
    if not urls:
        print("Keine Bild-URLs in meta.json")
        return 1
    failed = 0
    blocked = 0
    for url in urls:
        ok = False
        last = ""
        for attempt in range(args.retries):
            try:
                req = urllib.request.Request(url, method="GET", headers={"User-Agent": "tinkellect-radar/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    ctype = r.headers.get("Content-Type", "")
                    size = len(r.read())
                    ok = r.status == 200 and "image" in ctype and size > 1000
                    last = f"{r.status} {ctype} {size} B"
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (403, 407) and "host_not_allowed" in str(e.headers.get("x-deny-reason", "")):
                    blocked += 1
                    break
            except Exception as e:  # noqa: BLE001
                last = str(e)
            if ok:
                break
            time.sleep(4 * (attempt + 1))  # raw.githubusercontent.com braucht nach dem Push manchmal Sekunden
        print(f"{'OK     ' if ok else 'FEHLER '} {url}  [{last}]")
        if not ok:
            failed += 1
    if blocked:
        print("NETZWERK GESPERRT – Prüfung nicht möglich, Bilder gelten als ok, wenn der Push erfolgreich war.")
        return 4
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
