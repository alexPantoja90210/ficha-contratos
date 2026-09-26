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

FRONT_WINDOW = 8000   # cubre el 94% de los campos de portada
AFTER_ANCHOR   = 1200   # text util tras un ancla lexica
BEFORE_ANCHOR     = 400

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

# Las fechas se buscan SOLO en la portada y SOLO hacia adelante del ancla:
# una ventana que mire hacia atras arrastra fechas de otra clausula.
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
    """Dado el text completo de un contract, propone fragments por category."""

    BOILERPLATE = re.compile(
        r"(?i)^(exhibit|ex-|execution\s+(copy|version)|confidential|"
        r"page\s+\d+|redacted|filed|form\s+\d|schedule\b|annex\b|"
        r"\[?\*+\]?|\d+[\d.\-]*)\b")
    TIPO = re.compile(r"(?i)\b(agreements?|contract|licen[cs]e|lease|indenture|"
                      r"memorandum\s+of\s+understanding)\b")

    def __init__(self, text):
        self.text = text
        self.portada = text[:FRONT_WINDOW]

    # -- helpers -----------------------------------------------------------
    def _windows(self, patrones, text=None, maximo=6,
                  antes=BEFORE_ANCHOR, despues=AFTER_ANCHOR):
        text = self.text if text is None else text
        out = []
        for pat in patrones:
            for m in re.finditer(pat, text, re.I):
                out.append(text[max(0, m.start() - antes): m.end() + despues])
                if len(out) >= maximo:
                    return out
        return out

    def _after_anchor(self, patrones, text, despues, maximo=8, antes=0):
        """Ventanas que empiezan EN el ancla: no arrastran data anteriores.

        Devuelve varias, en ordered de specificity del pattern y luego de
        aparicion. La regla recorre la lista y se queda con la primera que
        rinda un value; una sola ventana falla cuando el ancla aparece antes
        mencionada que definida.
        """
        out = []
        for pat in patrones:
            for m in re.finditer(pat, text, re.I):
                out.append(text[max(0, m.start() - antes): m.end() + despues])
                if len(out) >= maximo:
                    return out
        return out

    # -- por category -----------------------------------------------------
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
            kind = self.TIPO.search(t)
            if kind and upper_ratio > 0.7:
                return [t[:list(self.TIPO.finditer(t))[-1].end()].strip()]
            if kind or upper_ratio > 0.85:
                candidates.append((bool(kind), upper_ratio, t))
        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
            best = candidates[0][2]
            fin = list(self.TIPO.finditer(best))
            return [best[:fin[-1].end()].strip() if fin else best]
        # Respaldo: la clausula definitoria del cuerpo
        m = re.search(r"(?i)\bthis\s+(.{0,70}?\b(?:agreement|contract|licen[cs]e))\b",
                      self.text[:4000])
        return [m.group(1).strip().upper()] if m else [pieces[0] if pieces else ""]

    def _parties(self):
        candidates = []
        for m in re.finditer(r"(?is)\b(?:by\s+and\s+between|between)\b(.{0,900}?)"
                             r"(?:\bwitnesseth\b|\brecitals\b|\n\s*\n|$)", self.portada):
            if len(m.group(1).strip()) >= 30:
                candidates.append(m.group(1))
        # Respaldo: el preambulo entero, where igual estan los alias entre parentesis
        candidates.append(self.portada[:4000])
        return candidates

    # -- interfaz ----------------------------------------------------------
    def fragments(self, category):
        k = key_of(category)
        if k == "document name":
            return self._title()
        if k == "parties":
            return self._parties()
        if k in DATE_ANCHORS:
            v = self._after_anchor(DATE_ANCHORS[k], self.portada, AFTER_DATE,
                                 antes=BEFORE_DATE.get(k, 0))
            if k == "effective date":
                # Muchos contracts no distinguen ambas fechas: si la etiqueta
                # no rindio nada, vale la del preambulo.
                v = v + self._after_anchor(DATE_ANCHORS["agreement date"],
                                         self.portada, AFTER_DATE)
            return v or [self.portada[:2500]]
        if k in ANCHORS:
            return self._windows(ANCHORS[k])
        # Sin estrategia de localizacion para esta category. Devolver el
        # documento entero seria mentir: cualquier regla encontraria "algo".
        # La sheet lo marker como pendiente de la capa de retrieval.
        return []

    SOPORTADAS = {"document name", "parties", "agreement date",
                  "effective date", "governing law",
                  "notice period to terminate renewal", "renewal term"}

    def supports(self, category):
        return key_of(category) in self.SOPORTADAS
