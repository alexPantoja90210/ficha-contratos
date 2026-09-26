#!/usr/bin/env python3
"""LocalizadorDeTexto: encuentra la clausula dentro del contrato crudo.

Es la mitad que `medir_reglas.py` no medja: alli el parrafo venia ya marcado
por el anotador. Misma interfaz que `LocalizadorDeCorpus` de ficha.py:

    localizador.fragmentos(categoria) -> list[str]

La estrategia por categoria sale del dato de posicion mediana de cada clausula:
los campos de portada viven en el primer 1% del documento y se buscan en una
ventana inicial; Governing Law vive en el 84% y se busca por ancla lexica en
TODO el texto -- justo lo que un modelo que trunca a 8k no puede hacer.
"""
import re

VENTANA_PORTADA = 8000   # cubre el 94% de los campos de portada
DESPUES_ANCLA   = 1200   # texto util tras un ancla lexica
ANTES_ANCLA     = 400

ANCLAS = {
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
ANCLAS_FECHA = {
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
DESPUES_FECHA = 220
ANTES_FECHA   = {"effective date": 170, "agreement date": 0}


def clave(nombre):
    return "".join(ch for ch in nombre.lower() if ch.isalnum() or ch == " ").strip()


class LocalizadorDeTexto:
    """Dado el texto completo de un contrato, propone fragmentos por categoria."""

    BOILERPLATE = re.compile(
        r"(?i)^(exhibit|ex-|execution\s+(copy|version)|confidential|"
        r"page\s+\d+|redacted|filed|form\s+\d|schedule\b|annex\b|"
        r"\[?\*+\]?|\d+[\d.\-]*)\b")
    TIPO = re.compile(r"(?i)\b(agreements?|contract|licen[cs]e|lease|indenture|"
                      r"memorandum\s+of\s+understanding)\b")

    def __init__(self, texto):
        self.texto = texto
        self.portada = texto[:VENTANA_PORTADA]

    # -- helpers -----------------------------------------------------------
    def _ventanas(self, patrones, texto=None, maximo=6,
                  antes=ANTES_ANCLA, despues=DESPUES_ANCLA):
        texto = self.texto if texto is None else texto
        salida = []
        for pat in patrones:
            for m in re.finditer(pat, texto, re.I):
                salida.append(texto[max(0, m.start() - antes): m.end() + despues])
                if len(salida) >= maximo:
                    return salida
        return salida

    def _tras_ancla(self, patrones, texto, despues, maximo=8, antes=0):
        """Ventanas que empiezan EN el ancla: no arrastran datos anteriores.

        Devuelve varias, en orden de especificidad del patron y luego de
        aparicion. La regla recorre la lista y se queda con la primera que
        rinda un valor; una sola ventana falla cuando el ancla aparece antes
        mencionada que definida.
        """
        salida = []
        for pat in patrones:
            for m in re.finditer(pat, texto, re.I):
                salida.append(texto[max(0, m.start() - antes): m.end() + despues])
                if len(salida) >= maximo:
                    return salida
        return salida

    # -- por categoria -----------------------------------------------------
    def _titulo(self):
        piezas = [t.strip() for t in re.split(r"\n|\s{2,}", self.texto[:3000]) if t.strip()]
        candidatos = []
        for t in piezas[:40]:
            if len(t) < 8 or len(t) > 130 or self.BOILERPLATE.match(t):
                continue
            if re.match(r"(?i)^(this|the|whereas|between)\b", t):
                continue
            letras = [c for c in t if c.isalpha()]
            if not letras:
                continue
            mayus = sum(c.isupper() for c in letras) / len(letras)
            tipo = self.TIPO.search(t)
            if tipo and mayus > 0.7:
                return [t[:list(self.TIPO.finditer(t))[-1].end()].strip()]
            if tipo or mayus > 0.85:
                candidatos.append((bool(tipo), mayus, t))
        if candidatos:
            candidatos.sort(key=lambda c: (c[0], c[1]), reverse=True)
            mejor = candidatos[0][2]
            fin = list(self.TIPO.finditer(mejor))
            return [mejor[:fin[-1].end()].strip() if fin else mejor]
        # Respaldo: la clausula definitoria del cuerpo
        m = re.search(r"(?i)\bthis\s+(.{0,70}?\b(?:agreement|contract|licen[cs]e))\b",
                      self.texto[:4000])
        return [m.group(1).strip().upper()] if m else [piezas[0] if piezas else ""]

    def _partes(self):
        candidatos = []
        for m in re.finditer(r"(?is)\b(?:by\s+and\s+between|between)\b(.{0,900}?)"
                             r"(?:\bwitnesseth\b|\brecitals\b|\n\s*\n|$)", self.portada):
            if len(m.group(1).strip()) >= 30:
                candidatos.append(m.group(1))
        # Respaldo: el preambulo entero, donde igual estan los alias entre parentesis
        candidatos.append(self.portada[:4000])
        return candidatos

    # -- interfaz ----------------------------------------------------------
    def fragmentos(self, categoria):
        k = clave(categoria)
        if k == "document name":
            return self._titulo()
        if k == "parties":
            return self._partes()
        if k in ANCLAS_FECHA:
            v = self._tras_ancla(ANCLAS_FECHA[k], self.portada, DESPUES_FECHA,
                                 antes=ANTES_FECHA.get(k, 0))
            if k == "effective date":
                # Muchos contratos no distinguen ambas fechas: si la etiqueta
                # no rindio nada, vale la del preambulo.
                v = v + self._tras_ancla(ANCLAS_FECHA["agreement date"],
                                         self.portada, DESPUES_FECHA)
            return v or [self.portada[:2500]]
        if k in ANCLAS:
            return self._ventanas(ANCLAS[k])
        # Sin estrategia de localizacion para esta categoria. Devolver el
        # documento entero seria mentir: cualquier regla encontraria "algo".
        # La ficha lo marca como pendiente de la capa de recuperacion.
        return []

    SOPORTADAS = {"document name", "parties", "agreement date",
                  "effective date", "governing law",
                  "notice period to terminate renewal", "renewal term"}

    def soporta(self, categoria):
        return clave(categoria) in self.SOPORTADAS
