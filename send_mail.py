#!/usr/bin/env python3
"""Fallback-Versand per SMTP für LOKALE Läufe (Desktop-Routine auf dem eigenen PC).

In der Cloud-Routine wird NICHT dieses Skript benutzt, sondern der Gmail-Connector (siehe CLAUDE.md).

Aufruf:
    python send_mail.py --meta out/2026-09-27/meta.json --dry-run     # schreibt out/.../newsletter.eml, sendet nichts
    python send_mail.py --meta out/2026-09-27/meta.json               # sendet per SMTP

Zugangsdaten aus .env im Repo-Ordner (nie committen, steht in .gitignore):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=deine@gmail.com
    SMTP_PASS=app-passwort        # Gmail: 2FA an, dann App-Passwort erzeugen
    MAIL_FROM=deine@gmail.com
    MAIL_TO=empfaenger@example.com,zweiter@example.com

Die Chart-Bilder werden als CID-Inline-Anhänge eingebettet (funktioniert in Gmail, Outlook, Apple Mail),
die absoluten Bild-URLs aus newsletter.html werden dafür ersetzt.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "MAIL_FROM", "MAIL_TO"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    html = Path(meta["html_file"]).read_text(encoding="utf-8")
    text = Path(meta["text_file"]).read_text(encoding="utf-8")
    env = load_env(ROOT / ".env")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    missing = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "MAIL_FROM", "MAIL_TO") if not env.get(k)]
    if missing and not args.dry_run:
        print(f"FEHLER: .env unvollständig, fehlt: {', '.join(missing)}", file=sys.stderr)
        return 1
    recipients = [r.strip() for r in env.get("MAIL_TO", "").split(",") if r.strip()]
    bad = [r for r in recipients if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", r)]
    if bad:
        print(f"FEHLER: ungültige Empfänger: {bad}", file=sys.stderr)
        return 1

    msg = EmailMessage()
    msg["Subject"] = meta["subject"]
    msg["From"] = formataddr((cfg.get("sender_name", "AI Radar"), env.get("MAIL_FROM", "noreply@example.com")))
    msg["To"] = ", ".join(recipients) if recipients else "dry-run@example.com"
    msg["Message-ID"] = make_msgid(domain="tinkellect.de")

    # Bild-URLs -> cid: ; Bilder anhängen
    cids: list[tuple[str, Path, str]] = []
    for url, path in zip(meta["image_urls"], meta["chart_files"]):
        p = Path(path)
        if not p.is_file():
            print(f"FEHLER: Chart fehlt: {p}", file=sys.stderr)
            return 1
        cid = make_msgid(domain="tinkellect.de")
        html = html.replace(url, f"cid:{cid[1:-1]}")
        text = text.replace(url, p.name)
        cids.append((cid, p, mimetypes.guess_type(p.name)[0] or "image/png"))
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    for cid, p, ctype in cids:
        maintype, subtype = ctype.split("/", 1)
        msg.get_payload()[1].add_related(p.read_bytes(), maintype=maintype, subtype=subtype, cid=cid,
                                         filename=p.name)

    out_eml = Path(meta["html_file"]).with_name("newsletter.eml")
    out_eml.write_bytes(bytes(msg))
    total = out_eml.stat().st_size
    print(f"EML     {out_eml} ({total // 1024} KB gesamt, HTML {meta['html_bytes'] // 1024} KB)")
    if meta["html_bytes"] > cfg.get("limits", {}).get("html_max_bytes", 92000):
        print("WARNUNG HTML zu groß – Gmail kürzt ab ~102 KB", file=sys.stderr)
    if args.dry_run:
        print("DRY-RUN – nichts gesendet. Empfänger wären:", recipients or "(MAIL_TO fehlt)")
        return 0

    port = int(env.get("SMTP_PORT", "587"))
    with smtplib.SMTP(env["SMTP_HOST"], port, timeout=60) as s:
        s.ehlo()
        if port != 465:
            s.starttls()
        s.login(env["SMTP_USER"], env["SMTP_PASS"])
        s.send_message(msg)
    print(f"GESENDET an {', '.join(recipients)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
