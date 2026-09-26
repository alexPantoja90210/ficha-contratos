#!/usr/bin/env python3
"""Mide de PUNTA A PUNTA: localizar la clausula en el contrato crudo y normalizarla.

Compara contra `medir_reglas.py`, que partia del parrafo ya marcado por el
anotador. La diferencia entre ambas columnas es exactamente lo que cuesta
tener que encontrar la clausula uno mismo.

Uso:  python medir_e2e.py contratos.json master_clauses.csv
"""
import csv, io, json, sys
from pathlib import Path

import medir_reglas as R
from localizador import LocalizadorDeTexto
from reglas_texto import partes_de_texto

# categoria -> (regla, comparador, % medido con el parrafo ya localizado)
CASOS = [
    ("Document Name",                      R.regla_nombre,     R.igual_texto,    97.6),
    ("Governing Law",                      R.regla_ley,        R.igual_contiene, 95.1),
    ("Notice Period To Terminate Renewal", R.regla_preaviso,   R.igual_contiene, 87.0),
    ("Parties",                            partes_de_texto,    R.igual_partes,   86.4),
    ("Agreement Date",                     R.regla_fecha,      R.igual_fecha,    85.5),
    ("Effective Date",                     R.regla_fecha,      R.igual_fecha,    82.6),
    ("Renewal Term",                       R.regla_renovacion, R.igual_contiene, 61.3),
]

def main(ruta_json, ruta_csv):
    contratos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))

    # el csv nombra los contratos con extension .pdf; los textos son .txt
    def stem(n): return n[:-4] if n.lower().endswith(".pdf") else n
    faltan = sum(1 for f in filas if stem(f["Filename"]) not in contratos)
    print(f"contratos: {len(contratos)}   filas: {len(filas)}   sin cruce: {faltan}\n")

    print(f"{'categoria':36}{'con valor':>10}{'e2e':>8}{'solo normaliza':>16}{'costo':>8}")
    resumen = []
    for cat, regla, compara, base in CASOS:
        col = R.columna_respuesta(filas[0], cat)
        con = ok = 0
        for fila in filas:
            real = (fila.get(col) or "").strip()
            if not real or R.REDACTADA.fullmatch(real):
                continue
            texto = contratos.get(stem(fila["Filename"]))
            if texto is None:
                continue
            con += 1
            if compara(regla(LocalizadorDeTexto(texto).fragmentos(cat)), real):
                ok += 1
        pct = 100 * ok / con if con else 0.0
        resumen.append((cat, con, pct, base))
        print(f"{cat:36}{con:>10}{pct:>7.1f}%{base:>15.1f}%{pct-base:>+7.1f}")
    return resumen

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contratos.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
