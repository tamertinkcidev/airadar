#!/usr/bin/env python3
"""Rendert die Newsletter-Charts aus einer JSON-Spec in Tinkellect-Farben (brand.json).

Aufruf:
    python charts.py --spec out/2026-09-27/charts.json --out out/2026-09-27/charts

Spec-Format (vollständiges Beispiel: examples/charts.example.json):
{
  "charts": [
    {"type": "hbar", "file": "tau2_retail.png",
     "title": "τ²-bench Retail – Erfolgsquote (pass^1)", "subtitle": "Stand 27.09.2026",
     "unit": " %", "data": [["Modell A", 84.2], ["Modell B", 79.0]],
     "highlight": ["Modell A"], "source": "τ²-bench Leaderboard", "xlim": [0, 100]},
    {"type": "delta", "file": "delta.png", "title": "Veränderung ggü. Vorwoche",
     "unit": " pp", "data": [["Modell A", 2.1], ["Modell B", -0.8]], "source": "..."},
    {"type": "scatter", "file": "cost_vs_score.png", "title": "Kosten vs. Leistung",
     "x_label": "$ je 1 Mio. Output-Tokens (log)", "y_label": "Intelligence Index",
     "x_log": true, "points": [{"label": "Modell A", "x": 15, "y": 68, "highlight": true}],
     "source": "Artificial Analysis"}
  ]
}

Der Dateiname ist die Referenz in content.json ("chart": "tau2_retail.png"); build_newsletter.py
baut daraus die öffentliche Bild-URL. Erlaubt sind nur Buchstaben, Ziffern, "_" und "-".

Exit-Codes: 0 alles gerendert, 1 mindestens ein Chart fehlgeschlagen, 2 Spec unbrauchbar.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parent
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+\.png$")
NEUTRAL_POINT = "#7C8AA6"


def load_brand() -> dict:
    with open(ROOT / "brand.json", encoding="utf-8") as f:
        return json.load(f)


def setup_fonts(brand: dict) -> str | None:
    """Registriert die Display-Schrift (z. B. Bruno Ace), falls die TTF im Ordner liegt."""
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["font.size"] = 11
    ttf = brand.get("fonts", {}).get("display_ttf")
    if ttf:
        path = ROOT / ttf
        if path.is_file():
            font_manager.fontManager.addfont(str(path))
            return font_manager.FontProperties(fname=str(path)).get_name()
    return None


def _num(v: float, signed: bool = False) -> str:
    """Deutsche Zahlenformatierung: 84,2 / 1.250 / +2,1."""
    if abs(v) >= 1000:
        txt = f"{v:,.0f}".replace(",", ".")
    elif float(v).is_integer():
        txt = str(int(v))
    else:
        txt = f"{v:.1f}".replace(".", ",")
    if signed and v > 0:
        txt = "+" + txt
    return txt


def _fmt(v, unit: str, signed: bool = False) -> str:
    if v is None:
        return "n/a"
    return f"{_num(v, signed)}{unit}"


def _frame(fig, ax, spec: dict, brand: dict, display_font: str | None) -> None:
    """Gemeinsamer Rahmen: Titel, Untertitel, Quelle, Brand-Marke, Achsen-Styling."""
    c = brand["colors"]
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(c["border"])
    ax.tick_params(axis="y", length=0, labelsize=10.5, colors=c["text"])
    ax.tick_params(axis="x", labelsize=9, colors=c["text_muted"])
    ax.set_axisbelow(True)

    title_kw = {"fontsize": 14, "color": c["text"], "fontweight": "bold"}
    if display_font:
        title_kw = {"fontsize": 13.5, "color": c["text"], "fontfamily": display_font}
    fig.text(0.03, 0.96, spec.get("title", ""), ha="left", va="top", **title_kw)
    if spec.get("subtitle"):
        fig.text(0.03, 0.905, spec["subtitle"], ha="left", va="top",
                 fontsize=9.5, color=c["text_muted"])
    if spec.get("source"):
        fig.text(0.03, 0.018, f"Quelle: {spec['source']}", ha="left", va="bottom",
                 fontsize=8, color=c["text_muted"])
    fig.text(0.97, 0.018, brand.get("newsletter_title", ""), ha="right", va="bottom",
             fontsize=8, color=c["accent"])


def render_hbar(spec: dict, brand: dict, display_font: str | None, out_path: Path,
                signed: bool = False) -> None:
    c = brand["colors"]
    rows = [(str(r[0]), None if r[1] is None else float(r[1])) for r in spec["data"]]
    if not rows:
        raise ValueError("data ist leer")
    if spec.get("sort", True):
        rows.sort(key=lambda r: (r[1] is None, -(r[1] if r[1] is not None else 0.0)))
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    n = len(rows)
    highlight = set(spec.get("highlight", []))
    unit = spec.get("unit", "")

    fig_h = max(2.9, 0.5 * n + 2.1)
    fig, ax = plt.subplots(figsize=(8, fig_h), dpi=150)
    ypos = list(range(n))[::-1]
    if signed:
        colors = [c["positive"] if (v or 0) >= 0 else c["negative"] for v in values]
    else:
        colors = [c["accent"] if lab in highlight else c["chart_bar"] for lab in labels]
    plotted = [v if v is not None else 0.0 for v in values]
    bars = ax.barh(ypos, plotted, color=colors, height=0.62)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    for tick, lab in zip(ax.get_yticklabels(), labels):
        if lab in highlight:
            tick.set_fontweight("bold")

    vals = [v for v in values if v is not None]
    if signed:
        m = max([abs(v) for v in vals] + [1.0])
        xlim = spec.get("xlim") or [-m * 1.35, m * 1.35]
        ax.axvline(0, color=c["text_muted"], linewidth=0.8)
    else:
        m = max(vals + [0.0])
        xlim = spec.get("xlim") or [0, (m * 1.18) if m > 0 else 1.0]
    ax.set_xlim(xlim)
    span = float(xlim[1]) - float(xlim[0])
    for bar, v in zip(bars, values):
        txt = _fmt(v, unit, signed)
        w = bar.get_width()
        y = bar.get_y() + bar.get_height() / 2
        if signed and w < 0:
            ax.text(w - span * 0.01, y, txt, va="center", ha="right", fontsize=10, color=c["text"])
        else:
            ax.text(w + span * 0.01, y, txt, va="center", ha="left", fontsize=10, color=c["text"])
    ax.xaxis.grid(True, color=c["border"], linewidth=0.8)
    if spec.get("x_label"):
        ax.set_xlabel(spec["x_label"], fontsize=9, color=c["text_muted"])

    _frame(fig, ax, spec, brand, display_font)
    fig.tight_layout(rect=[0, 0.06, 1, 0.86])
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)


def render_scatter(spec: dict, brand: dict, display_font: str | None, out_path: Path) -> None:
    c = brand["colors"]
    pts = spec.get("points", [])
    if not pts:
        raise ValueError("points ist leer")
    fig, ax = plt.subplots(figsize=(8, 5.4), dpi=150)
    for p in pts:
        hl = bool(p.get("highlight"))
        x, y = float(p["x"]), float(p["y"])
        ax.scatter([x], [y], s=85 if hl else 60, color=c["accent"] if hl else NEUTRAL_POINT,
                   zorder=3, edgecolors="white", linewidths=1)
        ax.annotate(str(p.get("label", "")), (x, y), xytext=(6, 5), textcoords="offset points",
                    fontsize=8.5, color=c["text"], fontweight="bold" if hl else "normal")
    ax.margins(x=0.14, y=0.14)  # Platz für Labels am Rand
    if spec.get("x_log"):
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _num(v)))
        ax.xaxis.set_minor_formatter(NullFormatter())
    if spec.get("y_log"):
        ax.set_yscale("log")
    ax.grid(True, color=c["border"], linewidth=0.8)
    ax.set_xlabel(spec.get("x_label", ""), fontsize=9.5, color=c["text_muted"])
    ax.set_ylabel(spec.get("y_label", ""), fontsize=9.5, color=c["text_muted"])

    _frame(fig, ax, spec, brand, display_font)
    fig.tight_layout(rect=[0, 0.06, 1, 0.86])
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Newsletter-Charts rendern")
    ap.add_argument("--spec", required=True, help="Pfad zu charts.json")
    ap.add_argument("--out", required=True, help="Zielordner für die PNGs")
    args = ap.parse_args()

    brand = load_brand()
    display_font = setup_fonts(brand)
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    charts = spec.get("charts", [])
    if not charts:
        print("FEHLER: keine Charts in der Spec", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    for ch in charts:
        name = str(ch.get("file", ""))
        if not SAFE_NAME.match(name):
            print(f"FEHLER: ungültiger Dateiname {name!r} (erlaubt: a-z, 0-9, _, - und .png)",
                  file=sys.stderr)
            errors += 1
            continue
        out_path = out_dir / name
        try:
            t = ch.get("type", "hbar")
            if t == "hbar":
                render_hbar(ch, brand, display_font, out_path)
            elif t == "delta":
                render_hbar(ch, brand, display_font, out_path, signed=True)
            elif t == "scatter":
                render_scatter(ch, brand, display_font, out_path)
            else:
                raise ValueError(f"unbekannter Chart-Typ {t!r} (hbar | delta | scatter)")
            print(f"OK      {out_path}")
        except Exception as exc:  # noqa: BLE001 – jeden Fehler melden, weiterrendern
            errors += 1
            print(f"FEHLER  {name}: {exc}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
