#!/usr/bin/env python3
"""Assigns each CUAD category to an extraction bucket.

Input:   category_descriptions.csv from the TheAtticusProject/cuad repository
Output:  categories.json  (consumed by the sheet)
         categories.csv   (for reading by eye)

The assignment is a design decision, not a measured result. Change it by editing
the tables at the top of this file.
"""
import csv, io, json, re, sys, collections
from pathlib import Path

# --- The decision. Edit here. --------------------------------------------
# rule      : the answer has a verifiable shape and sits in a predictable place
# hybrid    : retrieval locates the clause, the rule normalizes the value
# retrieval : a presence question; the system marks present/absent on its own
# human     : a presence question where a wrong "absent" is expensive;
#             the system proposes, a person confirms

RULE = {
    "Document Name": dict(
        where="First 2000 characters",
        pattern=r"(?im)^\s*([A-Z][A-Z \-&']{6,})\s*$|\b([A-Z][\w ]*?AGREEMENT)\b",
        validates="non-empty string", measured_pct=97.6, measured_of=510),
    # Moved to MODEL after measuring end to end: 86.4% with the paragraph
    # already located, 3.6% having to pull it out of the raw contract.
    "Parties (dropped from rule bucket)": dict(
        where="Opening paragraph",
        pattern=r"(?i)\b(?:by and between|between)\b(.{0,400}?)(?:\bwitnesseth\b|\brecitals\b|\n\n|\.\s+[A-Z])",
        validates="at least 2 entities", measured_pct=86.4, measured_of=509),
    "Agreement Date": dict(
        where="Opening paragraph",
        pattern=r"(?i)\bdated(?:\s+as\s+of)?\s+(.{0,40}?\d{4})",
        validates="parseable date", measured_pct=85.5, measured_of=463),
    "Effective Date": dict(
        where="Opening paragraph or definitions",
        pattern=r"(?i)\beffective\s+(?:date|as\s+of)\b[^.]{0,60}?((?:\d{1,2}/\d{1,2}/\d{2,4})|(?:[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}))",
        validates="parseable date", measured_pct=82.6, measured_of=357),
    "Governing Law": dict(
        where="Governing law clause",
        pattern=r"(?i)govern(?:ed|ing)\s+(?:by|law).{0,120}?\b(?:State|Commonwealth|Province|laws)\s+of\s+([A-Z][\w ]+)",
        validates="value inside the state/country gazetteer", measured_pct=95.1, measured_of=432),
}

HYBRID = {
    "Notice Period to Terminate Renewal": dict(
        locates="renewal termination clause",
        normalizes="term nearest to 'notice'/'non-renewal', unit days",
        validates="number + unit",
        measured_pct=87.0, measured_of=100),
}

# Measured against the 510 contracts in master_clauses.csv. They do not close
# on their own.
DERIVED_OR_WEAK = {
    "Expiration Date": dict(
        note="Not written down: it is computed from Effective Date + the term. "
             "The error compounds on top of Effective Date (82.6%).",
        measured_pct=34.4, measured_of=326),
    "Renewal Term": dict(
        note="Multi-valued answers ('perpetual', '7/22/2019; 7/22/2022') and "
             "competing terms inside the same paragraph.",
        measured_pct=61.3, measured_of=163),
}

# Yes/No questions where a wrong "absent" changes the economics of the deal
# or stalls the transaction -> never closed without a person.
HUMAN = {
    "Cap on Liability", "Uncapped Liability", "Liquidated Damages",
    "IP Ownership Assignment", "Joint IP Ownership", "Source Code Escrow",
    "Change of Control", "Anti-Assignment", "Non-Compete", "Exclusivity",
    "Most Favored Nation", "Minimum Commitment",
} | set(DERIVED_OR_WEAK)

# Categories where the rule was measured and lost: here a model earns its hour.
MODEL = {
    "Parties": dict(
        note="The entities come tangled up with addresses, corporate "
             "descriptors and aliases. Rule: 3.6% end to end. A model reading "
             "the first page resolves this without effort.",
        measured_pct=3.6, measured_of=497),
}
# --------------------------------------------------------------------------

def strip_prefix(value: str) -> str:
    return re.sub(r"^[A-Za-z ()incl.]+:\s*", "", value).strip()

def bucket_of(name: str) -> str:
    if name in MODEL:  return "model"
    if name in RULE:   return "rule"
    if name in HYBRID: return "hybrid"
    if name in HUMAN:  return "human"
    return "retrieval"

def main(source_path: Path, dest_dir: Path) -> int:
    rows = list(csv.reader(io.StringIO(source_path.read_text(encoding="utf-8-sig"))))
    if not rows:
        print("empty csv", file=sys.stderr); return 1
    data = rows[1:]

    out = []
    for row in data:
        name = strip_prefix(row[0])
        bucket = bucket_of(name)
        record = {
            "category": name,
            "description": strip_prefix(row[1]),
            "cuad_format": strip_prefix(row[2]) or None,
            "cuad_group": strip_prefix(row[3]) if len(row) > 3 else None,
            "bucket": bucket,
            "closes_alone": bucket != "human",
        }
        record.update(RULE.get(name, {}))
        record.update(HYBRID.get(name, {}))
        record.update(DERIVED_OR_WEAK.get(name, {}))
        record.update(MODEL.get(name, {}))
        out.append(record)

    if len(out) != 41:
        print(f"warning: expected 41 categories, found {len(out)}", file=sys.stderr)

    missing = (set(RULE) | set(HYBRID) | HUMAN) - {r["category"] for r in out}
    if missing:
        print(f"warning: assigned names absent from the csv: {sorted(missing)}", file=sys.stderr)

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "categories.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    with (dest_dir / "categories.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "cuad_format", "cuad_group", "bucket", "closes_alone"])
        for r in out:
            w.writerow([r["category"], r["cuad_format"], r["cuad_group"],
                        r["bucket"], r["closes_alone"]])

    counts = collections.Counter(r["bucket"] for r in out)
    for k in ("rule", "hybrid", "model", "retrieval", "human"):
        print(f"{k:14} {counts[k]:2}")
    print(f"{'total':14} {sum(counts.values()):2}")
    print(f"close on their own  {sum(1 for r in out if r['closes_alone']):2}")
    return 0

if __name__ == "__main__":
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("category_descriptions.csv")
    dest_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    raise SystemExit(main(source_path, dest_dir))
