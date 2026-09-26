#!/usr/bin/env python3
"""What the product covers, decided by measurement rather than taste.

A category is in scope only if it can close on its own with evidence:

  rule      end-to-end accuracy >= 65% over the 510 contracts
  presence  balanced accuracy >= 70% AND recall >= 70% on the held_out split,
            with a calibratable threshold
  both      it must beat the NAIVE PARSE (baseline_naive.py): the first line,
            the first date, the first state named, or "not present" every time.
            A category that cannot beat that does not justify existing, however
            good its balanced accuracy looks.

Recall is in the criterion on purpose. A category that detects well but misses the
ones that are there cannot assert absence, and a sheet that cannot say "not
present" is useless for reviewing a contract.

What does not make the cut is not deleted: it stays listed, with its number. A
scope is a decision you can argue with, not a list of whatever came out well.
"""
import json
from pathlib import Path

MIN_RULE      = 65.0
MIN_BALANCED = 70.0
MIN_RECALL     = 70.0

# Acierto del parseo naive y del producto, misma particion de held_out.
# Fuente: baseline_ingenuo.py y medir_ficha.py.
NAIVE = {
    "Document Name": 5, "Governing Law": 38, "Cap On Liability": 42,
    "Agreement Date": 53, "License Grant": 55, "Audit Rights": 56,
    "Effective Date": 50, "Insurance": 65, "No-Solicit Of Employees": 90,
    "Warranty Duration": 83,
}
PRODUCT = {
    "Document Name": 66, "Governing Law": 90, "Cap On Liability": 86,
    "Agreement Date": 74, "License Grant": 76, "Audit Rights": 73,
    "Effective Date": 67, "Insurance": 76, "No-Solicit Of Employees": 80,
    "Warranty Duration": 76,
}

def beats_naive(cat):
    """None cuando no hay medicion del naive para esa category."""
    if cat not in NAIVE:
        return None
    return PRODUCT[cat] > NAIVE[cat]

# acierto de punta a punta medido en medir_e2e.py
RULES_MEASURED = {
    "Governing Law":                      91.0,
    "Agreement Date":                     73.6,
    "Document Name":                      71.9,
    "Effective Date":                      68.0,
    "Notice Period to Terminate Renewal":  61.2,
    "Renewal Term":                        60.6,
    "Parties":                              5.8,
}

def decide(path="retrieval_model.json"):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    perf = {r["category"]: r for r in d["test"]}

    inside, outside = [], []
    for cat, pct in RULES_MEASURED.items():
        row = dict(category=cat, engine="rule", measure=pct, criterion="acierto e2e",
                    naive=NAIVE.get(cat))
        gana = beats_naive(cat)
        (inside if pct >= MIN_RULE and gana is not False else outside).append(row)

    for cat, r in perf.items():
        row = dict(category=cat, engine="presence", measure=r["balanced"],
                    recall=r["recall"], criterion="balanced y recall",
                    naive=NAIVE.get(cat))
        gana = beats_naive(cat)
        if (r["balanced"] >= MIN_BALANCED and r["recall"] >= MIN_RECALL
                and gana is not False):
            inside.append(row)
        else:
            outside.append(row)

    inside.sort(key=lambda f: -f["measure"])
    outside.sort(key=lambda f: -f["measure"])
    return inside, outside

if __name__ == "__main__":
    inside, outside = decide()
    print(f"IN SCOPE ({len(inside)})")
    for f in inside:
        ing = f"  naive {f['naive']}%" if f.get("naive") is not None else ""
        print(f"  {f['category']:36}{f['engine']:11}{f['measure']:5.1f}%{ing}")
    print(f"\nFUERA ({len(outside)}) -- con su numero, para que la decision se pueda discutir")
    for f in outside:
        rec = f"  recall {f['recall']:.0f}%" if "recall" in f else ""
        ing = (f"  LOSES to the naive parse ({f['naive']}%)"
               if f.get("naive") is not None and PRODUCT.get(f["category"], 0) <= f["naive"]
               else "")
        print(f"  {f['category']:36}{f['engine']:11}{f['measure']:5.1f}%{rec}{ing}")
