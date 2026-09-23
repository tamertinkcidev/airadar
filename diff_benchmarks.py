#!/usr/bin/env python3
"""Vergleicht data/benchmarks.json mit dem jüngsten Snapshot in data/history/ und schreibt Deltas.

Aufruf:
    python diff_benchmarks.py --out out/2026-09-27/deltas.json

Ausgabe: Tabelle auf stdout + JSON mit allen geänderten/neuen Werten, gruppiert je Benchmark,
direkt verwendbar für ein "delta"-Chart in charts.json:
    {"type": "delta", "file": "delta_bfcl.png", "title": "...", "unit": " pp",
     "data": <deltas["bfcl"]["chart_data"]>}

Exit-Codes: 0 ok, 3 kein Snapshot vorhanden (Baseline-Ausgabe → kein Delta-Chart).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--current", default=str(ROOT / "data" / "benchmarks.json"))
    ap.add_argument("--snapshot", default=None, help="expliziter Snapshot; sonst der jüngste in data/history/")
    args = ap.parse_args()

    current = load(Path(args.current))
    if args.snapshot:
        snap_path = Path(args.snapshot)
    else:
        # Der jüngste Snapshot ist der Stand VOR den Updates dieses Laufs (Schritt 1 des Ablaufs).
        snaps = sorted((ROOT / "data" / "history").glob("*-benchmarks.json"))
        if not snaps:
            print("KEIN SNAPSHOT – Baseline-Ausgabe, kein Delta-Chart möglich.")
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps({"snapshot": None, "benchmarks": {}}, indent=2), encoding="utf-8")
            return 3
        snap_path = snaps[-1]
    old = load(snap_path)
    out: dict = {"snapshot": snap_path.name, "benchmarks": {}}
    rows: list[str] = []
    for key, b in current.get("benchmarks", {}).items():
        ob = old.get("benchmarks", {}).get(key, {})
        changes = []
        for model, r in (b.get("results") or {}).items():
            nv = r.get("value")
            ov = (ob.get("results") or {}).get(model, {}).get("value")
            if nv is None:
                continue
            if ov is None:
                changes.append({"model": model, "old": None, "new": nv, "delta": None, "kind": "neu"})
                rows.append(f"{b['name']:<42} {model:<28} neu: {nv}")
            elif abs(float(nv) - float(ov)) > 1e-9:
                d = round(float(nv) - float(ov), 2)
                changes.append({"model": model, "old": ov, "new": nv, "delta": d, "kind": "geändert"})
                rows.append(f"{b['name']:<42} {model:<28} {ov} -> {nv} ({d:+})")
        if changes:
            out["benchmarks"][key] = {
                "name": b["name"],
                "metric": b.get("metric", ""),
                "changes": changes,
                "chart_data": [[c["model"], c["delta"]] for c in changes if c["delta"] is not None],
            }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Snapshot: {snap_path.name}")
    print("\n".join(rows) if rows else "Keine Wertänderungen gegenüber dem Snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
