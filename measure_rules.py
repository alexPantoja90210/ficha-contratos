#!/usr/bin/env python3
"""Measures the extraction rules against CUAD's master_clauses.csv.

What it measures and what it does not
-------------------------------------
master_clauses.csv holds, per contract and category, the FRAGMENT the annotator
marked and the normalized ANSWER they wrote. This script hands each rule the
already-located fragment and compares its output against the answer.

  Measures     : the NORMALIZATION half (fragment to value).
  Does NOT     : the LOCATION half (finding the fragment in the contract), because
                 this file does not carry the full contracts.

A high percentage here does not say the rule works on a raw contract. It says that,
once in front of the right paragraph, it pulls out the right value.

Usage:  python measure_rules.py master_clauses.csv
"""
import ast, csv, io, re, sys
from pathlib import Path

# ---------- lectura ----------------------------------------------------------
def fragments(cell):
    cell = (cell or "").strip()
    if not cell:
        return []
    try:
        v = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return [cell]
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]

def answer_column(row, category):
    for suf in ("-Answer", "- Answer"):
        if category + suf in row:
            return category + suf
    return None

# ---------- normalizadores ---------------------------------------------------
MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}

DATE_LONG = re.compile(
    r"(?i)\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b")
DATE_ORDINAL = re.compile(
    r"(?i)\b(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b")
DATE_SLASHES = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
# "1 August 2019", "20t h day of November, 2018" (noise de OCR en el ordinal)
DATE_DAY_MONTH = re.compile(
    r"(?i)\b(\d{1,2})\s*(?:st|nd|rd|th|t\s*h)?\s*(?:day\s+of\s+)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(\d{4})\b")

def to_mmddyy(mes, dia, anio):
    anio = int(anio)
    if anio > 100:
        anio %= 100
    return f"{int(mes)}/{int(dia)}/{anio:02d}"

def extract_date(text):
    m = DATE_ORDINAL.search(text)
    if m:
        return to_mmddyy(MONTHS[m.group(2)[:3].lower()], m.group(1), m.group(3))
    m = DATE_LONG.search(text)
    if m:
        return to_mmddyy(MONTHS[m.group(1)[:3].lower()], m.group(2), m.group(3))
    m = DATE_DAY_MONTH.search(text)
    if m:
        return to_mmddyy(MONTHS[m.group(2)[:3].lower()], m.group(1), m.group(3))
    m = DATE_SLASHES.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 >= b:          # 29/3/18 viene en dia/mes/anio
            a, b = b, a
        return to_mmddyy(a, b, m.group(3))
    return None

def rule_date(frs):
    for f in frs:
        v = extract_date(f)
        if v:
            return v
    return None

NUMBERS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
           "eight":8,"nine":9,"ten":10,"twelve":12,"fifteen":15,"twenty":20,
           "thirty":30,"forty":40,"forty-five":45,"sixty":60,"ninety":90,
           "hundred":100,"eighteen":18,"twenty-four":24,"thirty-six":36}
# "two (2) years" -> el digito entre parentesis manda sobre la palabra
TERM_RE = re.compile(
    r"(?i)\b(?:(\d+)|([a-z]+(?:-[a-z]+)?))\s*(?:\(\s*(\d+)\s*\))?\s*"
    r"(day|week|month|year)s?\b")

def term_in(text, unidades):
    for m in TERM_RE.finditer(text):
        unidad = m.group(4).lower()
        if unidad not in unidades:
            continue
        if m.group(3):
            n = int(m.group(3))
        elif m.group(1):
            n = int(m.group(1))
        else:
            n = NUMBERS.get(m.group(2).lower())
        if n:
            return f"{n} {unidad}{'s' if n != 1 else ''}"
    return None

def term_near(text, unidades, claves, ventana=160):
    """El term_in mas cercano a una de las palabras key_of. El parrafo suele traer
    varios (el termino de renovacion y el preaviso); el primero no es el bueno."""
    anclas = [m.start() for c in claves
              for m in re.finditer(c, text, re.I)]
    if not anclas:
        return None
    best = None
    for m in TERM_RE.finditer(text):
        unidad = m.group(4).lower()
        if unidad not in unidades:
            continue
        if m.group(3):
            n = int(m.group(3))
        elif m.group(1):
            n = int(m.group(1))
        else:
            n = NUMBERS.get((m.group(2) or "").lower())
        if not n:
            continue
        d = min(abs(m.start() - a) for a in anclas)
        if d <= ventana and (best is None or d < best[0]):
            best = (d, f"{n} {unidad}{'s' if n != 1 else ''}")
    return best[1] if best else None


def rule_renewal(frs):
    for f in frs:
        if re.search(r"(?i)\bperpetual\b", f):
            return "perpetual"
        v = (term_near(f, {"year", "month"},
                         [r"renew", r"extend", r"successive", r"additional term"])
             or term_in(f, {"year", "month"}))
        if v:
            return v
    return None

def rule_notice(frs):
    claves = [r"notice", r"non-?renewal", r"notif", r"prior to the (?:end|expir)"]
    for f in frs:                      # el preaviso casi siempre va en dias
        v = term_near(f, {"day"}, claves) or term_near(f, {"month"}, claves)
        if v:
            return v
    for f in frs:
        v = term_in(f, {"day"})
        if v:
            return v
    return None


TERM_OF_RE = re.compile(
    r"(?i)(?:for|of|continue[sd]?\s+for|period\s+of|term\s+of)\s+"
    r"(?:a\s+)?(?:(\d+)|([a-z]+(?:-[a-z]+)?))\s*(?:\(\s*(\d+)\s*\))?\s*"
    r"(month|year)s?\b")

def rule_expiration(frs, fecha_efectiva):
    """Expiration Date casi nunca esta escrita: se calcula.
    El contract dice 'continue for five (5) years following the Effective Date'
    y el anotador anoto la fecha resultante."""
    from datetime import date
    text = " ".join(frs)
    if re.search(r"(?i)end of the (?:then[- ])?current calendar year", text) and fecha_efectiva:
        m, d, y = [int(x) for x in fecha_efectiva.split("/")]
        return f"12/31/{y:02d}"
    if not fecha_efectiva:
        return extract_date(text)
    m = TERM_OF_RE.search(text)
    if not m:
        return extract_date(text)
    n = int(m.group(3) or m.group(1) or 0) or NUMBERS.get((m.group(2) or "").lower())
    if not n:
        return extract_date(text)
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
    return to_mmddyy(mes, dia, anio)

# A title is mostly letters and holds at least one real word. Without this the
# rule happily returns control characters, an HTML tag or a single byte: it
# cannot crash, but it asserts nonsense, which is the worse failure.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def looks_like_title(text):
    t = CONTROL.sub("", text or "").strip()
    if len(t) < 8 or len(t) > 200 or "<" in t or ">" in t:
        return None
    letters = sum(c.isalpha() or c.isspace() for c in t)
    if letters / len(t) < 0.6:
        return None
    if not re.search(r"[A-Za-z]{3,}", t):
        return None
    return t

def rule_name(frs):
    return looks_like_title(frs[0]) if frs else None

def rule_parties(frs):
    seen, out = set(), []
    for f in frs:
        f = f.strip()
        key_of = re.sub(r"[^a-z0-9]", "", f.lower())
        if len(key_of) > 3 and key_of not in seen:
            seen.add(key_of)
            out.append(f)
    return "; ".join(out) if out else None

JURISDICTIONS = ("Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware "
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
# Se held-outn de mas largo a mas corto para que "New York" gane sobre "York".
# El desempate va por el nombre: sorted() sobre un set hereda el orden de
# iteracion del set, y Python aleatoriza el hash de cadenas por proceso, asi
# que sin esto dos jurisdicciones del mismo largo se alternan entre corridas
# y la cifra medida cambia sola.
JURISDICTIONS = sorted(set(JURISDICTIONS), key=lambda j: (-len(j), j))

def rule_law(frs):
    text = " ".join(frs)
    # 1) el name pegado a la frase de ley aplicable
    cerca = re.search(r"(?i)laws?\s+of\s+(?:the\s+)?(?:State|Commonwealth|Province)?"
                      r"\s*of\s*([A-Z][\w ]{2,30})", text)
    if cerca:
        for e in JURISDICTIONS:
            if cerca.group(1).strip().lower().startswith(e.lower()):
                return e
    # 2) cualquier jurisdiccion nombrada en el fragment
    for e in JURISDICTIONS:
        if re.search(r"\b" + re.escape(e) + r"\b", text, re.I):
            return e
    return None

# ---------- comparadores -----------------------------------------------------
# En CUAD hay respuestas tachadas por confidencialidad: "[* * *]", "[]/[]/[][]"
REDACTED = re.compile(r"[\[\]\*\s/\-]+")

DAYS_PER_UNIT = {"day": 1, "week": 7, "month": 30, "year": 365}

def to_days(text):
    m = re.search(r"(?i)\b(\d+)\s*(day|week|month|year)s?\b", text or "")
    return int(m.group(1)) * DAYS_PER_UNIT[m.group(2).lower()] if m else None


def same_text(a, b):
    n = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()
    return n(a) == n(b)

def same_date(pred, real):
    r = extract_date(real or "")
    return bool(pred) and pred == r

def same_contains(pred, real):
    if not pred or not real:
        return False
    if pred.lower() in real.lower() or real.lower() in pred.lower():
        return True
    # "1 year" y "12 months" son el mismo term_in: la diferencia era del comparador,
    # no de la regla.
    dp, dr = to_days(pred), to_days(real)
    return dp is not None and dp == dr

def same_parties(pred, real):
    if not pred or not real:
        return False
    limpia = lambda s: {re.sub(r"[^a-z0-9]", "", p.lower())
                        for p in re.split(r"[;]", re.sub(r"\(.*?\)", "", s)) if p.strip()}
    p, r = limpia(pred), limpia(real)
    if not r:
        return False
    return len(p & r) >= min(2, len(r))

RULES = [
    ("Document Name",                      rule_name,     same_text,     "rule"),
    ("Parties",                            rule_parties,     same_parties,    "rule"),
    ("Agreement Date",                     rule_date,      same_date,     "rule"),
    ("Effective Date",                     rule_date,      same_date,     "rule"),
    ("Governing Law",                      rule_law,        same_contains,  "rule"),
    ("Expiration Date",                    "derivada",       same_date,     "derivada"),
    ("Renewal Term",                       rule_renewal, same_contains,  "hibrido"),
    ("Notice Period To Terminate Renewal", rule_notice,   same_contains,  "hibrido"),
]

def main(path):
    rows = list(csv.DictReader(io.StringIO(
        Path(path).read_text(encoding="utf-8-sig", errors="replace"))))
    print(f"contracts: {len(rows)}\n")
    print(f"{'category':36}{'bucket':>10}{'with value':>11}{'correct':>9}{'%':>7}")
    summary = []
    for cat, regla, compara, bucket_of in RULES:
        col = answer_column(rows[0], cat)
        con = ok = 0
        failures = []
        for row in rows:
            real = (row.get(col) or "").strip()
            if not real or REDACTED.fullmatch(real):
                continue   # respuesta redactada en el corpus: no es decidible
            con += 1
            if regla == "derivada":
                efectiva = rule_date(fragments(row.get("Effective Date")))
                pred = rule_expiration(fragments(row.get(cat)), efectiva)
            else:
                pred = regla(fragments(row.get(cat)))
            if compara(pred, real):
                ok += 1
            elif len(failures) < 3:
                failures.append((real[:38], (pred or "-")[:38]))
        pct = 100 * ok / con if con else 0.0
        summary.append((cat, bucket_of, con, ok, pct, failures))
        print(f"{cat:36}{bucket_of:>10}{con:>11}{ok:>9}{pct:>6.1f}%")
    print("\n--- sample failures (expected | produced) ---")
    for cat, _, _, _, pct, failures in summary:
        if pct < 95 and failures:
            print(f"\n{cat}")
            for real, pred in failures:
                print(f"   {real:40} | {pred}")
    return summary

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "master_clauses.csv")
