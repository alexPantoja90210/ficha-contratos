#!/usr/bin/env python3
"""Builds the demo page: picks which contracts it shows and rebuilds the HTML.

The three defaults are held_out examples chosen because between them they cover the
interesting cases: one has Governing Law at the 1% mark of the document and another
has the same clause at 85%.

  python build_page.py                          # the three defaults
  python build_page.py --list                   # available indices and names
  python build_page.py --add 12 --remove VEONEER
  python build_page.py --contracts 480 433 465  # replaces the whole list

A contract is named by its index (alphabetical order of the corpus) or by any piece
of its name, as long as that piece identifies exactly one.

There is no state between runs: every run starts from the default list and applies
that run's flags. Publishing is a separate step — the file lands on disk and the
page carries a build stamp so it is always clear which build is live.
"""
import argparse, datetime, json, os, re, sys
from pathlib import Path

# The project reads its data with relative paths (categories.json,
# retrieval_model.json, template.html), so the script plants itself in its own
# folder and can be invoked from anywhere.
HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))

import measure_rules as R, retrieval as REC
from locator import TextLocator, key_of
from presence import PresenceDetector
from scope import decide, NAIVE
import sheet as F

DEFAULT_CONTRACTS = [
    "VirtuosoSurgicalInc_20191227_1-A_EX1A-6 MAT CTRCT_11933379_EX1A-6 MAT CTRCT_License Agreement",
    "TALCOTTRESOLUTIONLIFEINSURANCECO-SEPARATEACCOUNTTWELVE_04_30_2020-EX-99.8(L)-SERVICE AGREEMENT",
    "VEONEER,INC_02_21_2020-EX-10.11-JOINT VENTURE AGREEMENT",
]

# One single figure per category across the whole page: the one from the
# held_out partition (measure_sheet.py). Never the one over all 510, so that two
# numbers for the same thing are never published.
TESTED = {"Governing Law": 90, "Cap on Liability": 86, "License Grant": 76,
          "Insurance": 76, "Agreement Date": 74, "Audit Rights": 73,
          "Effective Date": 67, "Document Name": 66}

MAX_TEXT = 60000          # how much of the contract gets embedded
DATE_RE = re.compile(
    r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{1,2}\s*(?:st|nd|rd|th|t\s*h)?\s+day\s+of\s+[A-Za-z]+,?\s*\d{4})")


# The corpus lives outside the repository (27 MB). It is looked for where it
# usually sits, rather than demanding the path be typed on every run.
CORPUS_CANDIDATES = [
    Path("contracts.json"),
    HERE / "contracts.json",
    HERE.parent / "cuad" / "contracts.json",
    Path("C:/dev/cuad/contracts.json"),
    Path.home() / "dev" / "cuad" / "contracts.json",
]

def default_corpus():
    for c in CORPUS_CANDIDATES:
        if c.is_file():
            return str(c)
    return None


def resolve_one(clave_usuario, names):
    """Index or piece of a name -> full name. Fails if ambiguous."""
    s = str(clave_usuario)
    if s.isdigit():
        i = int(s)
        if not 0 <= i < len(names):
            sys.exit(f"index out of range: {i} (there are {len(names)})")
        return names[i]
    coinciden = [n for n in names if s.lower() in n.lower()]
    if not coinciden:
        sys.exit(f"no contract matches {s!r}")
    if len(coinciden) > 1:
        print(f"{s!r} is ambiguous, it matches {len(coinciden)}:", file=sys.stderr)
        for n in coinciden[:6]:
            print("   ", n, file=sys.stderr)
        sys.exit(1)
    return coinciden[0]


def tested_for(cat):
    return next((v for k, v in TESTED.items() if key_of(k) == key_of(cat)), None)

def naive_for(cat):
    return next((v for k, v in NAIVE.items() if key_of(k) == key_of(cat)), None)


def rule_range(text, value, cat):
    """Only highlight text that really corresponds to the value shown."""
    if not value:
        return None
    if "date" in key_of(cat):
        for fr in TextLocator(text).fragments(cat):
            anchor_at = text.find(fr[:150])
            if anchor_at < 0:
                continue
            for m in DATE_RE.finditer(fr):
                if R.extract_date(m.group(0)) == value:
                    return [anchor_at + m.start(), anchor_at + m.end()]
        return None
    for cand in (value, value.split(";")[0].strip()):
        i = text.lower().find(cand.lower())
        if i >= 0:
            return [i, i + len(cand)]
    return None


def build_pages(nombres_elegidos, contracts, inside, det, cache):
    out = []
    for name in nombres_elegidos:
        text = contracts[name]
        length = len(text)
        rows = []
        for e in F.sheet(text):
            cat = e["category"]
            engine = next(d["engine"] for d in inside if key_of(d["category"]) == key_of(cat))
            span_range = passage = depth = None
            if engine == "rule":
                span_range = rule_range(text, e["value"], cat)
                if span_range:
                    depth = round(100 * span_range[0] / length)
            else:
                nd = next((c for c in det.cues if key_of(c) == key_of(cat)), None)
                if nd and e["state"] == "encontrada":
                    _, where = REC.score_windows(text, det.cues[nd], cache)
                    if where is not None:
                        passage = " ".join(text[where:where + 340].split())
                        depth = round(100 * where / length)
            # A rule row has no per-row signal, so it carries the clause's
            # measured accuracy. A presence row carries its calibrated value.
            conf = tested_for(cat) if engine == "rule" else e["confidence"]
            rows.append(dict(category=cat, engine=engine, state=e["state"],
                                 value=e["value"], confidence=conf,
                                 confidence_kind=e.get("confidence_kind"),
                                 clause_accuracy=tested_for(cat),
                                 naive=naive_for(cat), span_range=span_range,
                                 passage=passage, depth=depth))
        out.append(dict(name=name, text=text[:MAX_TEXT],
                           length=length, rows=rows))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=None,
                    help="contracts.json; if omitted, the usual paths are searched")
    ap.add_argument("--template", default="template.html")
    ap.add_argument("--out", default="page.html")
    ap.add_argument("--contracts", nargs="*", help="replaces the whole list")
    ap.add_argument("--add", nargs="*", default=[])
    ap.add_argument("--remove", nargs="*", default=[])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    path = a.corpus or default_corpus()
    if not path:
        print("contracts.json not found. Looked in:", file=sys.stderr)
        for c in CORPUS_CANDIDATES:
            print(f"   {c}", file=sys.stderr)
        sys.exit("Pass the path with --corpus, or rebuild it (see README).")
    if not Path(path).is_file():
        sys.exit(f"Does not exist: {path}")
    contracts = json.loads(Path(path).read_text(encoding="utf-8"))
    names = sorted(contracts)

    if a.list:
        held_out = int(len(names) * 0.8)
        for i, n in enumerate(names):
            marker = "held-out" if i >= held_out else "      "
            print(f"{i:>4} {marker}  {n[:92]}")
        return

    chosen = [resolve_one(c, names) for c in (a.contracts if a.contracts else DEFAULT_CONTRACTS)]
    for c in a.add:
        n = resolve_one(c, names)
        if n not in chosen:
            chosen.append(n)
    for c in a.remove:
        n = resolve_one(c, names)
        if n not in chosen:
            sys.exit(f"not in the list: {n}")
        chosen.remove(n)
    if not chosen:
        sys.exit("the page would have no contracts")

    inside, outside = decide()
    det = PresenceDetector()
    data = build_pages(chosen, contracts, inside, det, {})

    evid = [dict(cat=f["category"], pct=tested_for(f["category"]),
                 ing=naive_for(f["category"])) for f in inside]
    evid.sort(key=lambda r: -r["pct"])
    fuera_out = [dict(category=f["category"], engine=f["engine"],
                      measure=f["measure"], recall=f.get("recall")) for f in outside]

    # Stamp: the page says which build it came from. Without it there is no way
    # to tell whether what is published matches the last thing built.
    today = datetime.date.today().isoformat()
    stamp = f"Built {today} · {len(data)} contract" + ("s" if len(data) != 1 else "")

    html = Path(a.template).read_text(encoding="utf-8")
    html = html.replace("__STAMP__", stamp)
    for marker, value in (("__DATOS__", data), ("__EVID__", evid), ("__FUERA__", fuera_out)):
        if marker not in html:
            sys.exit(f"the template has no {marker}")
        html = html.replace(marker, json.dumps(value, ensure_ascii=False))
    Path(a.out).write_text(html, encoding="utf-8")

    print(f"{len(data)} contracts on the page:")
    for c in data:
        m = sum(1 for e in c["rows"] if e["span_range"])
        p = sum(1 for e in c["rows"] if e["passage"])
        print(f"  {c['name'][:62]:64} {m} highlights, {p} passages")
    abs_path = Path(a.out).resolve()
    print(f"\n{stamp}")
    print(f"{abs_path}  ({abs_path.stat().st_size//1024} KB)")
    print("\nThis is the final output. To make the published link show it,")
    print("ask Claude to publish page.html: the file lives on your disk,")
    print("publishing goes through Claude.")

if __name__ == "__main__":
    main()
