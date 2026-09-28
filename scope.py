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

# Accuracy of the naive parse and of the product, same held_out partition.
# Source: baseline_naive.py and measure_sheet.py.
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
    """None when there is no naive measurement for that category."""
    if cat not in NAIVE:
        return None
    return PRODUCT[cat] > NAIVE[cat]

# End-to-end accuracy as measure_e2e.py prints it over the 510 contracts.
# These are transcribed figures, so they drift if nobody re-runs the script.
# measure_e2e.py is the source; if the two disagree, the script is right.
RULES_MEASURED = {
    "Governing Law":                      91.0,
    "Agreement Date":                     73.6,
    "Document Name":                      71.7,
    "Effective Date":                      68.0,
    "Notice Period to Terminate Renewal":  42.9,
    "Renewal Term":                        48.8,
    "Parties":                              4.6,
}

def decide(path="retrieval_model.json"):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    perf = {r["category"]: r for r in d["test"]}

    inside, outside = [], []
    for cat, pct in RULES_MEASURED.items():
        row = dict(category=cat, engine="rule", measure=pct,
                   criterion="end-to-end accuracy", naive=NAIVE.get(cat))
        beats = beats_naive(cat)
        (inside if pct >= MIN_RULE and beats is not False else outside).append(row)

    for cat, r in perf.items():
        row = dict(category=cat, engine="presence", measure=r["balanced"],
                   recall=r["recall"], criterion="balanced accuracy and recall",
                   naive=NAIVE.get(cat))
        beats = beats_naive(cat)
        if (r["balanced"] >= MIN_BALANCED and r["recall"] >= MIN_RECALL
                and beats is not False):
            inside.append(row)
        else:
            outside.append(row)

    inside.sort(key=lambda r: -r["measure"])
    outside.sort(key=lambda r: -r["measure"])
    return inside, outside

if __name__ == "__main__":
    inside, outside = decide()
    print(f"IN SCOPE ({len(inside)})")
    for r in inside:
        nv = f"  naive {r['naive']}%" if r.get("naive") is not None else ""
        print(f"  {r['category']:36}{r['engine']:11}{r['measure']:5.1f}%{nv}")
    print(f"\nOUT OF SCOPE ({len(outside)}) -- with its number, so the decision can be argued with")
    for r in outside:
        rec = f"  recall {r['recall']:.0f}%" if "recall" in r else ""
        nv = (f"  LOSES to the naive parse ({r['naive']}%)"
              if r.get("naive") is not None and PRODUCT.get(r["category"], 0) <= r["naive"]
              else "")
        print(f"  {r['category']:36}{r['engine']:11}{r['measure']:5.1f}%{rec}{nv}")
