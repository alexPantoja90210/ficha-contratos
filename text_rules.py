#!/usr/bin/env python3
"""Rules for running contract prose.

measure_rules.py receives lists of entities the annotator already extracted. On a
raw contract they have to be pulled out of the sentence, which is a different
problem — and one the rules lose: 5.8% end to end. Parties is out of scope for
that reason, and this module is kept as the measured evidence of it.
"""
import re

# ... Acme Systems, Inc., a Delaware corporation ("Company") ...
# The name starts after a boundary (comma, parenthesis, "and", "between") so it
# does not drag in the previous sentence, and the corporate descriptor sitting
# between the name and the alias is stripped off.
ENTITY_WITH_ALIAS = re.compile(
    r"""(?:^|[,;()]|\band\b|\bbetween\b|\n)\s*
        ([A-Z][\w&.'\-]*(?:[ ][\w&.'\-]+){0,7}?)      # the name
        \s*(?:,?\s*(?:an?|the)\s[^,()]{0,60})?         # ", a Delaware corporation"
        \s*,?\s*\(\s*["“‘']?\s*
        ([^"”’')]{1,40}?)                    # the alias
        \s*["”’']?\s*\)""",
    re.X)

# The company descriptor between a party name and its alias.
# The leading separator is a single optional comma rather than [,\s]+, and the
# middle class excludes commas and parentheses: with the loose version this
# pattern took 40 seconds on adversarial whitespace, which is a denial of
# service on a 338,000-character contract.
DESCRIPTOR = re.compile(
    r"(?i)\s*,?\s*(?:an?|the)\s[^,()]{0,40}?"
    r"(?:corporation|company|llc|l\.l\.c\.|inc\.?|ltd\.?|limited|partnership|"
    r"gmbh|s\.a\.|b\.v\.|plc|trust|association|entity)\s*$")

# A captured party name is bounded before the quadratic DESCRIPTOR pattern ever
# sees it. This is the bound the security test names: the pattern is quadratic,
# so the guarantee has to come from the input size, not from the regex.
MAX_NAME = 200


def strip_descriptor(name):
    """Drop the trailing corporate descriptor from a captured party name."""
    if not name:
        return ""
    return DESCRIPTOR.sub("", name[:MAX_NAME])


ALIAS_NOT_PARTY = re.compile(
    r"(?i)^(the\s+)?(agreement|effective\s+date|term|parties|exhibit|schedule|"
    r"annex|closing|company\s+products?|services?|software|products?|territory|"
    r"site|website|program|content|confidential\s+information|\d[\d.\- ]*)$")


def parties_from_text(fragments, limit=6):
    out, seen = [], set()
    for f in fragments:
        for m in ENTITY_WITH_ALIAS.finditer(f):
            name = strip_descriptor(m.group(1)).strip(" ,;.")
            alias = m.group(2).strip(" ,;.")
            if len(name) < 4 or ALIAS_NOT_PARTY.match(alias):
                continue
            # a name that is just one lowercase common word is not an entity
            if name.islower():
                continue
            k = re.sub(r"[^a-z0-9]", "", name.lower())
            if k and k not in seen:
                seen.add(k)
                out.append(f'{name} ("{alias}")')
            if len(out) >= limit:
                break
        if len(out) >= 2:
            break
    return "; ".join(out) if out else None
