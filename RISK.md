# Risk tolerance, controls and impact

Covers NIST AI RMF **MAP 1.5** (risk tolerance), **MAP 4.2** (internal risk
controls) and **MAP 5.1** (impact likelihood and magnitude). Every rate here is
measured on the 101 held-out contracts, not estimated.

---

## 1. Risk tolerance (MAP 1.5)

The tolerance is already executable — it lives in `scope.py` and decides what
ships. Stated plainly:

| Rule | Threshold | Why this number |
|---|---|---|
| Rule-based clause | end-to-end accuracy ≥ 65% | Below this the reviewer stops trusting the row and reads the clause anyway, so the row costs attention and returns nothing |
| Presence clause | balanced accuracy ≥ 70% | Plain accuracy is uninformative here: always answering "not present" scores 79.7% on this corpus |
| Presence clause | recall ≥ 70% | A clause that cannot be found cannot be declared absent, and a sheet that cannot say "not present" is useless for review |
| Every clause | must beat the naive parse | A row that loses to the first line, the first date or "not present" is worse than doing nothing |

**What this tolerance accepts.** Roughly one row in four is wrong. That is
tolerable only because the sheet is a reading aid, never the reviewer of record,
and because the errors fall mostly on the cheap side (section 3).

**What it refuses.** Two clauses that passed the first three rules were dropped
by the fourth. Warranty Duration and No-Solicit of Employees had balanced
accuracy of 76% and 75.6% and still lost to "not present" by 7 and 10 points.

**Not covered.** This is a system-level tolerance set by one person. It is not an
organizational risk appetite, and no one has signed it.

---

## 2. Internal risk controls (MAP 4.2)

Controls that exist in code, each with the failure it prevents.

| Control | Where | Prevents |
|---|---|---|
| Uncalibrated categories never decide alone | `presence.py` | A threshold fitted on fewer than 5 positives producing a detector that answers "yes" to everything |
| Absence asserted only when recall supports it | `presence.py` | Reporting "not present" from a detector that misses half of what is there |
| A jump into the document only where location was accurate | `presence.py` | Sending a reader to the wrong paragraph, which is worse than offering no jump |
| A title must be mostly letters and hold a real word | `measure_rules.looks_like_title` | Asserting control characters or an HTML fragment as a document name |
| Party-name descriptor bounded to 200 characters | `text_rules.strip_descriptor` | A quadratic pattern reached with a whole contract |
| Term ties broken on the term itself | `retrieval.py`, `measure_rules.py` | A figure that changes between runs of identical code |
| Split by contract, never by question | `retrieval.py` | The same contract text on both sides of the train/test line |
| Redacted gold answers excluded | `measure_rules.REDACTED` | Scoring against an answer the corpus withheld |

**Third-party risk.** One dependency: the CUAD corpus, CC BY 4.0, attributed.
No runtime dependency outside the Python standard library, asserted by
`test_security.py`. No network call is made, asserted by the same test.

---

## 3. Impact: how often, how bad, who absorbs it (MAP 5.1)

Measured on the held-out split. For presence clauses the error is split into the
two directions, because they do not cost the same.

| Clause | n | Wrong | False absent | False present | Who absorbs it |
|---|---:|---:|---:|---:|---|
| Document Name | 101 | 34 | — | — | Reader sees a wrong title. All 34 errors are a confident wrong value, never a blank |
| Audit Rights | 101 | 27 | 10 (10%) | 17 (17%) | Mostly a wasted reading |
| License Grant | 101 | 24 | 6 (6%) | 18 (18%) | Mostly a wasted reading |
| Insurance | 101 | 24 | 9 (9%) | 15 (15%) | Mostly a wasted reading |
| Agreement Date | 89 | 23 | — | — | 9 wrong values, 14 blanks. A blank is safe; it shows as needing review |
| Effective Date | 70 | 23 | — | — | 12 wrong values, 11 blanks |
| Cap on Liability | 101 | 14 | 3 (3%) | 11 (11%) | The costly direction is the rarest: 3 contracts in 101 |
| Governing Law | 84 | 8 | — | — | 5 wrong values, 3 blanks |

**The shape of the error is favourable, and that was the design intent.** In all
four presence clauses a false *present* is roughly twice as common as a false
*absent*. A false present costs the reviewer one reading. A false absent means a
clause that exists is reported missing, and on Cap on Liability — the clause a
lawyer looks for first — that happens in 3 contracts out of 101.

**Document Name is the outlier and should be treated as one.** It is the least
accurate clause (66%), the one with the widest demographic spread (46% on the
shortest quartile against 84% on the third, per `measure_bias.py`), and the only
one whose errors are all confident wrong values rather than blanks. Of the three
properties, the third is the one that matters: the other clauses fail by going
quiet, this one fails by being wrong out loud.

**Not covered.** No estimate of frequency in a real deployment, because there is
no deployment. No harm analysis beyond the immediate reader. No incident history.
