#!/usr/bin/env python3
"""Checks that a deployed Function URL returns what sheet.py returns locally.

Deploying is not a claim until somebody compares the two. This posts every
held-out contract to the endpoint and diffs the response against sheet.sheet()
run in this process, row by row and field by field. It also exercises the
refusal paths against the live endpoint, because an endpoint that accepts
anything is a different product from the one that was measured.

Standard library only, like everything else here.

Usage:  python verify_deployment.py https://xxxx.lambda-url.us-east-1.on.aws/
        python verify_deployment.py <url> --limit 20        (a quick pass)
"""
import argparse, json, statistics, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sheet import sheet                                    # noqa: E402

CORPUS_CANDIDATES = [Path("contracts.json"), HERE / "contracts.json",
                     HERE.parent / "cuad" / "contracts.json",
                     Path("C:/dev/cuad/contracts.json")]
TIMEOUT = 30


def call(url, payload=None, method=None, raw=None, origin=None):
    """-> (status, parsed body or raw text, elapsed ms, response headers)"""
    data = raw if raw is not None else (
        json.dumps(payload).encode("utf-8") if payload is not None else None)
    headers = {"content-type": "application/json"}
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(
        url, data=data, method=method or ("POST" if data is not None else "GET"),
        headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body, status, got = r.read().decode("utf-8"), r.status, r.headers
    except urllib.error.HTTPError as e:
        body, status, got = e.read().decode("utf-8"), e.code, e.headers
    ms = (time.perf_counter() - started) * 1000
    try:
        return status, json.loads(body), ms, got
    except ValueError:
        return status, body, ms, got


def check_cors(url):
    """A browser is the only client that enforces CORS. This is that check.

    A response carrying "access-control-allow-origin" twice is rejected by every
    browser and by no script, so a deployment can pass every other test here and
    still be unusable from a page. It happens when the function emits the header
    AND whatever fronts it adds the same one.
    """
    print("CORS, as a browser would see it")
    origin = "http://example.invalid"
    ok = True

    status, _, _, h = call(url, payload={"text": "AGREEMENT"}, origin=origin)
    allow = h.get_all("access-control-allow-origin") or []
    if len(allow) == 1:
        print(f"  allow-origin on a POST      {allow[0]!r}   ok")
    elif not allow:
        print("  allow-origin on a POST      MISSING   a browser will refuse")
        ok = False
    else:
        print(f"  allow-origin on a POST      SENT {len(allow)} TIMES {allow}")
        print("      A browser rejects a response with more than one value here.")
        print("      Configure CORS in one place only: the function or the")
        print("      Function URL, never both.")
        ok = False

    status, _, _, h = call(url, method="OPTIONS", raw=b"", origin=origin)
    pre = h.get_all("access-control-allow-origin") or []
    methods = (h.get("access-control-allow-methods") or "").upper()
    good_pre = status in (200, 204) and len(pre) == 1 and "POST" in methods
    print(f"  preflight                   {status}, allow-origin x{len(pre)}, "
          f"methods {methods or '(none)'}   {'ok' if good_pre else 'PROBLEM'}")
    ok = ok and good_pre
    print()
    return ok


def default_corpus():
    for c in CORPUS_CANDIDATES:
        if c.is_file():
            return c
    return None


def check_refusals(url):
    """The endpoint is public. What it rejects is part of the product."""
    cases = [
        ("empty body",         400, dict(raw=b"")),
        ("not JSON",           400, dict(raw=b"AGREEMENT between A and B")),
        ("JSON array",         400, dict(raw=b"[1,2,3]")),
        ("missing text",       400, dict(payload={"contract": "x"})),
        ("text not a string",  400, dict(payload={"text": 42})),
        ("text empty",         400, dict(payload={"text": "   "})),
        ("text oversize",      413, dict(payload={"text": "a" * 1_000_001})),
        # 405 comes from the handler. A bare local stub may answer 501 first,
        # because it never routes the method through. Against a real Function
        # URL the request reaches the handler and 405 is what it returns.
        ("method not allowed", 405, dict(method="DELETE", raw=b"")),
    ]
    print("refusal paths")
    ok = 0
    for name, expected, kw in cases:
        status, body, _, _ = call(url, **kw)
        good = status == expected
        ok += good
        msg = body.get("error", "") if isinstance(body, dict) else str(body)[:48]
        print(f"  {name:20}{status:>5} (want {expected})  "
              f"{'ok' if good else 'MISMATCH':9}{str(msg)[:46]}")
    print(f"  {ok}/{len(cases)} as specified\n")
    return ok == len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--limit", type=int, default=0,
                    help="check only the first N held-out contracts")
    a = ap.parse_args()
    url = a.url if a.url.endswith("/") else a.url + "/"

    corpus = Path(a.corpus) if a.corpus else default_corpus()
    if not corpus or not corpus.is_file():
        sys.exit("contracts.json not found. Pass --corpus with its path.")

    print(f"endpoint {url}\ncorpus   {corpus}\n")

    status, body, ms, _ = call(url)
    if status != 200 or not isinstance(body, dict) or "scope" not in body:
        sys.exit(f"GET returned {status}: {str(body)[:300]}")
    s = body["scope"]
    print(f"GET  {status}  {ms:.0f} ms")
    print(f"  in scope {s['in_scope']} of {s['total_categories']}   "
          f"measured {s['measured']['rows_correct_pct']}%   "
          f"naive {s['measured']['naive_parse_pct']}%\n")

    cors_ok = check_cors(url)
    refusals_ok = check_refusals(url)

    contracts = json.loads(corpus.read_text(encoding="utf-8"))
    names = sorted(contracts)
    held_out = names[int(len(names) * 0.8):]
    if a.limit:
        held_out = held_out[:a.limit]

    print(f"comparing {len(held_out)} held-out contracts against sheet.sheet()")
    same = 0
    diffs, times, states = [], [], {}
    for i, name in enumerate(held_out, 1):
        text = contracts[name]
        status, body, ms, _ = call(url, payload={"text": text})
        if status != 200 or not isinstance(body, dict):
            diffs.append((name, f"HTTP {status}: {str(body)[:120]}"))
            continue
        times.append(ms)
        for r in body["rows"]:
            states[r["state"]] = states.get(r["state"], 0) + 1
        local = sheet(text)
        if body["rows"] == local:
            same += 1
        else:
            for remote_row, local_row in zip(body["rows"], local):
                if remote_row != local_row:
                    changed = {k for k in local_row
                               if remote_row.get(k) != local_row.get(k)}
                    diffs.append((name, f"{local_row['category']}: {sorted(changed)}"))
                    break
        if i % 20 == 0:
            print(f"  {i}/{len(held_out)}")

    times.sort()
    print(f"\nrows identical to local: {same}/{len(held_out)}")
    if times:
        print(f"round trip: median {statistics.median(times):.0f} ms   "
              f"p95 {times[int(len(times) * .95) - 1]:.0f} ms   max {times[-1]:.0f} ms")
    print(f"states returned: {states}")
    if diffs:
        print(f"\n{len(diffs)} DIFFERENCES:")
        for name, what in diffs[:12]:
            print(f"  {name[:56]:58}{what}")
    print()
    if same == len(held_out) and refusals_ok and cors_ok and not diffs:
        print("The deployed endpoint returns exactly what sheet.py returns locally.")
        print("The published 76.3% describes this endpoint, not only the laptop.")
        return 0
    print("The deployment does NOT match local output. The figures on the page")
    print("describe sheet.py, so they do not describe this endpoint until it does.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
