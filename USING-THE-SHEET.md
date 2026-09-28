# Using the sheet

Covers NIST AI RMF **MAP 3.4** (operator proficiency). What a reader has to know
before the sheet is worth anything to them.

## The one rule

**The sheet is a reading aid. It is never the reviewer of record.** It tells you
where to look first and what might be missing. It does not tell you whether a
clause is favourable, enforceable, or standard for your industry. It is not legal
advice.

## What each state means, and what you owe it

| State | What the sheet is saying | What you have to do |
|---|---|---|
| `found` | A value was extracted, or a clause was detected | Read the highlighted paragraph. On a rule-based row the highlight is the exact text; confirm it is the clause you wanted |
| `absent` | The clause was looked for and not found, and the measured recall supports saying so | Trust it least on the clauses with the lowest recall. Check the accuracy on the row |
| `absent_review` | It looks absent, but the detector does not see enough to assert it | Read the contract for this clause yourself. This state exists because the alternative was a confident lie |
| `review` | A candidate exists, but the clause is expensive enough that a person confirms | Always read this one |
| `model_pending` | The rule was measured and lost; nothing is claimed | Read the contract |

## Read the number on every row

Each row carries the accuracy measured for that clause on 101 contracts the
system never saw. A row at 90% and a row at 66% are not the same claim, and the
sheet does not pretend they are.

Today: Governing Law 90%, Cap on Liability 86%, License Grant 76%, Insurance 76%,
Agreement Date 74%, Audit Rights 73%, Effective Date 67%, Document Name 66%.

## Four things the sheet will not tell you

1. **Where a presence clause is.** Rule-based rows jump to the exact paragraph.
   Presence rows show the highest-scoring passage with no guarantee it is the
   clause: location is right between 12% and 46% of the time. Treat that passage
   as a starting point, not an answer.
2. **The other 33 clauses.** The sheet covers eight of CUAD's 41 categories.
   Everything else is out of scope and silent — silence here is not absence.
3. **Anything about contracts unlike its corpus.** English, US commercial
   contracts. A contract in Spanish, or under another jurisdiction, is outside
   what was measured.
4. **Whether it is having a bad day on your document.** Short contracts get
   worse titles: Document Name drops to 46% on the shortest quartile.

## Before you rely on a row

- Is the clause one of the eight? If not, the sheet has no opinion.
- Is the row's accuracy high enough for the decision you are making?
- If the row says absent and the clause matters, read for it anyway.
- If the row says `review` or `absent_review`, that is the sheet asking for you
  by name.
