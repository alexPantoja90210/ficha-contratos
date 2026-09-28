#!/usr/bin/env python3
"""Measures the WHOLE sheet, row by row, on contracts never seen before.

The earlier measurements were per category. This one is per sheet: of the rows that
can be judged, how many come out right on the same contract. That is what happens
to a user, who does not read a category but a page.

Usage:  python measure_sheet.py contracts.json master_clauses.csv
"""
import ast, csv, io, json, sys
from collections import Counter
from pathlib import Path

import measure_rules as R
from locator import TextLocator, key_of
from presence import PresenceDetector
from scope import decide

COMPARATORS = {
    "document name":  (R.rule_name, R.same_text),
    "governing law":  (R.rule_law,    R.same_contains),
    "agreement date": (R.rule_date,  R.same_date),
    "effective date": (R.rule_date,  R.same_date),
}

def column_for(row, cat):
    k = key_of(cat)
    for c in row:
        if c.endswith("-Answer") or c.endswith("- Answer"):
            if key_of(c.replace("- Answer", "").replace("-Answer", "")) == k:
                return c
    return None

def has_span(row, cat):
    k = key_of(cat)
    for c in row:
        if c.endswith("Answer"):
            continue
        if key_of(c) == k:
            cell = (row.get(c) or "").strip()
            try:
                v = ast.literal_eval(cell) if cell else []
            except (ValueError, SyntaxError):
                v = [cell] if cell else []
            return bool(v)
    return None

def main(corpus_path, clauses_path):
    contracts = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(clauses_path).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n

    inside, _ = decide()
    det = PresenceDetector()
    held_out_names = set(sorted(contracts)[int(len(contracts) * 0.8):])

    by_cat = {f["category"]: [0, 0] for f in inside}
    by_sheet, total_rows = [], 0

    for row in rows:
        name = stem(row["Filename"])
        text = contracts.get(name)
        if text is None or name not in held_out_names:
            continue
        loc = TextLocator(text)
        ok_count = judgeable = 0
        for f in inside:
            cat = f["category"]
            if f["engine"] == "rule":
                col = column_for(rows[0], cat)
                gold = (row.get(col) or "").strip() if col else ""
                if not gold or R.REDACTED.fullmatch(gold):
                    continue
                rule, cmp_ = COMPARATORS[key_of(cat)]
                ok = cmp_(rule(loc.fragments(cat)), gold)
            else:
                gold = has_span(row, cat)
                if gold is None:
                    continue
                state, _, _ = det.evaluate(cat, text)
                ok = (state == "found") == gold
            judgeable += 1
            ok_count += ok
            by_cat[cat][0] += ok
            by_cat[cat][1] += 1
        if judgeable:
            by_sheet.append((ok_count, judgeable))
            total_rows += judgeable

    print(f"held-out contracts judged: {len(by_sheet)}")
    print(f"judgeable rows in total : {total_rows}\n")

    print(f"{'category':36}{'engine':11}{'ok_count':>6}{'of':>5}{'%':>7}")
    for f in inside:
        b, n = by_cat[f["category"]]
        if n:
            print(f"{f['category']:36}{f['engine']:11}{b:>6}{n:>5}{100*b/n:>6.0f}%")

    total_ok = sum(b for b, _ in by_sheet)
    print(f"\nrows correct: {total_ok}/{total_rows} = "
          f"{100*total_ok/total_rows:.1f}%")

    dist = Counter(round(10 * b / n) for b, n in by_sheet)
    print("\nsheets by share of rows correct:")
    for k in sorted(dist, reverse=True):
        bar = "#" * dist[k]
        print(f"  {k*10:>3}% {dist[k]:>4} sheets  {bar}")
    perfect = sum(1 for b, n in by_sheet if b == n)
    print(f"\nsheets with no errors at all: {perfect} of {len(by_sheet)} "
          f"({100*perfect/len(by_sheet):.0f}%)")
    eighty = sum(1 for b, n in by_sheet if b / n >= 0.8)
    print(f"sheets 80% correct or better: {eighty} ({100*eighty/len(by_sheet):.0f}%)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
