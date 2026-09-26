#!/usr/bin/env python3
"""Computes the TRIVIAL FLOOR of each presence category in CUAD.

The trivial floor is what a system scores by always answering the majority class —
normally "no, that clause is not there". Any result below that floor is worth less
than doing nothing.

It exists for one purpose: to stop us publishing a number that looks good and is
not. Run it BEFORE building, not after.

Usage:  python trivial_floor.py master_clauses.csv [out.csv]
"""
import csv, io, sys
from pathlib import Path

SKEW_WARNING = 75.0     # por encima: la accuracy deja de ser informativa
USEFUL        = 65.0     # por debajo: un numero de accuracy si significa algo

def answer_column(row, category):
    for suf in ("-Answer", "- Answer"):
        if category + suf in row:
            return category + suf
    return None

def main(path, out=None):
    rows = list(csv.DictReader(io.StringIO(
        Path(path).read_text(encoding="utf-8-sig", errors="replace"))))
    report = []
    for cat in list(rows[0]):
        if cat.endswith("-Answer") or cat.endswith("- Answer") or cat == "Filename":
            continue
        col = answer_column(rows[0], cat)
        if not col:
            continue
        vals = [(f.get(col) or "").strip() for f in rows]
        vals = [v for v in vals if v]
        if not vals or not set(vals) <= {"Yes", "No"}:
            continue
        si, no = vals.count("Yes"), vals.count("No")
        floor = 100 * max(si, no) / len(vals)
        report.append({
            "category": cat,
            "si": si, "no": no, "total": len(vals),
            "trivial_floor_pct": round(floor, 1),
            "majority_class": "Yes" if si >= no else "No",
            # con clase minoritaria escasa, la accuracy miente: lo que importa
            # es cuantas de las que SI estan logramos encontrar
            "valid_metric": "accuracy" if floor < USEFUL else "recall_clase_minoritaria",
            "human_confirmations": min(si, no),
        })
    report.sort(key=lambda r: -r["trivial_floor_pct"])

    ancho = max(len(r["category"]) for r in report)
    print(f"{'category':{ancho}}{'Yes':>6}{'No':>6}{'floor':>8}  valid metrictes")
    for r in report:
        print(f"{r['category']:{ancho}}{r['si']:>6}{r['no']:>6}"
              f"{r['trivial_floor_pct']:>7.1f}%  {r['valid_metric']}")

    pisos = [r["trivial_floor_pct"] for r in report]
    print(f"\npresence categories        : {len(report)}")
    print(f"mean trivial floor          : {sum(pisos)/len(pisos):.1f}%")
    print(f"skewed >= {SKEW_WARNING:.0f}% (accuracy miente): "
          f"{sum(1 for p in pisos if p >= SKEW_WARNING)}")
    print(f"balanceadas (< {USEFUL:.0f}%, accuracy works): "
          f"{sum(1 for p in pisos if p < USEFUL)}")
    print(f"human confirmations if only the rare class is confirmed: "
          f"{sum(r['human_confirmations'] for r in report)} of "
          f"{len(report)*len(rows)} cells")

    print("\nRULE: never publish accuracy averaged across categories. Report, "
          "per category, its gain over its own floor, and for skewed ones "
          "the minority-class recall.")

    if out:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(report[0]))
            w.writeheader()
            w.writerows(report)
        print(f"\nwritten: {out}")
    return report

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "master_clauses.csv",
         sys.argv[2] if len(sys.argv) > 2 else "trivial_floor.csv")
