#!/usr/bin/env python3
"""Measures END TO END: locate the clause in the raw contract, then normalize it.

Compares against measure_rules.py, which starts from the paragraph the annotator
already marked. The gap between the two columns is exactly what it costs to have to
find the clause yourself.

Usage:  python measure_e2e.py contracts.json master_clauses.csv
"""
import csv, io, json, sys
from pathlib import Path

import measure_rules as R
from locator import TextLocator
from text_rules import parties_from_text

# category -> (regla, comparador, % medido con el parrafo ya localizado)
CASES = [
    ("Document Name",                      R.rule_name,     R.same_text,    97.6),
    ("Governing Law",                      R.rule_law,        R.same_contains, 95.1),
    ("Notice Period To Terminate Renewal", R.rule_notice,   R.same_contains, 87.0),
    ("Parties",                            parties_from_text,    R.same_parties,   86.4),
    ("Agreement Date",                     R.rule_date,      R.same_date,    85.5),
    ("Effective Date",                     R.rule_date,      R.same_date,    82.6),
    ("Renewal Term",                       R.rule_renewal, R.same_contains, 61.3),
]

def main(ruta_json, ruta_csv):
    contracts = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))

    # el csv nombra los contracts con extension .pdf; los textos son .txt
    def stem(n): return n[:-4] if n.lower().endswith(".pdf") else n
    missing = sum(1 for f in rows if stem(f["Filename"]) not in contracts)
    print(f"contracts: {len(contracts)}   rows: {len(rows)}   unmatched: {missing}\n")

    print(f"{'category':36}{'with value':>10}{'e2e':>8}{'normalize only':>16}{'cost':>8}")
    summary = []
    for cat, regla, compara, anchor_at in CASES:
        col = R.answer_column(rows[0], cat)
        con = ok = 0
        for row in rows:
            real = (row.get(col) or "").strip()
            if not real or R.REDACTED.fullmatch(real):
                continue
            text = contracts.get(stem(row["Filename"]))
            if text is None:
                continue
            con += 1
            if compara(regla(TextLocator(text).fragments(cat)), real):
                ok += 1
        pct = 100 * ok / con if con else 0.0
        summary.append((cat, con, pct, anchor_at))
        print(f"{cat:36}{con:>10}{pct:>7.1f}%{anchor_at:>15.1f}%{pct-anchor_at:>+7.1f}")
    return summary

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
