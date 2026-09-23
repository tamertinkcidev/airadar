#!/usr/bin/env python3
"""Baut den Newsletter aus content.json + brand.json + config.json + gerenderten Charts.

Aufruf:
    python build_newsletter.py --content out/2026-09-27/content.json \
        --charts charts/2026-09-27 --out out/2026-09-27

Erzeugt im --out-Ordner:
    newsletter.html   E-Mail-Version (tabellenbasiert, Inline-CSS, absolute Bild-URLs)
    newsletter.txt    Plain-Text-Alternative
    preview.html      Browser-Vorschau mit lokalen Bildpfaden
    meta.json         Betreff, Größen, Bild-URLs, Warnungen/Fehler

Bild-URLs: <config.assets_base_url>/<charts-Ordner relativ zum Repo>/<datei>.png
Der charts-Ordner muss im Repo liegen (public), damit Gmail die Bilder laden kann.

Exit-Codes: 0 ok (ggf. mit Warnungen), 1 harte Fehler (nichts gebaut oder unvollständig).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL_RE = re.compile(r"^https?://[^\s<>\"']+$")
FILE_RE = re.compile(r"^[A-Za-z0-9_-]+\.png$")

REQUIRED_TOP = ["issue", "tldr", "new_models", "benchmarks", "changes",
                "use_cases", "tinkellect", "n8n_updates", "sources"]
USE_CASES_EXPECTED = [
    "Klassifikation/Routing", "Dokument-/E-Mail-Extraktion", "Tool-Calling-Agent in n8n",
    "Recherche/Web", "Coding", "Long Context", "Günstig & schnell",
]


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def de_date(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        return f"{int(d):02d}.{int(m):02d}.{y}"
    except Exception:  # noqa: BLE001
        return iso


# ----------------------------------------------------------------------------- validation
def validate(c: dict, charts_dir: Path, cfg: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for k in REQUIRED_TOP:
        if k not in c:
            errors.append(f"content.json: Pflichtblock '{k}' fehlt")
    if errors:
        return errors, warnings

    issue = c["issue"]
    for k in ("date", "kw", "hook"):
        if not issue.get(k) and issue.get(k) != 0:
            errors.append(f"issue.{k} fehlt")
    try:
        date.fromisoformat(issue.get("date", ""))
    except ValueError:
        errors.append("issue.date muss YYYY-MM-DD sein")

    if not isinstance(c["tldr"], list) or not (2 <= len(c["tldr"]) <= 5):
        errors.append("tldr: 2–5 Sätze erwartet")

    lim = cfg.get("limits", {})
    bm = c["benchmarks"]
    if not isinstance(bm, list) or len(bm) < lim.get("min_charts", 3):
        errors.append(f"benchmarks: mindestens {lim.get('min_charts', 3)} Charts erwartet")
    if isinstance(bm, list) and len(bm) > lim.get("max_charts", 5):
        warnings.append(f"benchmarks: mehr als {lim.get('max_charts', 5)} Charts – Mail wird lang")
    for i, b in enumerate(bm if isinstance(bm, list) else []):
        f = str(b.get("chart", ""))
        if not FILE_RE.match(f):
            errors.append(f"benchmarks[{i}].chart ungültig: {f!r}")
        elif not (charts_dir / f).is_file():
            errors.append(f"benchmarks[{i}]: Chart-Datei fehlt: {charts_dir / f}")
        for k in ("title", "insight"):
            if not b.get(k):
                errors.append(f"benchmarks[{i}].{k} fehlt")
        if not URL_RE.match(str(b.get("source", ""))):
            errors.append(f"benchmarks[{i}].source ist keine URL")

    for i, m in enumerate(c["new_models"]):
        for k in ("name", "vendor", "note"):
            if not m.get(k):
                errors.append(f"new_models[{i}].{k} fehlt")
        if not URL_RE.match(str(m.get("source", ""))):
            errors.append(f"new_models[{i}].source ist keine URL")
    if not c["new_models"]:
        warnings.append("new_models ist leer – ok, wenn es diese Woche wirklich nichts gab")

    uc_names = [u.get("use_case") for u in c["use_cases"]]
    for name in USE_CASES_EXPECTED:
        if name not in uc_names:
            warnings.append(f"use_cases: '{name}' fehlt")
    for i, u in enumerate(c["use_cases"]):
        for k in ("use_case", "pick", "why"):
            if not u.get(k):
                errors.append(f"use_cases[{i}].{k} fehlt")

    t = c["tinkellect"]
    if not t.get("items") or len(t["items"]) < 2:
        errors.append("tinkellect.items: mindestens 2 konkrete Konsequenzen")

    for i, ch in enumerate(c["changes"]):
        if not ch.get("title") or not ch.get("text"):
            errors.append(f"changes[{i}]: title/text fehlt")
        if ch.get("source") and not URL_RE.match(str(ch["source"])):
            errors.append(f"changes[{i}].source ist keine URL")

    srcs = c["sources"]
    if len(srcs) < lim.get("min_sources", 6):
        errors.append(f"sources: mindestens {lim.get('min_sources', 6)} Quellen erwartet")
    for i, s in enumerate(srcs):
        if not s.get("title") or not URL_RE.match(str(s.get("url", ""))):
            errors.append(f"sources[{i}]: title/url ungültig")

    blob = json.dumps(c, ensure_ascii=False).lower()
    for bad in ("lorem ipsum", "tbd", "todo", "platzhalter", "xx,x"):
        if bad in blob:
            warnings.append(f"Platzhalter-Text gefunden: {bad!r}")
    return errors, warnings


# ----------------------------------------------------------------------------- html parts
def render_html(c: dict, brand: dict, cfg: dict, img_url: dict[str, str], subject: str) -> str:
    col = brand["colors"]
    font = brand["fonts"]["email_stack"]
    issue = c["issue"]
    title = brand.get("newsletter_title", "AI Radar")
    body_font = f"font-family:{font};"
    p = f"margin:0 0 10px 0;{body_font}font-size:15px;line-height:1.55;color:{col['text']};"
    muted = f"{body_font}font-size:12px;line-height:1.5;color:{col['text_muted']};"
    h2 = (f"margin:0 0 12px 0;{body_font}font-size:13px;letter-spacing:1.4px;"
          f"text-transform:uppercase;font-weight:700;color:{col['accent']};")
    h3 = f"margin:0 0 4px 0;{body_font}font-size:16px;font-weight:700;color:{col['text']};"
    link = f"color:{col['accent']};text-decoration:underline;"
    section_open = (f'<tr><td style="padding:22px 28px 6px 28px;border-top:1px solid {col["border"]};">')
    section_close = "</td></tr>"

    def a(url: str, text: str) -> str:
        return f'<a href="{esc(url)}" style="{link}">{esc(text)}</a>'

    parts: list[str] = []
    parts.append(f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting"><title>{esc(subject)}</title>
<style>img{{border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic}} @media (max-width:640px){{.wrap{{width:100%!important}} .pad{{padding-left:16px!important;padding-right:16px!important}}}}</style>
</head><body style="margin:0;padding:0;background:{col['surface']};">
<div style="display:none;max-height:0;overflow:hidden;{body_font}">{esc(c['tldr'][0])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{col['surface']};"><tr><td align="center" style="padding:20px 8px;">
<table role="presentation" class="wrap" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:640px;background:#ffffff;border-radius:12px;overflow:hidden;">""")

    # Header
    late_badge = ""
    if issue.get("late"):
        late_badge = (f'<span style="display:inline-block;margin-left:8px;padding:2px 8px;border-radius:10px;'
                      f'background:#F59E0B;color:#111;font-size:11px;font-weight:700;">verspätete Ausgabe</span>')
    logo = ""
    if brand.get("logo_url"):
        logo = (f'<img src="{esc(brand["logo_url"])}" alt="{esc(brand["brand_name"])}" width="120" '
                f'style="display:block;width:120px;height:auto;margin-bottom:14px;">')
    parts.append(f"""<tr><td class="pad" style="background:{col['header_bg']};padding:28px 28px 24px 28px;">
{logo}<div style="{body_font}font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{col['accent']};font-weight:700;">{esc(brand['brand_name'])} · {esc(brand.get('tagline', ''))}</div>
<div style="{body_font}font-size:26px;font-weight:800;color:{col['header_text']};margin-top:8px;line-height:1.2;">{esc(title)}</div>
<div style="{body_font}font-size:13px;color:#B6BDCB;margin-top:8px;">KW {esc(issue['kw'])} · {esc(de_date(issue['date']))}{late_badge}</div>
</td></tr>""")

    # TL;DR
    tl = "".join(f'<li style="margin:0 0 8px 0;">{esc(s)}</li>' for s in c["tldr"])
    parts.append(f"""{section_open.replace('border-top:1px solid ' + col['border'] + ';', '')}<div style="{h2}">TL;DR</div>
<ul style="margin:0 0 6px 0;padding:0 0 0 20px;{body_font}font-size:15px;line-height:1.5;color:{col['text']};">{tl}</ul>{section_close}""")

    # Neue Modelle
    parts.append(f'{section_open}<div style="{h2}">Neue Modelle &amp; Updates</div>')
    if c["new_models"]:
        for m in c["new_models"]:
            facts = []
            for label, key in (("Release", "released"), ("Kontext", "context"), ("Preis in/out je 1M", "price"),
                               ("Tool-Calling", "tools"), ("n8n", "n8n"), ("EU-Hosting", "eu")):
                if m.get(key):
                    val = de_date(m[key]) if key == "released" else m[key]
                    facts.append(f"<b>{esc(label)}:</b> {esc(val)}")
            parts.append(f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px 0;"><tr>
<td style="padding:12px 14px;background:{col['surface']};border-left:3px solid {col['accent']};border-radius:6px;">
<div style="{h3}">{esc(m['name'])} <span style="font-weight:400;color:{col['text_muted']};">· {esc(m['vendor'])}</span></div>
<div style="{muted}margin:2px 0 6px 0;">{' &nbsp;·&nbsp; '.join(facts)}</div>
<div style="{p}margin:0;">{esc(m['note'])} {a(m['source'], 'Quelle')}</div>
</td></tr></table>""")
    else:
        parts.append(f'<p style="{p}">Diese Woche keine neuen Modelle im Roster.</p>')
    parts.append(section_close)

    # Benchmarks
    parts.append(f'{section_open}<div style="{h2}">Benchmark-Lage</div>')
    for b in c["benchmarks"]:
        url = img_url[b["chart"]]
        src_label = b.get("source_label") or "Quelle"
        parts.append(f"""<div style="{h3}margin-top:6px;">{esc(b['title'])}</div>
<img src="{esc(url)}" alt="{esc(b['title'])}" width="584" style="display:block;width:100%;max-width:584px;height:auto;margin:8px 0 8px 0;border:1px solid {col['border']};border-radius:6px;">
<p style="{p}">{esc(b['insight'])} {a(b['source'], src_label)}</p>""")
    parts.append(section_close)

    # Was sich geändert hat
    if c["changes"]:
        parts.append(f'{section_open}<div style="{h2}">Was sich geändert hat</div>')
        for ch in c["changes"]:
            src = f" {a(ch['source'], 'Quelle')}" if ch.get("source") else ""
            parts.append(f'<div style="{h3}">{esc(ch["title"])}</div><p style="{p}">{esc(ch["text"])}{src}</p>')
        parts.append(section_close)

    # Use-Case-Matrix
    parts.append(f'{section_open}<div style="{h2}">Welches Modell wofür</div>'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">')
    for i, u in enumerate(c["use_cases"]):
        bg = "#ffffff" if i % 2 == 0 else col["surface"]
        alt = f'<div style="{muted}">Alternative: {esc(u["alt"])}</div>' if u.get("alt") else ""
        parts.append(f"""<tr style="background:{bg};">
<td valign="top" style="padding:10px 10px 10px 8px;width:34%;border-bottom:1px solid {col['border']};{body_font}font-size:14px;font-weight:700;color:{col['text']};">{esc(u['use_case'])}</td>
<td valign="top" style="padding:10px 8px;border-bottom:1px solid {col['border']};">
<div style="{body_font}font-size:14px;font-weight:700;color:{col['accent']};">{esc(u['pick'])}</div>{alt}
<div style="{body_font}font-size:13px;line-height:1.45;color:{col['text']};margin-top:3px;">{esc(u['why'])}</div></td></tr>""")
    parts.append("</table>" + section_close)

    # Tinkellect Callout
    t = c["tinkellect"]
    items = "".join(f'<li style="margin:0 0 8px 0;"><b>{esc(it["title"])}</b> – {esc(it["text"])}</li>' for it in t["items"])
    intro = f'<p style="{p}">{esc(t["intro"])}</p>' if t.get("intro") else ""
    parts.append(f"""<tr><td class="pad" style="padding:22px 28px 10px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:16px 18px;background:{col['accent_soft']};border-radius:10px;">
<div style="{h2}color:{col['header_bg']};">Für Tinkellect-Workflows</div>{intro}
<ul style="margin:0;padding:0 0 0 20px;{body_font}font-size:15px;line-height:1.5;color:{col['text']};">{items}</ul>
</td></tr></table></td></tr>""")

    # n8n Updates
    if c["n8n_updates"]:
        parts.append(f'{section_open}<div style="{h2}">n8n-Updates</div>')
        for n in c["n8n_updates"]:
            src = f" {a(n['source'], 'Release Notes')}" if n.get("source") else ""
            parts.append(f'<div style="{h3}">{esc(n["title"])}</div><p style="{p}">{esc(n["text"])}{src}</p>')
        parts.append(section_close)

    # Quellen
    srcs = "".join(f'<li style="margin:0 0 4px 0;">{a(s["url"], s["title"])}</li>' for s in c["sources"])
    parts.append(f'{section_open}<div style="{h2}">Quellen</div>'
                 f'<ol style="margin:0 0 10px 0;padding:0 0 0 20px;{muted}font-size:12px;">{srcs}</ol>{section_close}')

    # Footer
    closing = f'<p style="{p}font-size:14px;">{esc(c["closing"])}</p>' if c.get("closing") else ""
    web = ""
    if cfg.get("web_base_url"):
        web = f'<div style="{muted}margin-top:6px;">{a(cfg["web_base_url"].rstrip("/") + "/archive/" + issue["date"] + "/newsletter.html", "Web-Version")}</div>'
    footer_lines = "<br>".join(esc(x) for x in cfg.get("footer_lines", []))
    parts.append(f"""<tr><td class="pad" style="padding:18px 28px 26px 28px;background:{col['header_bg']};">
{closing.replace(col['text'], '#D5DAE6') if closing else ''}
<div style="{body_font}font-size:12px;line-height:1.6;color:#8B93A7;">{footer_lines}</div>{web}
</td></tr>
</table></td></tr></table></body></html>""")
    return "\n".join(parts)


def render_text(c: dict, brand: dict, cfg: dict, img_url: dict[str, str], subject: str) -> str:
    issue = c["issue"]
    L: list[str] = [subject, "=" * len(subject), f"KW {issue['kw']} · {de_date(issue['date'])}", ""]
    L += ["TL;DR"] + [f"- {s}" for s in c["tldr"]] + [""]
    L.append("NEUE MODELLE & UPDATES")
    for m in c["new_models"] or []:
        L.append(f"- {m['name']} ({m['vendor']}): {m['note']} [{m['source']}]")
    if not c["new_models"]:
        L.append("- keine")
    L += ["", "BENCHMARK-LAGE"]
    for b in c["benchmarks"]:
        L.append(f"- {b['title']}: {b['insight']} Chart: {img_url[b['chart']]} Quelle: {b['source']}")
    if c["changes"]:
        L += ["", "WAS SICH GEÄNDERT HAT"]
        for ch in c["changes"]:
            L.append(f"- {ch['title']}: {ch['text']}" + (f" [{ch['source']}]" if ch.get("source") else ""))
    L += ["", "WELCHES MODELL WOFÜR"]
    for u in c["use_cases"]:
        alt = f" (Alternative: {u['alt']})" if u.get("alt") else ""
        L.append(f"- {u['use_case']}: {u['pick']}{alt} – {u['why']}")
    L += ["", "FÜR TINKELLECT-WORKFLOWS"]
    if c["tinkellect"].get("intro"):
        L.append(c["tinkellect"]["intro"])
    for it in c["tinkellect"]["items"]:
        L.append(f"- {it['title']}: {it['text']}")
    if c["n8n_updates"]:
        L += ["", "N8N-UPDATES"]
        for n in c["n8n_updates"]:
            L.append(f"- {n['title']}: {n['text']}" + (f" [{n['source']}]" if n.get("source") else ""))
    L += ["", "QUELLEN"] + [f"{i + 1}. {s['title']} – {s['url']}" for i, s in enumerate(c["sources"])]
    L += ["", *cfg.get("footer_lines", [])]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Newsletter bauen")
    ap.add_argument("--content", required=True)
    ap.add_argument("--charts", required=True, help="Ordner mit den PNGs, im Repo (z. B. charts/2026-09-27)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--assets-base-url", default=None, help="überschreibt config.assets_base_url")
    args = ap.parse_args()

    brand = load_json(ROOT / "brand.json")
    cfg = load_json(ROOT / "config.json")
    content = load_json(Path(args.content))
    charts_dir = Path(args.charts).resolve()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    errors, warnings = validate(content, charts_dir, cfg)
    base = (args.assets_base_url or cfg.get("assets_base_url", "")).rstrip("/")
    if not URL_RE.match(base + "/x"):
        errors.append("config.assets_base_url fehlt oder ist keine URL")
    try:
        rel = charts_dir.relative_to(ROOT).as_posix()
    except ValueError:
        rel = ""
        errors.append(f"Charts-Ordner liegt nicht im Repo: {charts_dir} (Gmail kann die Bilder sonst nicht laden)")
    if errors:
        for e in errors:
            print(f"FEHLER  {e}", file=sys.stderr)
        for w in warnings:
            print(f"WARNUNG {w}", file=sys.stderr)
        return 1

    img_url = {b["chart"]: f"{base}/{rel}/{b['chart']}" for b in content["benchmarks"]}
    issue = content["issue"]
    subject = f"{brand.get('newsletter_title', 'AI Radar')} – KW{issue['kw']}: {issue['hook']}"
    if issue.get("late"):
        subject += " (verspätet)"

    html_out = render_html(content, brand, cfg, img_url, subject)
    text_out = render_text(content, brand, cfg, img_url, subject)
    (out_dir / "newsletter.html").write_text(html_out, encoding="utf-8")
    (out_dir / "newsletter.txt").write_text(text_out, encoding="utf-8")

    # Browser-Vorschau mit lokalen Pfaden (relativ zum out-Ordner)
    preview = html_out
    for name, url in img_url.items():
        local = Path(os_relpath(charts_dir / name, out_dir)).as_posix()
        preview = preview.replace(esc(url), esc(local))
    (out_dir / "preview.html").write_text(preview, encoding="utf-8")

    html_bytes = len(html_out.encode("utf-8"))
    max_bytes = cfg.get("limits", {}).get("html_max_bytes", 92000)
    if html_bytes > max_bytes:
        warnings.append(f"HTML ist {html_bytes} Bytes (> {max_bytes}) – Gmail kürzt ab ~102 KB. Texte straffen.")
    meta = {
        "date": issue["date"],
        "subject": subject,
        "html_file": str(out_dir / "newsletter.html"),
        "text_file": str(out_dir / "newsletter.txt"),
        "html_bytes": html_bytes,
        "approx_tokens": round(html_bytes / 3.6),
        "image_urls": list(img_url.values()),
        "chart_files": [str(charts_dir / n) for n in img_url],
        "warnings": warnings,
        "errors": [],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK      {out_dir / 'newsletter.html'} ({html_bytes} Bytes, ~{meta['approx_tokens']} Tokens)")
    print(f"BETREFF {subject}")
    for u in img_url.values():
        print(f"BILD    {u}")
    for w in warnings:
        print(f"WARNUNG {w}", file=sys.stderr)
    return 0


def os_relpath(target: Path, start: Path) -> str:
    import os
    return os.path.relpath(str(target), str(start.resolve()))


if __name__ == "__main__":
    sys.exit(main())
