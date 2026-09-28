#!/usr/bin/env python3
"""Security and privacy properties, asserted rather than claimed.

MEASURE 2.7 -- security and resilience
  1. Catastrophic backtracking. Every rule is a regular expression run over
     documents of up to 338,000 characters. A pattern with nested quantifiers
     can take exponential time on input crafted to trigger it, which hangs the
     process. Each pattern is timed against adversarial input.
  2. Dependency surface. The project imports nothing outside the standard
     library. That is a real security property, so it is asserted here and
     will break the test the day someone adds a dependency.

MEASURE 2.10 -- privacy
  3. No network. The claim is that no contract leaves the machine. Rather than
     repeat it, the sheet is run with the socket module disabled: if anything
     tried to open a connection it would raise, and the test would fail.

Usage:  python test_security.py
"""
import importlib, io, re, socket, sys, time
from pathlib import Path

# A pattern is only exposed to the size of input it actually receives.
# Those in locator and measure_rules scan whole contracts, up to 338,000
# characters in CUAD. The ones in text_rules see a captured party name, which
# strip_descriptor bounds. Timing a field-scale pattern against a whole
# document would report a risk the code does not carry.
DOC_BUDGET_MS   = 250
FIELD_BUDGET_MS = 50
DOC_SCALE   = ("locator", "measure_rules")
# Derived from what is actually on disk, so a new module in the repo is never
# reported as an external dependency just because this list went stale.
LOCAL = {p.stem for p in Path(".").glob("*.py")}

ADVERSARIAL = [
    "a" * 60000,
    ("laws of the State of " + "New " * 4000),
    ("dated as of " + "1 " * 20000),
    (" " * 50000 + "AGREEMENT"),
    ("(" * 5000 + ")" * 5000),
    ('x ("' * 8000),
    ("1 day of January, 2020 " * 3000),
]

def patterns():
    import measure_rules as R, locator as L, text_rules as T
    found = {}
    for mod in (R, L, T):
        for name in dir(mod):
            v = getattr(mod, name)
            if isinstance(v, re.Pattern):
                found[f"{mod.__name__}.{name}"] = v
            elif isinstance(v, (list, tuple)):
                for i, x in enumerate(v):
                    if isinstance(x, str) and len(x) > 4:
                        try:
                            found[f"{mod.__name__}.{name}[{i}]"] = re.compile(x, re.I)
                        except re.error:
                            pass
        for name in ("ANCHORS", "DATE_ANCHORS"):
            for k, pats in getattr(mod, name, {}).items():
                for i, pat in enumerate(pats):
                    found[f"{name}[{k}][{i}]"] = re.compile(pat, re.I)
    return found

def check_backtracking():
    print("1. Catastrophic backtracking")
    slow, n_doc, n_field = [], 0, 0
    for label, rx in sorted(patterns().items()):
        doc = label.startswith(DOC_SCALE) or label.startswith(("ANCHORS", "DATE_ANCHORS"))
        budget = DOC_BUDGET_MS if doc else FIELD_BUDGET_MS
        n_doc, n_field = n_doc + doc, n_field + (not doc)
        worst = 0.0
        for text in ADVERSARIAL:
            probe = text if doc else text[:200]
            t0 = time.perf_counter()
            try:
                rx.search(probe)
            except Exception:
                pass
            worst = max(worst, (time.perf_counter() - t0) * 1000)
        if worst > budget:
            slow.append((label, worst, budget))
    for label, ms, budget in sorted(slow, key=lambda x: -x[1]):
        print(f"   SLOW  {label:44}{ms:8.0f} ms  (budget {budget})")
    if not slow:
        print(f"   {n_doc} document-scale patterns under {DOC_BUDGET_MS} ms on "
              f"adversarial text")
        print(f"   {n_field} field-scale patterns under {FIELD_BUDGET_MS} ms on "
              f"bounded input")
        print("   text_rules.DESCRIPTOR is quadratic and is bounded by")
        print("   strip_descriptor, not by the pattern")
    return not slow

def check_dependencies():
    print("\n2. Dependency surface")
    external = set()
    for f in sorted(Path(".").glob("*.py")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
            if not m:
                continue
            root = m.group(1).split(".")[0]
            if root in LOCAL or root in sys.stdlib_module_names:
                continue
            external.add(f"{f.name}: {root}")
    if external:
        for e in sorted(external):
            print(f"   EXTERNAL  {e}")
    else:
        print("   standard library only")
    return not external

def check_no_network():
    print("\n3. No network during a run")
    blocked = []
    real = socket.socket
    def refuse(*a, **k):
        blocked.append(a)
        raise OSError("network disabled for this test")
    socket.socket = refuse
    try:
        import sheet
        importlib.reload(sheet)
        rows = sheet.sheet("SUPPLY AGREEMENT\n\nThis Supply Agreement is dated as of "
                           "March 14, 2019 and is governed by the laws of the State "
                           "of New York.\n" + "clause text. " * 400)
        ok = len(rows) == 8
        print(f"   sheet produced {len(rows)} rows with sockets disabled")
    except Exception as e:
        print(f"   FAILED: {e}")
        ok = False
    finally:
        socket.socket = real
    if blocked:
        print(f"   ATTEMPTED {len(blocked)} connection(s)")
    else:
        print("   no connection attempted")
    return ok and not blocked

if __name__ == "__main__":
    results = [check_backtracking(), check_dependencies(), check_no_network()]
    print()
    print("all properties hold" if all(results) else "SOME PROPERTIES DO NOT HOLD")
    sys.exit(0 if all(results) else 1)
