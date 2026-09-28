#!/usr/bin/env python3
"""Does the sheet work equally well across kinds of contract? (MEASURE 2.11)

A single overall figure hides who the product fails. This reports accuracy per
clause broken down two ways -- by agreement type and by document length -- and
shows the SPREAD rather than the mean.

The agreement type comes from the contract's own file name, which CUAD ends with
the kind of agreement it is. No extra data is needed.

Counts per group are small (5 to 9 contracts in the held-out split), so a
Wilson interval is printed with every rate. A gap narrower than the intervals
is not a finding, and the report says so rather than leaving it to the reader.

Usage:  python measure_bias.py contracts.json master_clauses.csv
"""
import ast, csv, io, json, math, re, sys
from collections import defaultdict
from pathlib import Path

import measure_rules as R
from locator import TextLocator, key_of
from presence import PresenceDetector
from scope import decide

MIN_GROUP = 5          # a group smaller than this is not reported on its own

COMPARATORS = {
    "document name":  (R.rule_name, R.same_text),
    "governing law":  (R.rule_law,  R.same_contains),
    "agreement date": (R.rule_date, R.same_date),
    "effective date": (R.rule_date, R.same_date),
}

def agreement_type(name):
    tail = re.split(r"[_-]", name)[-1].strip()
    return re.sub(r"\s*\d+$", "", tail).upper()[:34] or "?"

def wilson(ok, n, z=1.96):
    """Interval for a rate from few observations; the plain rate misleads here."""
    if not n:
        return (0.0, 0.0)
    p = ok / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))

def answer_column(row, cat):
    k = key_of(cat)
    for c in row:
        if c.endswith("-Answer") or c.endswith("- Answer"):
            if key_of(c.replace("- Answer", "").replace("-Answer", "")) == k:
                return c

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

def main(corpus, clauses):
    contracts = json.loads(Path(corpus).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(clauses).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n
    held_out = set(sorted(contracts)[int(len(contracts) * 0.8):])
    inside, _ = decide()
    det = PresenceDetector()

    # tally[clause][group] = [ok, n]
    by_type = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    by_size = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    lengths = sorted(len(contracts[n]) for n in held_out)
    q = [lengths[len(lengths) * i // 4] for i in (1, 2, 3)]
    def bucket(L):
        return ("Q1 shortest" if L <= q[0] else "Q2" if L <= q[1]
                else "Q3" if L <= q[2] else "Q4 longest")

    for row in rows:
        name = stem(row["Filename"])
        text = contracts.get(name)
        if text is None or name not in held_out:
            continue
        loc = TextLocator(text)
        kind, size = agreement_type(name), bucket(len(text))
        for f in inside:
            cat = f["category"]
            if f["engine"] == "rule":
                col = answer_column(rows[0], cat)
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
            for tally, group in ((by_type, kind), (by_size, size)):
                tally[cat][group][0] += ok
                tally[cat][group][1] += 1

    def report(title, tally, order=None):
        print(f"\n{'='*74}\n{title}\n{'='*74}")
        groups = order or sorted({g for c in tally.values() for g in c})
        groups = [g for g in groups
                  if sum(tally[c][g][1] for c in tally) >= MIN_GROUP * len(tally)]
        head = "".join(f"{g[:13]:>15}" for g in groups)
        print(f"{'clause':26}{head}{'spread':>9}")
        wide = []
        for cat in sorted(tally):
            cells, rates = "", []
            for g in groups:
                ok, n = tally[cat][g]
                if n < MIN_GROUP:
                    cells += f"{'-':>15}"
                    continue
                rates.append(ok / n)
                cells += f"{ok:>7}/{n:<3}{100*ok/n:>4.0f}%"
            if not rates:
                continue
            spread = 100 * (max(rates) - min(rates))
            print(f"{cat:26}{cells}{spread:>8.0f}")
            lo_hi = [wilson(*tally[cat][g]) for g in groups if tally[cat][g][1] >= MIN_GROUP]
            overlap = max(a for a, _ in lo_hi) <= min(b for _, b in lo_hi)
            if spread >= 30 and not overlap:
                wide.append((cat, spread, groups, tally))
        return wide

    types = [t for t, _ in sorted(
        {t: sum(by_type[c][t][1] for c in by_type) for c in by_type for t in by_type[c]}.items(),
        key=lambda kv: -kv[1])]
    wide_t = report("Accuracy by agreement type", by_type, types)
    wide_s = report("Accuracy by document length", by_size,
                    ["Q1 shortest", "Q2", "Q3", "Q4 longest"])

    print(f"\n{'='*74}\nVERDICT\n{'='*74}")
    if not (wide_t or wide_s):
        print("No clause shows a gap wider than 30 points whose intervals also")
        print("separate. With 5 to 9 contracts per group that is the most this")
        print("split can say: no bias demonstrated, not bias ruled out.")
    else:
        print("Clauses where one group is served materially worse, with")
        print("non-overlapping intervals:")
        for cat, spread, *_ in wide_t + wide_s:
            print(f"  {cat:30} spread {spread:.0f} points")
        print("\nA clause that fails one kind of contract is not the overall")
        print("figure for a reader who only has that kind. Agreement type")
        print("belongs in the scope criterion.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../cuad/contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
