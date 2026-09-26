#!/usr/bin/env python3
"""Reglas para texto corrido del contrato.

`medir_reglas.py` recibia listas de entidades ya extraidas por el anotador.
Sobre el contrato crudo hay que sacarlas de la frase, que es otro problema.
"""
import re

# ... Acme Systems, Inc., a Delaware corporation ("Company") ...
# El nombre arranca tras una frontera (coma, parentesis, "and", "between") para
# no arrastrar la oracion previa, y se descarta el descriptor societario que
# va entre el nombre y el alias.
ENTIDAD_CON_ALIAS = re.compile(
    r"""(?:^|[,;()]|\band\b|\bbetween\b|\n)\s*
        ([A-Z][\w&.'\-]*(?:[ ][\w&.'\-]+){0,7}?)      # el nombre
        \s*(?:,?\s*(?:an?|the)\s[^,()]{0,60})?         # ", a Delaware corporation"
        \s*,?\s*\(\s*["“‘']?\s*
        ([^"”’')]{1,40}?)                    # el alias
        \s*["”’']?\s*\)""",
    re.X)

DESCRIPTOR = re.compile(
    r"(?i)[,\s]+(a|an|the)\s+[\w\- ]{0,40}?"
    r"(corporation|company|llc|l\.l\.c\.|inc\.?|ltd\.?|limited|partnership|"
    r"gmbh|s\.a\.|b\.v\.|plc|trust|association|entity)\s*$")

ALIAS_NO_PARTE = re.compile(
    r"(?i)^(the\s+)?(agreement|effective\s+date|term|parties|exhibit|schedule|"
    r"annex|closing|company\s+products?|services?|software|products?|territory|"
    r"site|website|program|content|confidential\s+information|\d[\d.\- ]*)$")


def partes_de_texto(fragmentos, maximo=6):
    salida, vistos = [], set()
    for f in fragmentos:
        for m in ENTIDAD_CON_ALIAS.finditer(f):
            nombre = DESCRIPTOR.sub("", m.group(1)).strip(" ,;.")
            alias = m.group(2).strip(" ,;.")
            if len(nombre) < 4 or ALIAS_NO_PARTE.match(alias):
                continue
            # un nombre que es solo una palabra comun no es una entidad
            if nombre.islower():
                continue
            k = re.sub(r"[^a-z0-9]", "", nombre.lower())
            if k and k not in vistos:
                vistos.add(k)
                salida.append(f'{nombre} ("{alias}")')
            if len(salida) >= maximo:
                break
        if len(salida) >= 2:
            break
    return "; ".join(salida) if salida else None
