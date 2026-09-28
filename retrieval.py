#!/usr/bin/env python3
"""Retrieval layer for the presence categories.

Per category it learns, from the training contracts, which terms separate contracts
that have the clause from those that do not. Then it splits a new contract into
overlapping windows, scores each by the density of those terms, and keeps the best:
that window is the proposed location, and its score decides whether the clause is
there.

It gives the sheet both things it needs — presence AND where — with no model, no
keys, and in seconds. And it sets the floor a model has to clear to earn its hour.

Measurement rules (non-negotiable)
----------------------------------
1. The train/val/test split is BY CONTRACT, never by question: every contract is
   asked 41 times, and splitting questions at random would put the same text on
   both sides of the line.
2. No accuracy averaged across categories. The 79.7% that "always answer absent"
   scores would make this look good without being good.
3. The metric is balanced accuracy, reported against each category's trivial floor.
4. Term ties are broken on the term itself. Python randomizes string hashing per
   process; without this the top-K cutoff lands in a different place on every run
   and the project prints a different number each time.

Usage:  python retrieval.py contracts.json master_clauses.csv
"""
import ast, csv, io, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

WINDOW, STRIDE  = 1600, 800
TOP_TERMS       = 40
SPLIT_FRACTIONS = (0.60, 0.20)    # train, val; the rest is test

WORD_RE = re.compile(r"[a-z][a-z\-']{2,}")
STOPWORDS = set("""the and for any all such that this with shall are not but its his her
their which have has had was were been being from into upon under over more most other
than then them they there these those you your our ous will would may can could should
each either neither both same very much many few less least also only just even still
per pursuant hereof hereto herein hereby thereof thereto therein whereas provided
agreement party parties section article exhibit schedule date dates day days
""".split())


def tokens(text):
    return [t for t in WORD_RE.findall(text.lower()) if t not in STOPWORDS]


# ---------- data ------------------------------------------------------------
def load_data(corpus_path, clauses_path):
    contracts = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(clauses_path).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n

    categories = []
    for c in rows[0]:
        if c.endswith("-Answer") or c.endswith("- Answer") or c == "Filename":
            continue
        col = next((c + s for s in ("-Answer", "- Answer") if c + s in rows[0]), None)
        if not col:
            continue
        vals = {(f.get(col) or "").strip() for f in rows} - {""}
        if vals <= {"Yes", "No"}:
            categories.append((c, col))

    data = []
    for f in rows:
        text = contracts.get(stem(f["Filename"]))
        if text is None:
            continue
        labels, gold = {}, {}
        for c, col in categories:
            cell = (f.get(c) or "").strip()
            try:
                chunks = ast.literal_eval(cell) if cell else []
            except (ValueError, SyntaxError):
                chunks = [cell] if cell else []
            labels[c] = bool(chunks)
            gold[c] = [str(t) for t in chunks]
        data.append(dict(name=f["Filename"], text=text,
                         labels=labels, gold=gold))
    return data, [c for c, _ in categories]


def split_by_contract(data):
    """Split by contract, deterministic and without randomness: by name."""
    ordered = sorted(data, key=lambda d: d["name"])
    n = len(ordered)
    a, b = int(n * SPLIT_FRACTIONS[0]), int(n * (SPLIT_FRACTIONS[0] + SPLIT_FRACTIONS[1]))
    return ordered[:a], ordered[a:b], ordered[b:]


# ---------- term learning ----------------------------------------------------
def learn_cues(train, categories):
    bags = {d["name"]: set(tokens(d["text"])) for d in train}
    cues = {}
    for cat in categories:
        with_, without = Counter(), Counter()
        n_with = n_without = 0
        for d in train:
            b = bags[d["name"]]
            if d["labels"][cat]:
                with_.update(b); n_with += 1
            else:
                without.update(b); n_without += 1
        if n_with < 5:
            cues[cat] = []
            continue
        scores = []
        for t in set(with_) | set(without):
            p = (with_[t] + 0.5) / (n_with + 1)
            q = (without[t] + 0.5) / (n_without + 1)
            scores.append((math.log(p / q), t))
        # Tie-break on the term itself: without this the top-K cutoff moves
        # between runs, because Python randomizes string hashing per process.
        scores.sort(key=lambda x: (-x[0], x[1]))
        cues[cat] = [t for s, t in scores[:TOP_TERMS] if s > 0]
    return cues


# ---------- scoring ----------------------------------------------------------
def windows_of(text):
    return [(i, text[i:i + WINDOW]) for i in range(0, max(1, len(text)), STRIDE)]

def score_windows(text, cue_terms, cache):
    """Best window and its score: share of cue terms present."""
    if not cue_terms:
        return 0.0, None
    if text not in cache:
        cache[text] = [(i, set(tokens(v))) for i, v in windows_of(text)]
    best, where = 0.0, None
    cue_set = set(cue_terms)
    for i, toks in cache[text]:
        s = len(cue_set & toks) / len(cue_set)
        if s > best:
            best, where = s, i
    return best, where


MIN_TO_CALIBRATE = 5   # positives in validation

def calibrate(val, categories, cues, cache):
    """Per-category threshold that maximises balanced accuracy.

    With fewer than MIN_TO_CALIBRATE positives in validation the threshold means
    nothing: the search runs to the extremes and produces a detector that says
    "yes" to everything (4% accuracy) or "no" to everything. Those categories
    are marked NOT CALIBRATABLE rather than publishing an invented number.
    """
    thresholds, uncalibrated = {}, set()
    for cat in categories:
        points = [(score_windows(d["text"], cues[cat], cache)[0], d["labels"][cat])
                  for d in val]
        n_pos = sum(1 for _, y in points if y)
        n_neg = len(points) - n_pos
        if n_pos < MIN_TO_CALIBRATE or n_neg < MIN_TO_CALIBRATE:
            thresholds[cat] = None
            uncalibrated.add(cat)
            continue
        best = (0.0, 0.5)
        for u in [i / 40 for i in range(1, 41)]:
            tp = sum(1 for s, y in points if y and s >= u)
            tn = sum(1 for s, y in points if not y and s < u)
            bal = (tp / n_pos + tn / n_neg) / 2
            if bal > best[0]:
                best = (bal, u)
        thresholds[cat] = best[1]
    return thresholds, uncalibrated


def evaluate(test, categories, cues, thresholds, cache, uncalibrated):
    rows = []
    for cat in categories:
        if cat in uncalibrated:
            continue
        tp = tn = fp = fn = 0
        located_ok = located_n = 0
        for d in test:
            s, where = score_windows(d["text"], cues[cat], cache)
            pred = s >= thresholds[cat]
            real = d["labels"][cat]
            if real and pred:
                tp += 1
                gold = d["gold"][cat]
                if gold and where is not None:
                    located_n += 1
                    chunk = d["text"][where:where + WINDOW]
                    needle = " ".join(gold[0].split())[:60]
                    if needle and needle in " ".join(chunk.split()):
                        located_ok += 1
            elif real:
                fn += 1
            elif pred:
                fp += 1
            else:
                tn += 1
        n_pos, n_neg = tp + fn, tn + fp
        if not n_pos or not n_neg:
            continue
        sensitivity, specificity = tp / n_pos, tn / n_neg
        rows.append(dict(
            category=cat, n=n_pos + n_neg, positives=n_pos,
            floor=100 * max(n_pos, n_neg) / (n_pos + n_neg),
            accuracy=100 * (tp + tn) / (n_pos + n_neg),
            balanced=100 * (sensitivity + specificity) / 2,
            recall=100 * sensitivity, specificity=100 * specificity,
            located_pct=100 * located_ok / located_n if located_n else None))
    return rows


def main(corpus_path, clauses_path):
    data, categories = load_data(corpus_path, clauses_path)
    train, val, test = split_by_contract(data)
    print(f"contracts {len(data)}  train {len(train)}  val {len(val)}  test {len(test)}")
    print(f"presence categories: {len(categories)}\n")

    cues = learn_cues(train, categories)
    cache = {}
    thresholds, uncalibrated = calibrate(val, categories, cues, cache)
    rows = evaluate(test, categories, cues, thresholds, cache, uncalibrated)

    rows.sort(key=lambda r: r["balanced"] - 50, reverse=True)
    print(f"{'category':36}{'n':>4}{'n_pos':>5}{'floor':>7}{'exact':>7}"
          f"{'balanc':>8}{'recall':>8}{'located_pct':>7}")
    for r in rows:
        ub = f"{r['located_pct']:.0f}%" if r["located_pct"] is not None else "-"
        print(f"{r['category']:36}{r['n']:>4}{r['positives']:>5}{r['floor']:>6.0f}%"
              f"{r['accuracy']:>6.0f}%{r['balanced']:>7.1f}%{r['recall']:>7.0f}%{ub:>7}")

    bal = sum(r["balanced"] for r in rows) / len(rows)
    above = sum(1 for r in rows if r["balanced"] > 55)
    print(f"\nmean balanced accuracy : {bal:.1f}%   (chance is 50%)")
    print(f"categories above 55%: {above} of {len(rows)}")
    if uncalibrated:
        print(f"\nNOT CALIBRATABLE ({len(uncalibrated)}): fewer than "
              f"{MIN_TO_CALIBRATE} positives in validation; the threshold means "
              f"nothing.\n  " + ", ".join(sorted(uncalibrated)))
        print("  These go straight to human review: they are so rare that "
              "checking them by hand costs little.")
    Path("retrieval_model.json").write_text(
        json.dumps(dict(thresholds=thresholds, cues=cues, test=rows),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return rows

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
