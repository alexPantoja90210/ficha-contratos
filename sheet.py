#!/usr/bin/env python3
"""Clause sheet for one contract: eight clauses, present or absent.

Takes the FULL TEXT of a contract and returns eight rows with a state, a value,
the measured confidence for that row, and — only where it can be promised — where
the clause is.

Two engines behind one sheet:
  TextLocator       rules over the typed categories (title, dates, governing law)
  PresenceDetector  term retrieval over the presence categories

States
------
  found            resolved; the row closes on its own
  absent           not there, and the measured recall backs asserting it
  review           a candidate exists, or the category is expensive: a person looks
  absent_review    looks absent, but the detector does not see enough to say so
  model_pending    the rule was measured and lost; a model belongs here

Usage:  python sheet.py contracts.json [index]
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Same search as build_page.py: the corpus lives outside the repository.
CORPUS_CANDIDATES = [Path("contracts.json"), HERE / "contracts.json",
                     HERE.parent / "cuad" / "contracts.json",
                     Path("C:/dev/cuad/contracts.json")]

def default_corpus():
    for c in CORPUS_CANDIDATES:
        if c.is_file():
            return str(c)
    return None

import measure_rules as R
from locator import TextLocator, key_of
from text_rules import parties_from_text
from presence import PresenceDetector
from scope import decide

CONFIG = {c["category"]: c for c in
          json.loads(Path("categories.json").read_text(encoding="utf-8"))}
BY_KEY = {key_of(k): v for k, v in CONFIG.items()}

# El scope lo decide la medicion (ver scope.py), no el gusto.
DENTRO, FUERA = decide()
SCOPE = {key_of(f["category"]): f for f in DENTRO}

RULES = {
    "document name":                     (R.rule_name,     71.9),
    "governing law":                     (R.rule_law,        91.7),
    "agreement date":                    (R.rule_date,      73.6),
    "effective date":                    (R.rule_date,      68.0),
    "notice period to terminate renewal":(R.rule_notice,   61.2),
    "renewal term":                      (R.rule_renewal, 60.6),
    "parties":                           (parties_from_text,     5.8),
}
MIN_CONFIDENCE = 50.0

# el name difiere entre los dos archivos de CUAD
def equivalent(category, claves):
    k = key_of(category)
    return next((c for c in claves if key_of(c) == k), None)


def row_for(category, loc, det, text):
    cfg = BY_KEY.get(key_of(category), {})
    bucket_of = cfg.get("bucket", "retrieval")
    k = key_of(category)
    anchor_at = dict(category=category, bucket=bucket_of)

    # --- categories con regla ------------------------------------------------
    if k in RULES:
        regla, confidence = RULES[k]
        if confidence < MIN_CONFIDENCE:
            return {**anchor_at, "state": "model_pending", "value": None,
                    "text": None, "confidence": confidence, "confidence_kind": "clause", "start": None}
        frs = loc.fragments(category)
        value = regla(frs) if frs else None
        if not value:
            state = "absent" if bucket_of != "human" else "review"
            return {**anchor_at, "state": state, "value": None, "text": None,
                    "confidence": confidence, "confidence_kind": "clause", "start": None}
        return {**anchor_at,
                "state": "review" if bucket_of == "human" else "found",
                "value": value, "text": " ".join(frs[0].split())[:300],
                "confidence": confidence, "confidence_kind": "clause", "start": None}

    # --- presence categories --------------------------------------------
    detector_name = equivalent(category, det.cues)
    if detector_name is None:
        return {**anchor_at, "state": "review", "value": None, "text": None,
                "confidence": None, "confidence_kind": None, "start": None}

    state, conf, start = det.evaluate(detector_name, text)
    # An expensive category never closes on its own, however sure the detector is
    if bucket_of == "human" and state in ("found", "absent"):
        state = "review" if state == "found" else "absent_review"
    frag = " ".join(text[start:start + 400].split()) if start is not None else None
    return {**anchor_at, "state": state, "value": "present" if "found" in state
            else None, "text": frag, "confidence": conf,
            "confidence_kind": "row", "start": start}


def sheet(text, full=False):
    """full=True returns all 41; by default only the clauses in scope."""
    loc = TextLocator(text)
    det = PresenceDetector()
    cats = CONFIG if full else [c for c in CONFIG if key_of(c) in SCOPE]
    out = []
    for c in cats:
        e = row_for(c, loc, det, text)
        a = SCOPE.get(key_of(c))
        if a:
            e["engine"] = a["engine"]
            # A rule row has no per-row signal, so it carries the clause's
            # measured accuracy. A presence row keeps its calibrated value.
            if a["engine"] == "rule":
                e["confidence"] = a["measure"]
                e["confidence_kind"] = "clause"
            e["clause_accuracy"] = a["measure"]
        out.append(e)
    return out


SYMBOL = {"found": "[ok]", "absent": "[  ]", "review": "[?]",
           "absent_review": "[?-]", "model_pending": "[M]"}
LEGEND = {"absent": "not present",
           "review": "review",
           "absent_review": "do not see it; confirm",
           "model_pending": "the rule lost: a model belongs here"}

def print_sheet(f, titulo):
    print("=" * 78); print(titulo[:76]); print("=" * 78)
    ordered = {"found": 0, "review": 1, "absent_review": 2,
             "absent": 3, "model_pending": 4}
    for e in sorted(f, key=lambda e: (ordered[e["state"]], e["category"])):
        conf = f"{e['confidence']:.0f}%" if e["confidence"] else "  -"
        salto = " ->" if e["start"] is not None else "   "
        val = e["value"] or LEGEND.get(e["state"], "")
        print(f"  {SYMBOL[e['state']]:5}{e['category']:34}{str(val)[:26]:28}{conf:>5}{salto}")
    n = lambda *s: sum(1 for e in f if e["state"] in s)
    print("-" * 78)
    print(f"  close on their own {n('found','absent')}   "
          f"to review {n('review','absent_review')}   "
          f"pending {n('model_pending')}   total {len(f)}")
    print(f"  out of scope, with no measurement behind them: {len(FUERA)} categories")


def main(path, indice=0):
    contracts = json.loads(Path(path).read_text(encoding="utf-8"))
    name = sorted(contracts)[int(indice)]
    f = sheet(contracts[name])
    print_sheet(f, name)
    Path("ficha_ejemplo.json").write_text(
        json.dumps({"contract": name, "rows": f}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return f

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else default_corpus()
    if not path:
        sys.exit("contracts.json not found. Pass its path, or rebuild it (see README).")
    main(path, sys.argv[2] if len(sys.argv) > 2 else 0)
