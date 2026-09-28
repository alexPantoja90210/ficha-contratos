#!/usr/bin/env python3
"""AWS Lambda entry point: contract text in, the eight-row sheet out.

The same sheet.py that produces the measured 76.3%, behind a Function URL.
Nothing is added to the model here and nothing is re-tuned: this module only
validates the request, calls sheet(), and shapes the response.

Why there is no vector store, no embedding model and no LLM in this stack: the
sheet is rules plus term retrieval over the Python standard library, and it
answers in tens of milliseconds. Paying a per-token price and a per-hour index
to reproduce a number that is already measured would be a downgrade with a
monthly bill attached.

CORS is NOT set here. A Function URL configured with CORS adds those headers to
every response and answers the preflight itself without invoking this function.
Emitting them here as well sends "access-control-allow-origin" twice, and a
browser rejects a response carrying two values where one is allowed — which a
script never notices, because no HTTP client enforces CORS. Configure CORS on
the Function URL (see AWS-DEPLOY.md), or on whatever fronts this function.

Request   POST /            {"text": "<contract as plain text>"}
Response  200               {"rows": [...], "elapsed_ms": 17.2, "scope": {...}}
          GET  /            {"scope": {...}, "clauses": [...]}   no body needed
"""
import json
import time
from pathlib import Path

from sheet import sheet, IN_SCOPE, OUT_OF_SCOPE

HERE = Path(__file__).resolve().parent

# Lambda refuses a synchronous request over 6 MB before this code runs. The
# largest contract in CUAD is 330 KB, so this cap sits far below the platform
# limit and exists to reject a body that is not a contract at all.
MAX_CHARS = 1_000_000

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}

# Built once per container, not per request.
SCOPE_SUMMARY = {
    "in_scope": len(IN_SCOPE),
    "out_of_scope": len(OUT_OF_SCOPE),
    "total_categories": len(IN_SCOPE) + len(OUT_OF_SCOPE),
    "criterion": {
        "rule": "end-to-end accuracy >= 65%",
        "presence": "balanced accuracy >= 70% AND recall >= 70%",
        "both": "must beat the naive parse",
    },
    "measured": {
        "rows_correct_pct": 76.3,
        "held_out_contracts": 101,
        "naive_parse_pct": 46,
        "trivial_floor_pct": 79.7,
    },
}
CLAUSES = [
    {"category": r["category"], "engine": r["engine"],
     "measure": r["measure"], "naive": r.get("naive")}
    for r in IN_SCOPE
]


def _reply(status, payload):
    return {"statusCode": status, "headers": JSON_HEADERS,
            "body": json.dumps(payload, ensure_ascii=False)}


def _text_from(event):
    """The contract text, or a (status, message) pair explaining the refusal."""
    raw = event.get("body")
    if not raw:
        return None, (400, "empty body: POST {\"text\": \"<contract>\"}")
    if event.get("isBase64Encoded"):
        import base64
        try:
            raw = base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            return None, (400, "body is not valid base64")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None, (400, "body is not valid JSON")
    if not isinstance(data, dict):
        return None, (400, "body must be a JSON object")
    text = data.get("text")
    if not isinstance(text, str):
        return None, (400, "field \"text\" is required and must be a string")
    if not text.strip():
        return None, (400, "field \"text\" is empty")
    if len(text) > MAX_CHARS:
        return None, (413, f"text is {len(text)} characters; the cap is {MAX_CHARS}")
    return text, None


def handler(event, context):
    method = (event.get("requestContext", {})
                   .get("http", {})
                   .get("method", "POST")).upper()

    # A preflight only reaches here when nothing in front of the function is
    # configured for CORS. Answering it with no CORS headers is honest: the
    # browser will refuse, and the refusal points at the missing configuration
    # rather than at this code.
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {}, "body": ""}

    if method == "GET":
        return _reply(200, {"scope": SCOPE_SUMMARY, "clauses": CLAUSES})

    if method != "POST":
        return _reply(405, {"error": f"{method} not allowed"})

    text, refusal = _text_from(event)
    if refusal:
        status, message = refusal
        return _reply(status, {"error": message})

    started = time.perf_counter()
    try:
        rows = sheet(text)
    except Exception as exc:                       # noqa: BLE001
        # The contract text never goes into the log. A sheet that fails on a
        # real document is a defect to reproduce from its size and its type,
        # not from a copy of somebody's agreement sitting in CloudWatch.
        print(f"sheet failed on {len(text)} characters: {type(exc).__name__}")
        return _reply(500, {"error": "the sheet could not be produced"})
    elapsed_ms = (time.perf_counter() - started) * 1000

    closes = sum(1 for r in rows if r["state"] in ("found", "absent"))
    to_review = sum(1 for r in rows if r["state"] in ("review", "absent_review"))

    return _reply(200, {
        "rows": rows,
        "elapsed_ms": round(elapsed_ms, 1),
        "characters": len(text),
        "summary": {"closes_alone": closes, "to_review": to_review,
                    "total": len(rows)},
        "scope": SCOPE_SUMMARY,
    })


# Local check: python lambda_function.py ../cuad/contracts.json 433
if __name__ == "__main__":
    import sys
    corpus = sys.argv[1] if len(sys.argv) > 1 else "../cuad/contracts.json"
    index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    contracts = json.loads(Path(corpus).read_text(encoding="utf-8"))
    name = sorted(contracts)[index]
    event = {"requestContext": {"http": {"method": "POST"}},
             "body": json.dumps({"text": contracts[name]})}
    out = handler(event, None)
    print(out["statusCode"])
    print(json.dumps(json.loads(out["body"]), indent=2, ensure_ascii=False)[:1400])
