# Closing the MAP and MEASURE gaps

What [NIST-AI-RMF.md](NIST-AI-RMF.md) records as partial or unmet, and what it
would take to close each one. GOVERN is deliberately absent: it needs an
organization, not work.

The waves are ordered by what closes the gap, not by effort. Wave 1 is a script.
Wave 2 is a document. Wave 3 needs another person. Wave 4 is out of reach alone.

---

## Wave 1 — a script closes it

### MEASURE 2.11 · Fairness and bias evaluated — *not met*

The highest-value gap, and the one most likely to change the product.

CUAD contract names carry the agreement type, so 116 types are derivable with no
extra data. The held-out split has 6 types with 5 or more contracts: Distributor
(9), Sponsorship (7), Strategic Alliance (6), Franchise (5), Affiliate (5),
Supply (5).

**Build `measure_bias.py`:** accuracy per clause per contract type, plus accuracy
by document length quartile. Report the spread, not the mean.

The thing to watch for: a sheet that scores 76% overall but 50% on franchise
agreements is not a 76% product for a franchise lawyer. If the spread is wide,
contract type belongs in the scope criterion, and that is a product decision, not
a metric.

Counts are small — 5 to 9 contracts per type — so report intervals and resist
reading a 2-contract difference as a finding.

### MEASURE 2.6 · Fails safely — *partial*

**Build `test_degradation.py`:** feed an empty file, a 1-byte file, a 20 MB file,
a binary blob, a contract in Spanish, a contract with none of the eight clauses,
and text with no line breaks. Assert the sheet returns rows in a review state and
never crashes, never asserts a value it cannot support.

The claim today is that the system degrades to `review`. It has never been tested.

### MEASURE 2.7 · Security and resilience — *not met*

Two concrete risks, both testable:

1. **Catastrophic backtracking.** The locator and the rules use regular
   expressions with nested quantifiers over inputs up to 338,000 characters. A
   pathological contract could hang the process. Time every pattern against
   adversarial input and set a ceiling.
2. **Dependency surface.** Stdlib only, which is a real security property —
   assert it in a test so it stays true.

### MEASURE 2.10 · Privacy risk examined — *partial*

The claim is that nothing leaves the machine. **Verify it** rather than repeat
it: run the sheet with sockets disabled and assert it still works. Then write the
data-flow note: input stays in memory, no telemetry, no model endpoint, the only
file written is the page.

---

## Wave 2 — a document closes it

These are project-management artifacts, not code. They are the part of the
framework a PM owns.

| Subcategory | Outcome | What to write |
|---|---|---|
| **MAP 1.4** | Business value defined | Cost per contract reviewed today versus with the sheet; which of the eight clauses carry the value; what a wrong row costs |
| **MAP 1.5** | Risk tolerance documented | The thresholds in `scope.py` already are one. State them as a tolerance: what error rate is acceptable per clause and why |
| **MAP 5.1** | Impact likelihood and magnitude | One row per clause: how often it is wrong, what happens downstream when it is, who absorbs it |
| **MAP 4.2** | Internal risk controls | The honesty rules in `presence.py` are controls. Name them as such: no uncalibrated category decides alone, no absence without recall behind it, no jump without location accuracy |
| **MAP 3.4** | Operator proficiency | A short guide: what the states mean, what a user must verify, what the sheet will not tell them |

Wave 2 is a day of writing and it moves five subcategories. It is the cheapest
wave and the one most likely to be skipped.

---

## Wave 3 — another person closes it

### MEASURE 1.3 · An assessor who did not write the code — *not met*

The framework asks for someone who was not a front-line developer. One reviewer
is enough to satisfy it. Ask for two things: does the scope criterion hold up,
and does any measurement flatter the result.

### MAP 1.6 · Requirements elicited from relevant actors — *not met*

Two or three conversations with people who review contracts for a living. Not to
validate the build, but to find out which eight clauses they would have picked —
the current eight were chosen by what the measurement allowed, never by what a
reviewer needs.

This is the one most likely to change the product, and it costs only outreach.

---

## Wave 4 — out of reach alone

| Subcategory | Why |
|---|---|
| MEASURE 2.4 · Monitored in production | Needs a deployment and users |
| MAP 1.2 · Interdisciplinary actors, diversity | Needs a team |
| MAP 1.3 · Organizational mission | Needs an organization |
| All of GOVERN | Policies, accountability, training, legal review |

These stay open, and saying so is more useful than closing them on paper.

---

## Order

Wave 2 first: it is a day and it moves five subcategories. Then Wave 1's bias
evaluation, because it can still change what the product should cover. Wave 3
whenever the outreach lands.

After Waves 1 and 2, MAP and MEASURE would stand at roughly 13 of 17 and 11 of
14, with the remainder honestly out of reach. That is a defensible position for a
system built by one person, and it is a better claim than any number of passes.
