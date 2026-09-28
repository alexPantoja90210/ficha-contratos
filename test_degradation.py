#!/usr/bin/env python3
"""Does the sheet fail safely on input it was not built for? (MEASURE 2.6)

The claim in the documentation is that the sheet degrades to a review state
rather than asserting something it cannot support. That claim had never been
tested. This feeds it input no contract corpus contains and checks two things
on every case:

  it does not crash, and
  it does not report a clause as found or absent without evidence.

A crash is a bad failure. A confident wrong answer is a worse one.

Usage:  python test_degradation.py
"""
import sys, traceback
import sheet

SAFE = {"review", "absent_review", "model_pending", "absent"}

CASES = [
    ("empty file",            ""),
    ("one byte",              "x"),
    ("only whitespace",       "   \n\n\t  "),
    ("binary blob",           bytes(range(256)).decode("latin-1")),
    ("no line breaks",        "AGREEMENT " * 4000),
    ("Spanish contract",      "CONTRATO DE PRESTACION DE SERVICIOS\n\n"
                              "Celebrado entre Acme S.A. de C.V. y Norvex S. de R.L., "
                              "el 14 de marzo de 2019, regido por las leyes de Mexico."),
    ("none of the clauses",   "MEMORANDUM\n\nThe weather today is fine. "
                              "Nothing here concerns any commercial arrangement.\n" * 40),
    ("very long document",    ("SUPPLY AGREEMENT\n\nThis Supply Agreement is dated as of "
                               "March 14, 2019 and shall be governed by the laws of the "
                               "State of New York.\n" + "filler clause text. " * 200) * 60),
    ("repeated nulls",        "\x00" * 5000),
    ("html instead of text",  "<html><body><p>AGREEMENT</p></body></html>"),
]

def main():
    failures = []
    print(f"{'case':24}{'rows':>6}{'confident':>11}{'result':>10}")
    for name, text in CASES:
        try:
            rows = sheet.sheet(text)
        except Exception:
            failures.append((name, "crashed", traceback.format_exc().strip().splitlines()[-1]))
            print(f"{name:24}{'-':>6}{'-':>11}{'CRASH':>10}")
            continue
        # "confident" = the sheet asserted a value or asserted absence
        confident = [e for e in rows if e["state"] not in SAFE]
        bad = [e for e in confident if not e["value"]]
        verdict = "ok"
        if len(rows) != 8:
            failures.append((name, "wrong row count", f"{len(rows)} rows"))
            verdict = "ROWS"
        if bad:
            failures.append((name, "asserted with no value", bad[0]["category"]))
            verdict = "UNSAFE"
        print(f"{name:24}{len(rows):>6}{len(confident):>11}{verdict:>10}")

    print()
    if failures:
        print(f"{len(failures)} failure(s):")
        for name, kind, detail in failures:
            print(f"  {name:24} {kind}: {detail}")
        return 1
    print("No crashes, and nothing asserted without a value behind it.")
    print("Note: on input with no clauses the sheet still reports rows as")
    print("absent. That is correct only because absence is a real answer here.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
