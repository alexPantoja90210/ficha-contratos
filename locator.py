#!/usr/bin/env python3
"""TextLocator: finds the clause inside the raw contract.

This is the half that measure_rules.py does not measure: there the paragraph
arrives already marked by the annotator. Same interface as the corpus stand-in:

    locator.fragments(category) -> list[str]

The strategy per category comes from where each clause actually lives. The header
fields sit in the first 1% of the document and are searched in an opening window.
Governing Law sits at the 84% mark and is searched by lexical anchor across the
WHOLE text — precisely what a reader that truncates to 8k cannot do.

A category with no strategy returns an empty list. Returning the whole document
would be a lie: any rule would then find "something".
"""
import re

FRONT_WINDOW  = 8000   # covers 94% of the header fields
AFTER_ANCHOR  = 1200   # useful text after a lexical anchor
BEFORE_ANCHOR =  400

ANCHORS = {
    "governing law": [
        r"govern(?:ed|ing)\s+(?:by|law)", r"construed\s+in\s+accordance",
        r"laws?\s+of\s+the\s+(?:State|Commonwealth|Province)",
        r"interpreted\s+and\s+enforced", r"applicable\s+law",
    ],
    "notice period to terminate renewal": [
        r"notice\s+of\s+non-?renewal", r"non-?renewal",
        r"notice.{0,60}prior\s+to\s+the\s+(?:end|expiration)",
        r"renew.{0,200}?notice", r"written\s+notice.{0,80}renew",
    ],
    "renewal term": [
        r"automatically\s+renew", r"shall\s+renew", r"renewal\s+term",
        r"successive\s+(?:terms|periods)", r"additional\s+(?:term|period)",
    ],
}

# Dates are searched ONLY in the front matter and ONLY forward of the anchor:
# a window that looks backwards drags in a date from another clause.
DATE_ANCHORS = {
    "agreement date": [
        r"dated\s+as\s+of", r"made\s+(?:and\s+entered\s+into\s+)?as\s+of",
        r"entered\s+into\s+(?:as\s+of|on)", r"made\s+(?:as\s+of|on)",
        r"this\s+\d{1,2}\s*(?:st|nd|rd|th|t\s*h)?\s+day\s+of",
        r"executed\s+(?:as\s+of|on)",
    ],
    "effective date": [
        r'[Ee]ffective\s+Date[^.\n]{0,40}?(?:is|as\s+of|:)',
        r"effective\s+as\s+of", r'"?Effective\s+Date"?\)?\s*[:,]',
        r"[Ee]ffective\s+Date",
    ],
}
AFTER_DATE = 220
BEFORE_DATE   = {"effective date": 170, "agreement date": 0}


def key_of(name):
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ").strip()


class TextLocator:
    """Given the full text of a contract, proposes fragments per category."""

    BOILERPLATE = re.compile(
        r"(?i)^(exhibit|ex-|execution\s+(copy|version)|confidential|"
        r"page\s+\d+|redacted|filed|form\s+\d|schedule\b|annex\b|"
        r"\[?\*+\]?|\d+[\d.\-]*)\b")
    KIND = re.compile(r"(?i)\b(agreements?|contract|licen[cs]e|lease|indenture|"
                      r"memorandum\s+of\s+understanding)\b")

    def __init__(self, text):
        self.text = text
        self.front = text[:FRONT_WINDOW]

    # -- helpers -----------------------------------------------------------
    def _windows(self, patterns, text=None, limit=6,
                 before=BEFORE_ANCHOR, after=AFTER_ANCHOR):
        text = self.text if text is None else text
        out = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.I):
                out.append(text[max(0, m.start() - before): m.end() + after])
                if len(out) >= limit:
                    return out
        return out

    def _after_anchor(self, patterns, text, after, limit=8, before=0):
        """Windows that start AT the anchor: they drag in no earlier data.

        Returns several, ordered by pattern specificity and then by position.
        The rule walks the list and keeps the first one that yields a value; a
        single window fails whenever the anchor is mentioned before it is
        defined.
        """
        out = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.I):
                out.append(text[max(0, m.start() - before): m.end() + after])
                if len(out) >= limit:
                    return out
        return out

    # -- per category ------------------------------------------------------
    def _title(self):
        pieces = [t.strip() for t in re.split(r"\n|\s{2,}", self.text[:3000]) if t.strip()]
        candidates = []
        for t in pieces[:40]:
            if len(t) < 8 or len(t) > 130 or self.BOILERPLATE.match(t):
                continue
            if re.match(r"(?i)^(this|the|whereas|between)\b", t):
                continue
            letters = [c for c in t if c.isalpha()]
            if not letters:
                continue
            upper_ratio = sum(c.isupper() for c in letters) / len(letters)
            kind = self.KIND.search(t)
            if kind and upper_ratio > 0.7:
                return [t[:list(self.KIND.finditer(t))[-1].end()].strip()]
            if kind or upper_ratio > 0.85:
                candidates.append((bool(kind), upper_ratio, t))
        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
            best = candidates[0][2]
            end = list(self.KIND.finditer(best))
            return [best[:end[-1].end()].strip() if end else best]
        # Fallback: the defining clause in the body
        m = re.search(r"(?i)\bthis\s+(.{0,70}?\b(?:agreement|contract|licen[cs]e))\b",
                      self.text[:4000])
        return [m.group(1).strip().upper()] if m else [pieces[0] if pieces else ""]

    def _parties(self):
        candidates = []
        for m in re.finditer(r"(?is)\b(?:by\s+and\s+between|between)\b(.{0,900}?)"
                             r"(?:\bwitnesseth\b|\brecitals\b|\n\s*\n|$)", self.front):
            if len(m.group(1).strip()) >= 30:
                candidates.append(m.group(1))
        # Fallback: the whole preamble, where the parenthesised aliases live anyway
        candidates.append(self.front[:4000])
        return candidates

    # -- interface ---------------------------------------------------------
    def fragments(self, category):
        k = key_of(category)
        if k == "document name":
            return self._title()
        if k == "parties":
            return self._parties()
        if k in DATE_ANCHORS:
            v = self._after_anchor(DATE_ANCHORS[k], self.front, AFTER_DATE,
                                   before=BEFORE_DATE.get(k, 0))
            if k == "effective date":
                # Many contracts do not distinguish the two dates: if the label
                # yielded nothing, the one in the preamble will do.
                v = v + self._after_anchor(DATE_ANCHORS["agreement date"],
                                           self.front, AFTER_DATE)
            return v or [self.front[:2500]]
        if k in ANCHORS:
            return self._windows(ANCHORS[k])
        # No location strategy for this category. Returning the whole document
        # would be a lie: any rule would then find "something". The sheet marks
        # it as pending on the retrieval layer instead.
        return []

    SUPPORTED = {"document name", "parties", "agreement date",
                 "effective date", "governing law",
                 "notice period to terminate renewal", "renewal term"}

    def supports(self, category):
        return key_of(category) in self.SUPPORTED
