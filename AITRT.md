# Mapped against the AI Trust & Risk Taxonomy (AITRT)

[AITRT](https://github.com/ankampriyanka/Responsible-AI-RAI-AI-Trust-Risk-Taxonomy)
is an open, machine-readable layer connecting AI risks to trust dimensions,
controls, metrics and evidence. It is v0.1.0, Apache-2.0, and its own README says
the cross-framework mappings will be expanded and independently verified.

**It is used here as a checklist, not as a credential.** The authority for this
project's claims is [NIST-AI-RMF.md](NIST-AI-RMF.md). AITRT earns its place for a
different reason: it names risks NIST leaves implicit, and one of them was a live
defect in this project.

## What it caught that NIST did not

**AITRT-RISK-MODEL-003, Calibration Risk** — *the risk that model confidence
does not appropriately correspond to observed correctness.*

The sheet used to print one number beside every row of a clause: that clause's
accuracy over 101 contracts. A reader sees `Cap on Liability — 84%` and reads
"84% likely to be right here". It never meant that. It was a population rate,
identical on the row the detector was sure about and the row it barely decided.

`calibrate.py` now fits the margin between the window score and the calibrated
threshold against the accuracy that margin actually achieved, on the validation
split. Measured on the held-out split:

| | Expected Calibration Error |
|---|---:|
| One flat number per clause | **12.7%** |
| Calibrated by margin | **7.5%** |

The spread inside a single clause is the finding. Cap on Liability is 96%
correct when the score clears the threshold comfortably and **63%** when it
barely clears it — the flat 84% hid a 33-point difference. Two contracts now
show 92% and 50% on the same clause, which is what was true all along.

Rule-based clauses are not calibrated. The rule either produced a value or it did
not, and nothing separates a confident extraction from a lucky one. Those rows
carry the clause's measured accuracy and the interface labels it as exactly that
rather than dressing it as a per-row probability.

**AITRT-RISK-REG-001, Regulatory Classification Risk** — still open. No
assessment has been made of whether a contract-analysis tool falls under any
high-risk category in applicable regulation. "Probably not" is not an assessment.

## Where the project already stood

| Risk | Evidence |
|---|---|
| HS-003 Overreliance | [USING-THE-SHEET.md](USING-THE-SHEET.md), the five row states, a number on every row |
| HS-001 Harmful Bias | `measure_bias.py`, with Wilson intervals because the groups are small |
| SAFETY-002 Edge-Case Failure | `test_degradation.py`, which found the sheet asserting control characters as a title |
| SAFETY-003 Insufficient Human Intervention | `review` and `absent_review` are AITRT-CTRL-007 |
| MODEL-001 Validity | Measured end to end on contracts never seen |
| GOV-002 Documentation Deficiency | Seven documents, gaps named |
| DATA-002 / DATA-003 Quality and Provenance | 94.17% of cells usable, measured; CUAD CC BY 4.0 attributed |
| REG-003 Third-Party Dependency | Standard library only, asserted by `test_security.py` |
| SEC-001 Adversarial Manipulation | Every pattern timed against adversarial input at the scale it receives |

## Where the design is structurally immune

**SEC-004, Prompt or Context Manipulation** — *not applicable*. There is no model
receiving instructions, so there is no surface. The same largely holds for
SEC-003, Model Extraction: there is no model to extract, only regular
expressions and a term list anyone can read.

That is a consequence of choosing rules and term retrieval over a language model,
and it was not the reason for the choice. The measurement was. But it is a real
property and worth naming.

## Still open

| Risk | Why |
|---|---|
| MODEL-002 Model Drift · GOV-003 Monitoring Gap | Not deployed |
| GOV-001 Accountability Gap | No organization owns this |
| HS-002 Accessibility | The page was built responsive and theme-aware, but no accessibility testing was done |
| REG-001 Regulatory Classification | No assessment made |
| SEC-002 Poisoning | The cue terms are learned from CUAD; a corrupted corpus would corrupt them. Mitigated only by the corpus being public and fixed |
