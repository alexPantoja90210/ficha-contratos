#!/usr/bin/env python3
"""Paso 0 - Asigna cada categoria de CUAD a una cubeta de extraccion.

Entrada:  category_descriptions.csv del repositorio TheAtticusProject/cuad
Salida:   categorias_cubetas.json  (lo consume la Rebanada 2)
          categorias_cubetas.csv   (para revisar a ojo)

La asignacion es una decision de diseno, no un resultado medido.
Se cambia editando CUBETAS aqui abajo.
"""
import csv, io, json, re, sys, collections
from pathlib import Path

# --- La decision. Editar aqui. -------------------------------------------
# regla      : la respuesta tiene forma verificable y aparece en sitio previsible
# hibrido    : la recuperacion localiza la clausula, la regla normaliza el valor
# recuperacion: pregunta de presencia; el sistema marca encontrada/ausente solo
# humano     : pregunta de presencia donde un "ausente" equivocado cuesta caro;
#              el sistema propone, una persona confirma

REGLA = {
    "Document Name": dict(
        donde="Primeros 2000 caracteres",
        patron=r"(?im)^\s*([A-Z][A-Z \-&']{6,})\s*$|\b([A-Z][\w ]*?AGREEMENT)\b",
        valida="cadena no vacia", medido_pct=97.6, medido_de=510),
    # movida a MODELO tras medir de punta a punta: 86.4% con el parrafo ya
    # localizado, 3.6% teniendo que sacarla del contrato crudo.
    "Parties (retirada de regla)": dict(
        donde="Parrafo inicial",
        patron=r"(?i)\b(?:by and between|between)\b(.{0,400}?)(?:\bwitnesseth\b|\brecitals\b|\n\n|\.\s+[A-Z])",
        valida="al menos 2 entidades", medido_pct=86.4, medido_de=509),
    "Agreement Date": dict(
        donde="Parrafo inicial",
        patron=r"(?i)\bdated(?:\s+as\s+of)?\s+(.{0,40}?\d{4})",
        valida="fecha parseable", medido_pct=85.5, medido_de=463),
    "Effective Date": dict(
        donde="Parrafo inicial o definiciones",
        patron=r"(?i)\beffective\s+(?:date|as\s+of)\b[^.]{0,60}?((?:\d{1,2}/\d{1,2}/\d{2,4})|(?:[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}))",
        valida="fecha parseable", medido_pct=82.6, medido_de=357),
    "Governing Law": dict(
        donde="Clausula de ley aplicable",
        patron=r"(?i)govern(?:ed|ing)\s+(?:by|law).{0,120}?\b(?:State|Commonwealth|Province|laws)\s+of\s+([A-Z][\w ]+)",
        valida="valor dentro del catalogo de estados/paises", medido_pct=95.1, medido_de=432),
}

HIBRIDO = {
    "Notice Period to Terminate Renewal": dict(
        localiza="clausula de terminacion de la renovacion",
        normaliza="plazo mas cercano a 'notice'/'non-renewal', unidad dias",
        valida="numero + unidad",
        medido_pct=87.0, medido_de=100),
}

# Medidas contra los 510 contratos de master_clauses.csv. No cierran solas.
DERIVADA_O_DEBIL = {
    "Expiration Date": dict(
        nota="No esta escrita: se calcula sobre Effective Date + plazo del termino. "
             "El error se acumula sobre Effective Date (82.6%).",
        medido_pct=34.4, medido_de=326),
    "Renewal Term": dict(
        nota="Respuestas multivaluadas ('perpetual', '7/22/2019; 7/22/2022') y "
             "plazos que compiten dentro del mismo parrafo.",
        medido_pct=61.3, medido_de=163),
}

# Yes/No donde un "ausente" equivocado cambia la economia del trato
# o frena la transaccion -> no se cierra sin persona.
HUMANO = {
    "Cap on Liability", "Uncapped Liability", "Liquidated Damages",
    "IP Ownership Assignment", "Joint IP Ownership", "Source Code Escrow",
    "Change of Control", "Anti-Assignment", "Non-Compete", "Exclusivity",
    "Most Favored Nation", "Minimum Commitment",
} | set(DERIVADA_O_DEBIL)

# Categorias donde la regla se midio y perdio: aqui un modelo si se gana su hora.
MODELO = {
    "Parties": dict(
        nota="Las entidades vienen enredadas con domicilios, descriptores "
             "societarios y alias. Regla: 3.6% de punta a punta. Un modelo "
             "leyendo la primera pagina resuelve esto sin esfuerzo.",
        medido_pct=3.6, medido_de=497),
}
# --------------------------------------------------------------------------

def strip_prefix(value: str) -> str:
    return re.sub(r"^[A-Za-z ()incl.]+:\s*", "", value).strip()

def cubeta(nombre: str) -> str:
    if nombre in MODELO:  return "modelo"
    if nombre in REGLA:   return "regla"
    if nombre in HIBRIDO: return "hibrido"
    if nombre in HUMANO:  return "humano"
    return "recuperacion"

def main(origen: Path, destino: Path) -> int:
    filas = list(csv.reader(io.StringIO(origen.read_text(encoding="utf-8-sig"))))
    if not filas:
        print("csv vacio", file=sys.stderr); return 1
    datos = filas[1:]

    salida = []
    for fila in datos:
        nombre = strip_prefix(fila[0])
        c = cubeta(nombre)
        registro = {
            "categoria": nombre,
            "descripcion": strip_prefix(fila[1]),
            "formato_cuad": strip_prefix(fila[2]) or None,
            "grupo_cuad": strip_prefix(fila[3]) if len(fila) > 3 else None,
            "cubeta": c,
            "cierra_solo": c != "humano",
        }
        registro.update(REGLA.get(nombre, {}))
        registro.update(HIBRIDO.get(nombre, {}))
        registro.update(DERIVADA_O_DEBIL.get(nombre, {}))
        registro.update(MODELO.get(nombre, {}))
        salida.append(registro)

    if len(salida) != 41:
        print(f"aviso: se esperaban 41 categorias, hay {len(salida)}", file=sys.stderr)

    faltan = (set(REGLA) | set(HIBRIDO) | HUMANO) - {r["categoria"] for r in salida}
    if faltan:
        print(f"aviso: nombres asignados que no existen en el csv: {sorted(faltan)}", file=sys.stderr)

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "categorias_cubetas.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    with (destino / "categorias_cubetas.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["categoria", "formato_cuad", "grupo_cuad", "cubeta", "cierra_solo"])
        for r in salida:
            w.writerow([r["categoria"], r["formato_cuad"], r["grupo_cuad"],
                        r["cubeta"], r["cierra_solo"]])

    cuenta = collections.Counter(r["cubeta"] for r in salida)
    for k in ("regla", "hibrido", "modelo", "recuperacion", "humano"):
        print(f"{k:14} {cuenta[k]:2}")
    print(f"{'total':14} {sum(cuenta.values()):2}")
    print(f"cierran solas  {sum(1 for r in salida if r['cierra_solo']):2}")
    return 0

if __name__ == "__main__":
    origen = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("category_descriptions.csv")
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    raise SystemExit(main(origen, destino))
