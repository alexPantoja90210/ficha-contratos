#!/usr/bin/env python3
"""Mide las reglas de extraccion contra master_clauses.csv de CUAD.

Que mide y que NO mide
----------------------
master_clauses.csv guarda, por contrato y categoria, el FRAGMENTO que el
anotador marco y la RESPUESTA normalizada que escribio. Este script le da a
cada regla el fragmento ya localizado y compara su salida contra la respuesta.

  Mide     : la mitad de NORMALIZACION (del fragmento al valor).
  NO mide  : la mitad de LOCALIZACION (encontrar el fragmento en el contrato),
             porque este archivo no trae los contratos completos.

Un porcentaje alto aqui no dice que la regla funcione sobre un contrato crudo.
Dice que, una vez frente al parrafo correcto, saca el valor correcto.

Uso:  python medir_reglas.py master_clauses.csv
"""
import ast, csv, io, re, sys
from pathlib import Path

# ---------- lectura ----------------------------------------------------------
def fragmentos(celda):
    celda = (celda or "").strip()
    if not celda:
        return []
    try:
        v = ast.literal_eval(celda)
    except (ValueError, SyntaxError):
        return [celda]
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]

def columna_respuesta(fila, categoria):
    for suf in ("-Answer", "- Answer"):
        if categoria + suf in fila:
            return categoria + suf
    return None

# ---------- normalizadores ---------------------------------------------------
MESES = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}

FECHA_LARGA = re.compile(
    r"(?i)\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b")
FECHA_ORDINAL = re.compile(
    r"(?i)\b(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b")
FECHA_BARRAS = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
# "1 August 2019", "20t h day of November, 2018" (ruido de OCR en el ordinal)
FECHA_DIA_MES = re.compile(
    r"(?i)\b(\d{1,2})\s*(?:st|nd|rd|th|t\s*h)?\s*(?:day\s+of\s+)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b")

def a_mmddyy(mes, dia, anio):
    anio = int(anio)
    if anio > 100:
        anio %= 100
    return f"{int(mes)}/{int(dia)}/{anio:02d}"

def extrae_fecha(texto):
    m = FECHA_ORDINAL.search(texto)
    if m:
        return a_mmddyy(MESES[m.group(2)[:3].lower()], m.group(1), m.group(3))
    m = FECHA_LARGA.search(texto)
    if m:
        return a_mmddyy(MESES[m.group(1)[:3].lower()], m.group(2), m.group(3))
    m = FECHA_DIA_MES.search(texto)
    if m:
        return a_mmddyy(MESES[m.group(2)[:3].lower()], m.group(1), m.group(3))
    m = FECHA_BARRAS.search(texto)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 >= b:          # 29/3/18 viene en dia/mes/anio
            a, b = b, a
        return a_mmddyy(a, b, m.group(3))
    return None

def regla_fecha(frs):
    for f in frs:
        v = extrae_fecha(f)
        if v:
            return v
    return None

NUMEROS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
           "eight":8,"nine":9,"ten":10,"twelve":12,"fifteen":15,"twenty":20,
           "thirty":30,"forty":40,"forty-five":45,"sixty":60,"ninety":90,
           "hundred":100,"eighteen":18,"twenty-four":24,"thirty-six":36}
# "two (2) years" -> el digito entre parentesis manda sobre la palabra
PLAZO = re.compile(
    r"(?i)\b(?:(\d+)|([a-z]+(?:-[a-z]+)?))\s*(?:\(\s*(\d+)\s*\))?\s*"
    r"(day|week|month|year)s?\b")

def plazo(texto, unidades):
    for m in PLAZO.finditer(texto):
        unidad = m.group(4).lower()
        if unidad not in unidades:
            continue
        if m.group(3):
            n = int(m.group(3))
        elif m.group(1):
            n = int(m.group(1))
        else:
            n = NUMEROS.get(m.group(2).lower())
        if n:
            return f"{n} {unidad}{'s' if n != 1 else ''}"
    return None

def plazo_cerca(texto, unidades, claves, ventana=160):
    """El plazo mas cercano a una de las palabras clave. El parrafo suele traer
    varios (el termino de renovacion y el preaviso); el primero no es el bueno."""
    anclas = [m.start() for c in claves
              for m in re.finditer(c, texto, re.I)]
    if not anclas:
        return None
    mejor = None
    for m in PLAZO.finditer(texto):
        unidad = m.group(4).lower()
        if unidad not in unidades:
            continue
        if m.group(3):
            n = int(m.group(3))
        elif m.group(1):
            n = int(m.group(1))
        else:
            n = NUMEROS.get((m.group(2) or "").lower())
        if not n:
            continue
        d = min(abs(m.start() - a) for a in anclas)
        if d <= ventana and (mejor is None or d < mejor[0]):
            mejor = (d, f"{n} {unidad}{'s' if n != 1 else ''}")
    return mejor[1] if mejor else None


def regla_renovacion(frs):
    for f in frs:
        if re.search(r"(?i)\bperpetual\b", f):
            return "perpetual"
        v = (plazo_cerca(f, {"year", "month"},
                         [r"renew", r"extend", r"successive", r"additional term"])
             or plazo(f, {"year", "month"}))
        if v:
            return v
    return None

def regla_preaviso(frs):
    claves = [r"notice", r"non-?renewal", r"notif", r"prior to the (?:end|expir)"]
    for f in frs:                      # el preaviso casi siempre va en dias
        v = plazo_cerca(f, {"day"}, claves) or plazo_cerca(f, {"month"}, claves)
        if v:
            return v
    for f in frs:
        v = plazo(f, {"day"})
        if v:
            return v
    return None


TERMINO = re.compile(
    r"(?i)(?:for|of|continue[sd]?\s+for|period\s+of|term\s+of)\s+"
    r"(?:a\s+)?(?:(\d+)|([a-z]+(?:-[a-z]+)?))\s*(?:\(\s*(\d+)\s*\))?\s*"
    r"(month|year)s?\b")

def regla_vencimiento(frs, fecha_efectiva):
    """Expiration Date casi nunca esta escrita: se calcula.
    El contrato dice 'continue for five (5) years following the Effective Date'
    y el anotador anoto la fecha resultante."""
    from datetime import date
    texto = " ".join(frs)
    if re.search(r"(?i)end of the (?:then[- ])?current calendar year", texto) and fecha_efectiva:
        m, d, y = [int(x) for x in fecha_efectiva.split("/")]
        return f"12/31/{y:02d}"
    if not fecha_efectiva:
        return extrae_fecha(texto)
    m = TERMINO.search(texto)
    if not m:
        return extrae_fecha(texto)
    n = int(m.group(3) or m.group(1) or 0) or NUMEROS.get((m.group(2) or "").lower())
    if not n:
        return extrae_fecha(texto)
    mes, dia, anio = [int(x) for x in fecha_efectiva.split("/")]
    anio += 2000 if anio < 70 else 1900
    if m.group(4).lower() == "year":
        anio += n
    else:
        total = (mes - 1) + n
        anio += total // 12
        mes = total % 12 + 1
    try:
        date(anio, mes, dia)
    except ValueError:
        dia = 28
    return a_mmddyy(mes, dia, anio)

def regla_nombre(frs):
    return frs[0].strip() if frs else None

def regla_partes(frs):
    vistos, salida = set(), []
    for f in frs:
        f = f.strip()
        clave = re.sub(r"[^a-z0-9]", "", f.lower())
        if len(clave) > 3 and clave not in vistos:
            vistos.add(clave)
            salida.append(f)
    return "; ".join(salida) if salida else None

ESTADOS = ("Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware "
  "Florida Georgia Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky Louisiana Maine "
  "Maryland Massachusetts Michigan Minnesota Mississippi Missouri Montana Nebraska "
  "Nevada Ohio Oklahoma Oregon Pennsylvania Tennessee Texas Utah Vermont Virginia "
  "Washington Wisconsin Wyoming").split() + [
  "New York","New Jersey","New Mexico","New Hampshire","North Carolina","North Dakota",
  "South Carolina","South Dakota","Rhode Island","West Virginia","District of Columbia",
  "Ontario","Quebec","British Columbia","Alberta","England","Wales","Scotland",
  "Ireland","Singapore","Switzerland","Germany","France","Japan","China","India",
  "Israel","Netherlands","Australia","Canada","Korea","Hong Kong","Delaware",
  "Spain","Taiwan","Italy","Sweden","Norway","Denmark","Finland","Belgium",
  "Austria","Brazil","Mexico","Russia","Poland","Portugal","Greece","Turkey",
  "Luxembourg","Bermuda","Cayman Islands","New Zealand","South Africa",
  "United Kingdom","Puerto Rico","Manitoba","Saskatchewan","Nova Scotia"]
ESTADOS = sorted(set(ESTADOS), key=len, reverse=True)

def regla_ley(frs):
    texto = " ".join(frs)
    # 1) el nombre pegado a la frase de ley aplicable
    cerca = re.search(r"(?i)laws?\s+of\s+(?:the\s+)?(?:State|Commonwealth|Province)?"
                      r"\s*of\s*([A-Z][\w ]{2,30})", texto)
    if cerca:
        for e in ESTADOS:
            if cerca.group(1).strip().lower().startswith(e.lower()):
                return e
    # 2) cualquier jurisdiccion nombrada en el fragmento
    for e in ESTADOS:
        if re.search(r"\b" + re.escape(e) + r"\b", texto, re.I):
            return e
    return None

# ---------- comparadores -----------------------------------------------------
# En CUAD hay respuestas tachadas por confidencialidad: "[* * *]", "[]/[]/[][]"
REDACTADA = re.compile(r"[\[\]\*\s/\-]+")

UNIDAD_DIAS = {"day": 1, "week": 7, "month": 30, "year": 365}

def a_dias(texto):
    m = re.search(r"(?i)\b(\d+)\s*(day|week|month|year)s?\b", texto or "")
    return int(m.group(1)) * UNIDAD_DIAS[m.group(2).lower()] if m else None


def igual_texto(a, b):
    n = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()
    return n(a) == n(b)

def igual_fecha(pred, real):
    r = extrae_fecha(real or "")
    return bool(pred) and pred == r

def igual_contiene(pred, real):
    if not pred or not real:
        return False
    if pred.lower() in real.lower() or real.lower() in pred.lower():
        return True
    # "1 year" y "12 months" son el mismo plazo: la diferencia era del comparador,
    # no de la regla.
    dp, dr = a_dias(pred), a_dias(real)
    return dp is not None and dp == dr

def igual_partes(pred, real):
    if not pred or not real:
        return False
    limpia = lambda s: {re.sub(r"[^a-z0-9]", "", p.lower())
                        for p in re.split(r"[;]", re.sub(r"\(.*?\)", "", s)) if p.strip()}
    p, r = limpia(pred), limpia(real)
    if not r:
        return False
    return len(p & r) >= min(2, len(r))

REGLAS = [
    ("Document Name",                      regla_nombre,     igual_texto,     "regla"),
    ("Parties",                            regla_partes,     igual_partes,    "regla"),
    ("Agreement Date",                     regla_fecha,      igual_fecha,     "regla"),
    ("Effective Date",                     regla_fecha,      igual_fecha,     "regla"),
    ("Governing Law",                      regla_ley,        igual_contiene,  "regla"),
    ("Expiration Date",                    "derivada",       igual_fecha,     "derivada"),
    ("Renewal Term",                       regla_renovacion, igual_contiene,  "hibrido"),
    ("Notice Period To Terminate Renewal", regla_preaviso,   igual_contiene,  "hibrido"),
]

def main(ruta):
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta).read_text(encoding="utf-8-sig", errors="replace"))))
    print(f"contratos: {len(filas)}\n")
    print(f"{'categoria':36}{'cubeta':>10}{'con valor':>11}{'acierta':>9}{'%':>7}")
    resumen = []
    for cat, regla, compara, cubeta in REGLAS:
        col = columna_respuesta(filas[0], cat)
        con = ok = 0
        errores = []
        for fila in filas:
            real = (fila.get(col) or "").strip()
            if not real or REDACTADA.fullmatch(real):
                continue   # respuesta redactada en el corpus: no es decidible
            con += 1
            if regla == "derivada":
                efectiva = regla_fecha(fragmentos(fila.get("Effective Date")))
                pred = regla_vencimiento(fragmentos(fila.get(cat)), efectiva)
            else:
                pred = regla(fragmentos(fila.get(cat)))
            if compara(pred, real):
                ok += 1
            elif len(errores) < 3:
                errores.append((real[:38], (pred or "-")[:38]))
        pct = 100 * ok / con if con else 0.0
        resumen.append((cat, cubeta, con, ok, pct, errores))
        print(f"{cat:36}{cubeta:>10}{con:>11}{ok:>9}{pct:>6.1f}%")
    print("\n--- fallas de ejemplo (esperado | obtenido) ---")
    for cat, _, _, _, pct, errores in resumen:
        if pct < 95 and errores:
            print(f"\n{cat}")
            for real, pred in errores:
                print(f"   {real:40} | {pred}")
    return resumen

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "master_clauses.csv")
