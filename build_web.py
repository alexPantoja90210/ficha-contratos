#!/usr/bin/env python3
"""Bakes the Function URL into a deployable copy of the page.

web/index.html ships with ENDPOINT empty, which makes the page show a field to
type the URL into. That field is a development affordance: it depends on browser
storage to survive a reload, and on an S3 website endpoint that storage is not
dependable. A deployed page should not ask its reader for configuration.

The URL is NOT committed. A Function URL with auth type NONE is callable by
anyone who has it, and this repository is public: an endpoint in it is an open
invitation to spend somebody else's request allowance. So the deployable copy is
built here and ignored by git, which is where deployment configuration belongs.

The output is written as web/deploy/index.html, already carrying the name S3
needs for the index document: the console names an object after the file it is
given, so a file called anything else uploads as an object nobody serves.

Usage:  python build_web.py https://xxxx.lambda-url.us-east-1.on.aws/
        -> web/deploy/index.html, the file to upload
"""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "web" / "index.html"
OUT = HERE / "web" / "deploy" / "index.html"

VALID = re.compile(r"^https://[A-Za-z0-9.\-]+/?$")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    url = sys.argv[1].strip()
    if not VALID.match(url):
        sys.exit(f"that does not look like an endpoint URL: {url!r}")
    if not url.endswith("/"):
        url += "/"

    html = SRC.read_text(encoding="utf-8")
    old = 'const ENDPOINT = "";'
    if html.count(old) != 1:
        sys.exit(f"could not find {old!r} in {SRC.name} exactly once")
    html = html.replace(old, f'const ENDPOINT = "{url}";')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(HERE)}  {OUT.stat().st_size / 1024:.1f} KB")
    print(f"endpoint baked in: {url}")
    print("The field is hidden in this copy; the reader is not asked to configure it.")
    print("Not committed: the repository is public and this endpoint takes no auth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
