#!/usr/bin/env python3
"""The naive parse: what comes out anyway, without thinking about it.

It exists to answer one question: does the work of locating and calibrating add
anything over the obvious? If these figures match the product's, the product is not
worth it and we should say so.

The naive rules are what anyone would write in an afternoon:
  Document Name   the first non-empty line
  Agreement Date  the first date in the document
  Effective Date  the first date in the document
  Governing Law   the first state or country named in the document
  presence        "not present", always (the majority answer)
"""
import ast, csv, io, json, re, sys
from pathlib import Path

import measure_rules as R
from locator import key_of
from scope import decide


from measure_rules import JURISDICTIONS as GAZ

DATE_RE = re.compile(
    r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})")

def naive_title(t):
    for linea in t.splitlines():
        if linea.strip():
            return linea.strip()
    return None

def naive_date(t):
    m = DATE_RE.search(t)
    return R.extract_date(m.group(0)) if m else None

def naive_law(t):
    n_pos = [(t.lower().find(e.lower()), e) for e in GAZ]
    n_pos = [(i, e) for i, e in n_pos if i >= 0]
    return min(n_pos)[1] if n_pos else None

NAIVE_RULES = {
    "document name":  (naive_title, R.same_text),
    "agreement date": (naive_date,  R.same_date),
    "effective date": (naive_date,  R.same_date),
    "governing law":  (naive_law,    R.same_contains),
}

def column_for(row, cat):
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
            v = (row.get(c) or "").strip()
            try:
                v = ast.literal_eval(v) if v else []
            except (ValueError, SyntaxError):
                v = [v] if v else []
            return bool(v)

# lo que mide medir_ficha.py para el producto, sobre la misma particion
PRODUCT = {"Document Name": 66, "Agreement Date": 74, "Effective Date": 67,
            "Governing Law": 90, "Cap on Liability": 86, "License Grant": 76,
            "Warranty Duration": 76, "Insurance": 76,
            "No-Solicit of Employees": 80, "Audit Rights": 73}

def main(ruta_json, ruta_csv):
    contracts = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n
    held_out = set(sorted(contracts)[int(len(contracts) * 0.8):])
    inside, _ = decide()

    print(f"{'category':30}{'naive':>9}{'producto':>10}{'gana':>8}")
    total_i = total_p = n_cat = 0
    for f in inside:
        cat = f["category"]
        k = key_of(cat)
        ok_count = n = 0
        for row in rows:
            nom = stem(row["Filename"])
            text = contracts.get(nom)
            if text is None or nom not in held_out:
                continue
            if k in NAIVE_RULES:
                col = column_for(rows[0], cat)
                real = (row.get(col) or "").strip() if col else ""
                if not real or R.REDACTED.fullmatch(real):
                    continue
                regla, cmp_ = NAIVE_RULES[k]
                ok = cmp_(regla(text), real)
            else:
                real = has_span(row, cat)
                if real is None:
                    continue
                ok = (False == real)      # el naive dice "not present" siempre
            n += 1
            ok_count += ok
        pct = 100 * ok_count / n if n else 0
        prod = next(v for kk, v in PRODUCT.items() if key_of(kk) == k)
        total_i += pct; total_p += prod; n_cat += 1
        print(f"{cat:30}{pct:>8.0f}%{prod:>9}%{prod-pct:>+7.0f}")
    print(f"\n{'mean':30}{total_i/n_cat:>8.0f}%{total_p/n_cat:>9.0f}%"
          f"{(total_p-total_i)/n_cat:>+7.0f}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contracts.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
