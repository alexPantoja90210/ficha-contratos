#!/usr/bin/env python3
"""Rules for running contract prose.

measure_rules.py receives lists of entities the annotator already extracted. On a
raw contract they have to be pulled out of the sentence, which is a different
problem — and one the rules lose: 5.8% end to end. Parties is out of scope for
that reason, and this module is kept as the measured evidence of it.
"""
import re

# ... Acme Systems, Inc., a Delaware corporation ("Company") ...
# El name arranca tras una frontera (coma, parentesis, "and", "between") para
# no arrastrar la oracion previa, y se descarta el descriptor societario que
# va entre el name y el alias.
ENTITY_WITH_ALIAS = re.compile(
    r"""(?:^|[,;()]|\band\b|\bbetween\b|\n)\s*
        ([A-Z][\w&.'\-]*(?:[ ][\w&.'\-]+){0,7}?)      # el name
        \s*(?:,?\s*(?:an?|the)\s[^,()]{0,60})?         # ", a Delaware corporation"
        \s*,?\s*\(\s*["“‘']?\s*
        ([^"”’')]{1,40}?)                    # el alias
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

ALIAS_NOT_PARTY = re.compile(
    r"(?i)^(the\s+)?(agreement|effective\s+date|term|parties|exhibit|schedule|"
    r"annex|closing|company\s+products?|services?|software|products?|territory|"
    r"site|website|program|content|confidential\s+information|\d[\d.\- ]*)$")


def parties_from_text(fragments, maximo=6):
    out, seen = [], set()
    for f in fragments:
        for m in ENTITY_WITH_ALIAS.finditer(f):
            name = strip_descriptor(m.group(1)).strip(" ,;.")
            alias = m.group(2).strip(" ,;.")
            if len(name) < 4 or ALIAS_NOT_PARTY.match(alias):
                continue
            # un name que es solo una palabra comun no es una entidad
            if name.islower():
                continue
            k = re.sub(r"[^a-z0-9]", "", name.lower())
            if k and k not in seen:
                seen.add(k)
                out.append(f'{name} ("{alias}")')
            if len(out) >= maximo:
                break
        if len(out) >= 2:
            break
    return "; ".join(out) if out else None
