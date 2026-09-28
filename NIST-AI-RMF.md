# Mapped against the NIST AI Risk Management Framework

This project was measured against [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)
after it was built, using the subcategory outcomes published in the
[AI RMF Playbook](https://airc.nist.gov/airmf-resources/playbook).

**The headline is a failure, and it is the expected one.** The project meets
most of what MEASURE asks for and **none of what GOVERN asks for**. GOVERN is
organizational: policies, accountability structures, workforce training, legal
compliance, third-party procurement. One person with a laptop cannot satisfy it,
and a project that claimed to would be lying.

That split is the useful result. It says precisely what an organization would
have to add before this could be deployed, and it says the technical evidence is
already there.

| Function | Met | Partial | Not met | N/A |
|---|---:|---:|---:|---:|
| GOVERN (6 categories) | 0 | 0 | 6 | 0 |
| MAP (17 subcategories) | 8 | 4 | 4 | 1 |
| MEASURE 1–2 (14 subcategories) | 7 | 2 | 4 | 1 |

MEASURE 3 and 4 cover tracking risk in deployment and collecting feedback from
users. The system is not deployed and has no users, so they are out of reach
rather than unmet.

---

## MEASURE — where the project is strong

| Subcategory | Outcome | Status | Evidence |
|---|---|---|---|
| **MEASURE 1.1** | Metrics selected starting with the most significant risks | Met | Recall is in the scope criterion because a false "not present" on a liability cap is the expensive error. `scope.py` |
| **MEASURE 1.2** | Appropriateness of metrics regularly assessed and updated | **Met** | Plain accuracy was rejected once `trivial_floor.py` showed that always answering "not present" scores 79.7%. The metric changed to balanced accuracy plus recall, and later a naive-parse baseline was added as a third gate. |
| **MEASURE 1.3** | Assessors who were not front-line developers | **Not met** | Solo project, no independent review. Partially offset by `baseline_naive.py` and by comparison against a third-party harness, but neither is an independent assessor. |
| **MEASURE 2.1** | Test sets, metrics and TEVV tooling documented | Met | Held-out split of CUAD; five measurement scripts in the repository, each stating what it measures and what it does not. |
| **MEASURE 2.2** | Human-subject evaluations | N/A | No human subjects. |
| **MEASURE 2.3** | Performance demonstrated under deployment-like conditions | Met | Measured on raw full contracts, not on pre-located paragraphs. `measure_e2e.py` reports the gap between the two. |
| **MEASURE 2.4** | Behaviour monitored in production | Not met | Not deployed. |
| **MEASURE 2.5** | Valid and reliable; generalizability limits documented | **Met** | Determinism verified across runs; a real non-determinism defect was found and fixed. Limits stated: English, US commercial contracts. |
| **MEASURE 2.6** | Evaluated for safety; fails safely | Partial | The sheet degrades to `review` and `absent_review` rather than asserting. No formal safety evaluation. |
| **MEASURE 2.7** | Security and resilience evaluated | Not met | Not examined. |
| **MEASURE 2.8** | Transparency and accountability risks documented | Met | Every row carries its measured accuracy; the 33 out-of-scope categories are published with their numbers. |
| **MEASURE 2.9** | Model explained, validated, documented; output interpreted in context | **Met** | The rules are readable regular expressions and the learned cue terms are inspectable JSON. Nothing in the system is opaque. |
| **MEASURE 2.10** | Privacy risk examined | Partial | Runs locally with no network calls, so no contract leaves the machine. Not formally examined. |
| **MEASURE 2.11** | Fairness and bias evaluated | **Not met** | Not evaluated. |

## MAP — mostly met at the system level

Met: **1.1** purpose and context documented · **2.1** task and method defined ·
**2.2** knowledge limits and human oversight documented · **2.3** scientific
integrity and TEVV design (the split is by contract, never by question) ·
**3.2** cost of errors examined · **3.3** targeted application scope specified
(`scope.py` is this subcategory) · **3.5** human oversight defined · **4.1**
third-party data licensing (CUAD, CC BY 4.0).

Partial: **1.4** business value, **1.5** risk tolerance (thresholds are explicit
but not organizational), **4.2** internal risk controls, **5.1** impact
likelihood and magnitude.

Not met: **1.2** interdisciplinary actors and demographic diversity, **1.3**
organizational mission, **1.6** requirements elicited from AI actors, **3.4**
operator proficiency processes. All four need people this project does not have.

## GOVERN — none of it

| Category | Why not |
|---|---|
| GOVERN 1 | No organizational AI policy; no legal or regulatory review |
| GOVERN 2 | No accountability structure, no assigned roles |
| GOVERN 3 | No workforce, so no diversity or inclusion process |
| GOVERN 4 | No organizational risk culture |
| GOVERN 5 | No engagement process with external AI actors |
| GOVERN 6 | No third-party procurement policy |

## What this would take to close

The technical gaps are small and nameable: a fairness and bias evaluation
(MEASURE 2.11), a security review (2.7), and one reviewer who did not write the
code (1.3). The governance gaps are not technical work at all — they are an
organization deciding to own the system.

## A note on ISO/IEC 42001

[ISO/IEC 42001:2023](https://www.iso.org/standard/42001) was considered and set
aside. It is a certifiable management-system standard built on the same
harmonized structure as ISO 9001 and 27001: leadership commitment, competence
and training, internal audits by independent auditors, management review at
planned intervals. Those are organizational by definition. A solo project cannot
be assessed against it in any honest way, which is why NIST AI RMF was used —
its MAP and MEASURE functions apply at the level of a single system.
