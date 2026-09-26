#!/usr/bin/env python3
"""El parseo ingenuo: lo que sale "de todas maneras", sin pensarlo.

Existe para contestar una sola pregunta: ¿el trabajo de localizar y calibrar
aporta algo sobre lo obvio? Si estas cifras empatan con las del producto, el
producto no vale la pena y hay que decirlo.

Las reglas ingenuas son las que escribiria cualquiera en una tarde:
  Document Name   la primera linea no vacia
  Agreement Date  la primera fecha del documento
  Effective Date  la primera fecha del documento
  Governing Law   el primer estado o pais nombrado en el documento
  presencia       "no esta" siempre (la respuesta mayoritaria)
"""
import ast, csv, io, json, re, sys
from pathlib import Path

import medir_reglas as R
from localizador import clave
from alcance import decidir


from medir_reglas import ESTADOS as GAZ

FECHA = re.compile(
    r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})")

def ingenuo_titulo(t):
    for linea in t.splitlines():
        if linea.strip():
            return linea.strip()
    return None

def ingenua_fecha(t):
    m = FECHA.search(t)
    return R.extrae_fecha(m.group(0)) if m else None

def ingenua_ley(t):
    pos = [(t.lower().find(e.lower()), e) for e in GAZ]
    pos = [(i, e) for i, e in pos if i >= 0]
    return min(pos)[1] if pos else None

INGENUAS = {
    "document name":  (ingenuo_titulo, R.igual_texto),
    "agreement date": (ingenua_fecha,  R.igual_fecha),
    "effective date": (ingenua_fecha,  R.igual_fecha),
    "governing law":  (ingenua_ley,    R.igual_contiene),
}

def columna(fila, cat):
    k = clave(cat)
    for c in fila:
        if c.endswith("-Answer") or c.endswith("- Answer"):
            if clave(c.replace("- Answer", "").replace("-Answer", "")) == k:
                return c

def presente(fila, cat):
    k = clave(cat)
    for c in fila:
        if c.endswith("Answer"):
            continue
        if clave(c) == k:
            v = (fila.get(c) or "").strip()
            try:
                v = ast.literal_eval(v) if v else []
            except (ValueError, SyntaxError):
                v = [v] if v else []
            return bool(v)

# lo que mide medir_ficha.py para el producto, sobre la misma particion
PRODUCTO = {"Document Name": 66, "Agreement Date": 74, "Effective Date": 67,
            "Governing Law": 90, "Cap on Liability": 86, "License Grant": 76,
            "Warranty Duration": 76, "Insurance": 76,
            "No-Solicit of Employees": 80, "Audit Rights": 73}

def main(ruta_json, ruta_csv):
    contratos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n
    prueba = set(sorted(contratos)[int(len(contratos) * 0.8):])
    dentro, _ = decidir()

    print(f"{'categoria':30}{'ingenuo':>9}{'producto':>10}{'gana':>8}")
    total_i = total_p = n_cat = 0
    for f in dentro:
        cat = f["categoria"]
        k = clave(cat)
        bien = n = 0
        for fila in filas:
            nom = stem(fila["Filename"])
            texto = contratos.get(nom)
            if texto is None or nom not in prueba:
                continue
            if k in INGENUAS:
                col = columna(filas[0], cat)
                real = (fila.get(col) or "").strip() if col else ""
                if not real or R.REDACTADA.fullmatch(real):
                    continue
                regla, cmp_ = INGENUAS[k]
                ok = cmp_(regla(texto), real)
            else:
                real = presente(fila, cat)
                if real is None:
                    continue
                ok = (False == real)      # el ingenuo dice "no esta" siempre
            n += 1
            bien += ok
        pct = 100 * bien / n if n else 0
        prod = next(v for kk, v in PRODUCTO.items() if clave(kk) == k)
        total_i += pct; total_p += prod; n_cat += 1
        print(f"{cat:30}{pct:>8.0f}%{prod:>9}%{prod-pct:>+7.0f}")
    print(f"\n{'promedio':30}{total_i/n_cat:>8.0f}%{total_p/n_cat:>9.0f}%"
          f"{(total_p-total_i)/n_cat:>+7.0f}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contratos.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
