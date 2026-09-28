# Contract clause sheet — eight clauses, each with its number

Reads a contract as plain text and returns a **sheet of eight clauses**: what each
one says, which ones are missing, and **how confident that row is**.

No model, no API keys, no database. Under a second per contract, and the only
dependency is the Python standard library.

It also runs on AWS Lambda as a 34 KB package with nothing to vendor: see
[AWS-DEPLOY.md](AWS-DEPLOY.md).

```bash
python sheet.py contracts.json 433
```

```
[ok] Agreement Date        5/3/16          74%
[ok] Audit Rights          present         75%
[ok] Governing Law         Maryland        92%
[ok] License Grant         present         77%
[?]  Cap on Liability      review          84%
[  ] Warranty Duration     not present     76%
```

## How well it works

Measured on **101 contracts the system never saw** — the held-out split of
[CUAD](https://github.com/TheAtticusProject/cuad), 510 commercial contracts
annotated by attorneys — over 950 judgeable rows:

| | |
|---|---:|
| Rows correct | **76.3%** |
| Gain over a naive parse | **+30 points** |
| Sheets with 80% or more correct | 47% |
| Sheets without a single error | 16% |

Per category, against the naive parse it has to beat:

| Clause | Engine | Naive | This |
|---|---|---:|---:|
| Governing Law | rule | 38% | **90%** |
| Cap on Liability | presence | 42% | **86%** |
| License Grant | presence | 55% | 76% |
| Insurance | presence | 65% | 76% |
| Agreement Date | rule | 53% | 74% |
| Audit Rights | presence | 56% | 73% |
| Effective Date | rule | 50% | 67% |
| Document Name | rule | 5% | **66%** |

The naive parse is what anyone would write in an afternoon: the first line as the
title, the first date in the document, the first state named, and "not present"
for every yes/no question. `baseline_naive.py` computes it, and every claim here
is measured against it.

The two rows that look most trivial on screen are where the naive parse collapses.
The first line of a contract is almost never the title — it is `Exhibit 10.4`,
`EXECUTION COPY`, a page number. And the first state named is almost never the
governing law; it is a mailing address or a Delaware incorporation.

## Why eight clauses and not forty-one

CUAD defines 41 categories. The other 33 **did not make the cut**, and the cut was
written before looking at any results (`scope.py`):

- rule-based: end-to-end accuracy ≥ 65%
- presence: balanced accuracy ≥ 70% **and** recall ≥ 70%
- both: must beat the naive parse

Recall is in the criterion on purpose. A category that detects well but misses the
ones that are there cannot assert absence — and a sheet that cannot say "not
present" is useless for reviewing a contract.

Two categories were dropped by the last condition alone. *Warranty Duration* and
*No-Solicit of Employees* had balanced accuracy of 76% and 75.6% and passed the
first two rules, but answering "not present" every time scores 83% and 90% on
those two. The product lost by 7 and 10 points.

`python scope.py` prints all 41 with their numbers, in and out, so the decision can
be argued with rather than taken on faith.

## Two engines

| | |
|---|---|
| `locator.py` + rules | 4 typed categories: title, dates, governing law |
| `retrieval.py` | 4 presence categories, via learned discriminative terms |

The split was not a hunch. Each category was measured on both halves of the problem
— **locating** the clause and **normalizing** the value — and assigned to whichever
engine won.

*Governing Law* sits at the 84% depth mark of the median contract. A reader that
truncates to 8,000 characters sees it in 8% of cases; a regular expression that
scans the whole document resolves it at 90%. *Parties*, which looked easiest
because it sits in the opening paragraph, measured 5.8% end-to-end and was dropped:
that is where a model earns its hour.

## Measurement rules

These are wired into the code, not good intentions:

1. **No accuracy averaged across categories.** A detector that always answers "not
   present" scores 79.7% on this corpus. `trivial_floor.py` computes, per category,
   the floor a result has to clear before it means anything.
2. **The train/val/test split is by contract, never by question.** Every contract is
   asked all 41 questions; splitting questions at random would put the same text on
   both sides of the line.
3. **Term ties are broken on the term itself.** Python randomizes string hashing per
   process; without this the top-40 cutoff lands differently on every run and the
   project prints a different number each time.
4. **A category without enough positives to calibrate is not published.** It is
   marked uncalibratable and routed to human review.

## Scope and limits

This is not legal advice. It locates clauses and flags absences so a person can read
them; it does not judge whether a clause is favourable.

A perfect sheet is rare: 16% come out with no errors at all. Six or seven correct
rows out of eight is the normal case.

For rule-based categories the sheet jumps to the exact paragraph. For presence
categories it shows the highest-scoring passage with no guarantee it is the clause —
location accuracy runs between 12% and 46% on the held-out split.

The corpus is commercial contracts in English under US law. Porting this to Spanish
contracts is a different project.

## Getting the corpus

The corpus is not in this repository (27 MB). Download CUAD v1 from
[Zenodo](https://zenodo.org/records/4595826), then build `contracts.json` as a map
from contract name to its full text:

```python
import json, pathlib
src = pathlib.Path("CUAD_v1/full_contract_txt")
out = {p.stem: p.read_text(encoding="utf-8", errors="replace") for p in src.glob("*.txt")}
pathlib.Path("contracts.json").write_text(json.dumps(out, ensure_ascii=False))
```

`master_clauses.csv`, the attorney answers used for every measurement here, is
included: CUAD is CC BY 4.0.

## Files

| | |
|---|---|
| `sheet.py` | the product: contract in, eight-row sheet out |
| `scope.py` | what is in and what is out, with the criterion and the numbers |
| `buckets.py` | assigns each of the 41 categories to an extraction bucket |
| `locator.py` | finds the clause inside the raw contract |
| `retrieval.py` | learns terms, calibrates thresholds, evaluates |
| `presence.py` | applies what was learned, with the honesty rules |
| `build_page.py` | rebuilds the demo page from a chosen set of contracts |
| `measure_sheet.py` | measures the whole sheet, row by row |
| `measure_e2e.py` | measures locating plus normalizing |
| `measure_rules.py` | measures normalizing alone |
| `trivial_floor.py` | the floor each category has to clear |
| `calibrate.py` | per-row confidence for presence clauses, and its calibration error |
| `measure_bias.py` | accuracy by agreement type and document length |
| `test_degradation.py` | does it fail safely on input it was not built for |
| `test_security.py` | backtracking, dependency surface, no network |
| `baseline_naive.py` | the parse that comes for free, as a comparison |
| `lambda_function.py` | AWS Lambda entry point: contract in, sheet out |
| `build_lambda.py` | builds the 34 KB deployment package, no dependencies |
| `web/index.html` | paste-a-contract page that calls the Function URL |
| `AWS-DEPLOY.md` | deploying it, what it costs, and how to tear it down |

## Measured against NIST AI RMF

This project was mapped against the NIST AI Risk Management Framework after it was
built. It meets most of the MEASURE function and none of GOVERN, which is what a
solo technical artifact should look like. See [NIST-AI-RMF.md](NIST-AI-RMF.md), and [ROADMAP.md](ROADMAP.md) for what it
would take to close the open items. [AITRT.md](AITRT.md) runs the same exercise
against an open risk taxonomy, which caught a calibration defect NIST left
implicit.
