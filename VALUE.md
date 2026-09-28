# Business value

Covers NIST AI RMF **MAP 1.4** (business value or context of business use).

**Read the assumptions as assumptions.** This project has no client, no ticket
volume and no cost data. What follows is a value model with its inputs named, of
the kind written to decide whether to fund a project, not a report of results.
Every assumption below is marked, and each one says what would replace it with a
measurement.

## Who it is for

Someone who reviews commercial contracts and is not the person who drafted them:
in-house counsel triaging inbound agreements, a procurement analyst checking what
a supplier sent back, a small firm without a contract-management system. The
common shape is a stack of contracts, a short list of things to check, and no
time.

## What it changes

The sheet does not replace reading a contract. It changes the *order* of reading
and it makes absence visible. The reviewer opens knowing which of eight clauses
were found, which were not, and which need their eyes first.

## The model

| Input | Assumption | What would replace it |
|---|---|---|
| Time to locate eight clauses by hand | 20–40 min per contract, unassisted | Time five reviewers on ten contracts each |
| Time with the sheet | 10–20 min: confirm the found rows, read the flagged ones | The same test, with the sheet |
| Contracts per reviewer per week | 5–15 | The client's own volume |
| Cost of a missed clause | Dominated by one case: a liability cap reported absent when present | The client's claims history |

On those assumptions the sheet returns a few hours a week per reviewer. That is
a real saving and a modest one, and it is not the reason to build it.

## Where the value actually sits

**Absence is the product.** Finding a clause is the easy half; a reviewer would
have found it. Being told *"this contract does not limit your liability"* is the
half that changes a decision, and it is the half no keyword search can offer,
because an empty result set is not evidence of absence.

That is why recall sits in the scope criterion and why two clauses were dropped
for losing to "not present". It is also where the risk concentrates: measured on
the held-out split, Cap on Liability is reported absent when present in 3
contracts out of 101.

## What it is not worth

- **Not worth deploying unattended.** Roughly one row in four is wrong.
- **Not worth selling as review.** It is triage.
- **Not worth its infrastructure cost, because it has none.** No model, no API
  keys, no database, no per-seat licence, under a second per contract on a
  laptop. Any comparison against a paid contract-analysis product has to start
  there, and any comparison on clause coverage has to start with eight versus
  forty-one.

## The honest version

The measured claim is narrow: eight clauses, 76.3% of rows correct, 30 points
above what the obvious parse achieves, on contracts the system never saw. Whether
that is worth money depends on volume and on what a missed clause costs — two
numbers this project does not have and a client would.
