#!/usr/bin/env python3
"""Builds the Lambda deployment package.

Only what the product needs at runtime goes in. The measurement scripts, the
tests and master_clauses.csv (4 MB of attorney answers) stay out: they are how
the numbers were produced, not how a sheet is produced.

The package has no dependencies to vendor, so there is no pip step, no layer
and no container image. That is a property of the design, not a shortcut.

Usage:  python build_lambda.py            -> sheet-lambda.zip
"""
import sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "sheet-lambda.zip"

# Imported, directly or transitively, by lambda_function.
CODE = [
    "lambda_function.py",
    "sheet.py",
    "locator.py",
    "presence.py",
    "retrieval.py",
    "scope.py",
    "measure_rules.py",
    "text_rules.py",
]
# Fitted parameters and the category table the sheet reads at import.
DATA = [
    "categories.json",
    "retrieval_model.json",
    "calibration.json",
]

def main():
    missing = [f for f in CODE + DATA if not (HERE / f).is_file()]
    if missing:
        sys.exit(f"missing from the repository: {', '.join(missing)}")

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in CODE + DATA:
            z.write(HERE / f, f)

    size = OUT.stat().st_size
    print(f"{OUT.name}  {size/1024:.0f} KB  ({len(CODE)} modules, {len(DATA)} data files)")
    print(f"Lambda's zipped limit is 50 MB; this uses {100*size/(50*1024*1024):.2f}% of it.")
    print("No third-party packages: nothing to vendor, no layer, no container image.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
