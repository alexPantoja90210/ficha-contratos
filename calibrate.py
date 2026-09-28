#!/usr/bin/env python3
"""Per-row confidence that means what it says (AITRT-RISK-MODEL-003).

The page used to put one number beside every row of a clause: the accuracy that
clause scored over 101 contracts. A reader sees "90%" next to a value and reads
"90% likely to be right for THIS contract". It never meant that. It was a
population rate, identical on the row the detector was sure about and on the row
it barely decided.

For presence clauses there is a real per-row signal: how far the window score
sits from the calibrated threshold. A row that clears the threshold by a wide
margin is not the same claim as one that clears it by nothing. This fits
margin -> observed accuracy on the validation split and reports Expected
Calibration Error on the held-out split, before and after.

For rule-based clauses there is no comparable signal. The rule either produced a
value or it did not, and nothing separates a confident extraction from a lucky
one. Those rows keep the population rate and the interface says so rather than
dressing it up.

Usage:  python calibrate.py contracts.json master_clauses.csv
"""
import ast, csv, io, json, sys
from pathlib import Path

import retrieval as REC
from locator import key_of
from presence import PresenceDetector
from scope import decide

BINS = [0.0, 0.02, 0.05, 0.10, 1.0]   # |score - threshold|
MIN_PER_BIN = 8

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

def bin_of(margin):
    for i in range(len(BINS) - 1):
        if BINS[i] <= margin < BINS[i + 1]:
            return i
    return len(BINS) - 2

def observations(names, contracts, rows, det, cats, cache):
    """(clause, margin bin, was the row correct) for every judgeable row."""
    out = []
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n
    for row in rows:
        name = stem(row["Filename"])
        text = contracts.get(name)
        if text is None or name not in names:
            continue
        for cat in cats:
            gold = has_span(row, cat)
            if gold is None:
                continue
            score, _ = REC.score_windows(text, det.cues[cat], cache)
            thr = det.thresholds[cat]
            out.append((cat, bin_of(abs(score - thr)), (score >= thr) == gold))
    return out

def ece(pairs):
    """Expected Calibration Error: how far a stated confidence is from reality."""
    total = sum(n for _, n, _ in pairs)
    return sum(n * abs(conf - acc) for conf, n, acc in pairs) / total if total else 0.0

def main(corpus, clauses):
    contracts = json.loads(Path(corpus).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(clauses).read_text(encoding="utf-8-sig", errors="replace"))))
    names = sorted(contracts)
    n = len(names)
    val = set(names[int(n * .6):int(n * .8)])
    test = set(names[int(n * .8):])

    det = PresenceDetector()
    inside, _ = decide()
    cats = [f["category"] for f in inside if f["engine"] == "presence"]
    cache = {}

    # fit on validation
    fitted = {}
    for cat in cats:
        obs = [o for o in observations(val, contracts, rows, det, [cat], cache)]
        table = {}
        for b in range(len(BINS) - 1):
            hits = [ok for _, bb, ok in obs if bb == b]
            if len(hits) >= MIN_PER_BIN:
                table[b] = sum(hits) / len(hits)
        base = sum(ok for _, _, ok in obs) / len(obs) if obs else 0.0
        fitted[cat] = {"bins": table, "fallback": base}

    # evaluate on held-out
    print(f"{'clause':24}{'margin band':>14}{'n':>5}{'stated':>9}{'actual':>9}")
    before, after = [], []
    flat = {f["category"]: None for f in inside}
    from build_page import tested_for
    for cat in cats:
        obs = observations(test, contracts, rows, det, [cat], cache)
        pop = tested_for(cat) / 100.0
        for b in range(len(BINS) - 1):
            hits = [ok for _, bb, ok in obs if bb == b]
            if not hits:
                continue
            acc = sum(hits) / len(hits)
            cal = fitted[cat]["bins"].get(b, fitted[cat]["fallback"])
            band = f"{BINS[b]:.2f}-{BINS[b+1]:.2f}"
            print(f"{cat[:23]:24}{band:>14}{len(hits):>5}{100*cal:>8.0f}%{100*acc:>8.0f}%")
            before.append((pop, len(hits), acc))
            after.append((cal, len(hits), acc))
    print()
    print(f"Expected Calibration Error, one flat number per clause : {100*ece(before):.1f}%")
    print(f"Expected Calibration Error, calibrated by margin       : {100*ece(after):.1f}%")
    Path("calibration.json").write_text(
        json.dumps({c: {"bins": {str(k): v for k, v in f["bins"].items()},
                        "fallback": f["fallback"], "edges": BINS}
                    for c, f in fitted.items()}, indent=2), encoding="utf-8")
    print("\nwritten: calibration.json")
    print("Rule-based clauses are not calibrated: the rule gives no per-row")
    print("signal, so those rows carry the clause's measured accuracy and the")
    print("interface labels it as exactly that.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../cuad/contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
