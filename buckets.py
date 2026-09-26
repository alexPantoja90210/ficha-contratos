#!/usr/bin/env python3
"""Assigns each CUAD category to an extraction bucket.

Input:   category_descriptions.csv from the TheAtticusProject/cuad repository
Output:  categories.json  (consumed by the sheet)
         categories.csv   (for reading by eye)

The assignment is a design decision, not a measured result. Change it by editing
the tables at the top of this file.
"""
import csv, io, json, re, sys, collections
from pathlib import Path

# --- La decision. Editar aqui. -------------------------------------------
# regla      : la respuesta tiene forma verificable y aparece en sitio previsible
# hibrido    : la retrieval locates la clausula, la regla normalizes el value
# retrieval: pregunta de presence; el sistema marker encontrada/ausente solo
# humano     : pregunta de presence where un "ausente" equivocado cuesta caro;
#              el sistema propone, una persona confirma

RULE = {
    "Document Name": dict(
        where="Primeros 2000 caracteres",
        pattern=r"(?im)^\s*([A-Z][A-Z \-&']{6,})\s*$|\b([A-Z][\w ]*?AGREEMENT)\b",
        validates="cadena no vacia", measured_pct=97.6, measured_of=510),
    # movida a MODEL tras medir de punta a punta: 86.4% con el parrafo ya
    # localizado, 3.6% teniendo que sacarla del contract raw.
    "Parties (retirada de regla)": dict(
        where="Parrafo inicial",
        pattern=r"(?i)\b(?:by and between|between)\b(.{0,400}?)(?:\bwitnesseth\b|\brecitals\b|\n\n|\.\s+[A-Z])",
        validates="al menos 2 entidades", measured_pct=86.4, measured_of=509),
    "Agreement Date": dict(
        where="Parrafo inicial",
        pattern=r"(?i)\bdated(?:\s+as\s+of)?\s+(.{0,40}?\d{4})",
        validates="fecha parseable", measured_pct=85.5, measured_of=463),
    "Effective Date": dict(
        where="Parrafo inicial o definiciones",
        pattern=r"(?i)\beffective\s+(?:date|as\s+of)\b[^.]{0,60}?((?:\d{1,2}/\d{1,2}/\d{2,4})|(?:[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}))",
        validates="fecha parseable", measured_pct=82.6, measured_of=357),
    "Governing Law": dict(
        where="Clausula de ley aplicable",
        pattern=r"(?i)govern(?:ed|ing)\s+(?:by|law).{0,120}?\b(?:State|Commonwealth|Province|laws)\s+of\s+([A-Z][\w ]+)",
        validates="value inside del catalogo de estados/paises", measured_pct=95.1, measured_of=432),
}

HYBRID = {
    "Notice Period to Terminate Renewal": dict(
        locates="clausula de terminacion de la renovacion",
        normalizes="term_in mas cercano a 'notice'/'non-renewal', unidad dias",
        validates="numero + unidad",
        measured_pct=87.0, measured_of=100),
}

# Medidas contra los 510 contracts de master_clauses.csv. No close on their own.
DERIVED_OR_WEAK = {
    "Expiration Date": dict(
        note="No esta escrita: se calcula sobre Effective Date + term_in del termino. "
             "El error se acumula sobre Effective Date (82.6%).",
        measured_pct=34.4, measured_of=326),
    "Renewal Term": dict(
        note="Respuestas multivaluadas ('perpetual', '7/22/2019; 7/22/2022') y "
             "plazos que compiten inside del mismo parrafo.",
        measured_pct=61.3, measured_of=163),
}

# Yes/No where un "ausente" equivocado cambia la economia del trato
# o frena la transaccion -> no se cierra sin persona.
HUMAN = {
    "Cap on Liability", "Uncapped Liability", "Liquidated Damages",
    "IP Ownership Assignment", "Joint IP Ownership", "Source Code Escrow",
    "Change of Control", "Anti-Assignment", "Non-Compete", "Exclusivity",
    "Most Favored Nation", "Minimum Commitment",
} | set(DERIVED_OR_WEAK)

# Categorias where la regla se midio y perdio: aqui un modelo si se gana su hora.
MODEL = {
    "Parties": dict(
        note="Las entidades vienen enredadas con domicilios, descriptores "
             "societarios y alias. Regla: 3.6% de punta a punta. Un modelo "
             "leyendo la primera pagina resuelve esto sin esfuerzo.",
        measured_pct=3.6, measured_of=497),
}
# --------------------------------------------------------------------------

def strip_prefix(value: str) -> str:
    return re.sub(r"^[A-Za-z ()incl.]+:\s*", "", value).strip()

def bucket_of(name: str) -> str:
    if name in MODEL:  return "modelo"
    if name in RULE:   return "rule"
    if name in HYBRID: return "hibrido"
    if name in HUMAN:  return "humano"
    return "retrieval"

def main(source_path: Path, dest_dir: Path) -> int:
    rows = list(csv.reader(io.StringIO(source_path.read_text(encoding="utf-8-sig"))))
    if not rows:
        print("csv vacio", file=sys.stderr); return 1
    data = rows[1:]

    out = []
    for row in data:
        name = strip_prefix(row[0])
        c = bucket_of(name)
        record = {
            "category": name,
            "description": strip_prefix(row[1]),
            "cuad_format": strip_prefix(row[2]) or None,
            "cuad_group": strip_prefix(row[3]) if len(row) > 3 else None,
            "bucket": c,
            "closes_alone": c != "humano",
        }
        record.update(RULE.get(name, {}))
        record.update(HYBRID.get(name, {}))
        record.update(DERIVED_OR_WEAK.get(name, {}))
        record.update(MODEL.get(name, {}))
        out.append(record)

    if len(out) != 41:
        print(f"warning: expected 41 categories, found {len(out)}", file=sys.stderr)

    missing = (set(RULE) | set(HYBRID) | HUMAN) - {r["category"] for r in out}
    if missing:
        print(f"warning: assigned names absent from the csv: {sorted(missing)}", file=sys.stderr)

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "categories.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    with (dest_dir / "categories.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "cuad_format", "cuad_group", "bucket", "closes_alone"])
        for r in out:
            w.writerow([r["category"], r["cuad_format"], r["cuad_group"],
                        r["bucket"], r["closes_alone"]])

    counts = collections.Counter(r["bucket"] for r in out)
    for k in ("rule", "hibrido", "modelo", "retrieval", "humano"):
        print(f"{k:14} {counts[k]:2}")
    print(f"{'total':14} {sum(counts.values()):2}")
    print(f"close on their own  {sum(1 for r in out if r['closes_alone']):2}")
    return 0

if __name__ == "__main__":
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("category_descriptions.csv")
    dest_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    raise SystemExit(main(source_path, dest_dir))
