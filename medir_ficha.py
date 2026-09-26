#!/usr/bin/env python3
"""Mide la ficha COMPLETA, renglon por renglon, sobre contratos nunca vistos.

Las mediciones anteriores eran por categoria. Esta es por ficha: de los
renglones que se pueden juzgar, cuantos salen bien en el mismo contrato.
Es lo que le pasa a un usuario, que no lee una categoria sino una hoja.

Uso:  python medir_ficha.py contratos.json master_clauses.csv
"""
import ast, csv, io, json, sys
from collections import Counter
from pathlib import Path

import medir_reglas as R
from localizador import LocalizadorDeTexto, clave
from presencia import DetectorDePresencia
from alcance import decidir

COMPARADOR = {
    "document name":  (R.regla_nombre, R.igual_texto),
    "governing law":  (R.regla_ley,    R.igual_contiene),
    "agreement date": (R.regla_fecha,  R.igual_fecha),
    "effective date": (R.regla_fecha,  R.igual_fecha),
}

def columna(fila, cat):
    k = clave(cat)
    for c in fila:
        if c.endswith("-Answer") or c.endswith("- Answer"):
            if clave(c.replace("- Answer", "").replace("-Answer", "")) == k:
                return c
    return None

def span(fila, cat):
    k = clave(cat)
    for c in fila:
        if c.endswith("Answer"):
            continue
        if clave(c) == k:
            celda = (fila.get(c) or "").strip()
            try:
                v = ast.literal_eval(celda) if celda else []
            except (ValueError, SyntaxError):
                v = [celda] if celda else []
            return bool(v)
    return None

def main(ruta_json, ruta_csv):
    contratos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n

    dentro, _ = decidir()
    det = DetectorDePresencia()
    nombres_prueba = set(sorted(contratos)[int(len(contratos) * 0.8):])

    por_cat = {f["categoria"]: [0, 0] for f in dentro}
    por_ficha, total_renglones = [], 0

    for fila in filas:
        nom = stem(fila["Filename"])
        texto = contratos.get(nom)
        if texto is None or nom not in nombres_prueba:
            continue
        loc = LocalizadorDeTexto(texto)
        bien = juzgables = 0
        for f in dentro:
            cat = f["categoria"]
            if f["motor"] == "regla":
                col = columna(filas[0], cat)
                real = (fila.get(col) or "").strip() if col else ""
                if not real or R.REDACTADA.fullmatch(real):
                    continue
                regla, cmp_ = COMPARADOR[clave(cat)]
                ok = cmp_(regla(loc.fragmentos(cat)), real)
            else:
                real = span(fila, cat)
                if real is None:
                    continue
                estado, _, _ = det.evaluar(cat, texto)
                ok = (estado == "encontrada") == real
            juzgables += 1
            bien += ok
            por_cat[cat][0] += ok
            por_cat[cat][1] += 1
        if juzgables:
            por_ficha.append((bien, juzgables))
            total_renglones += juzgables

    print(f"contratos de prueba juzgados: {len(por_ficha)}")
    print(f"renglones juzgados en total : {total_renglones}\n")

    print(f"{'categoria':36}{'motor':11}{'bien':>6}{'de':>5}{'%':>7}")
    for f in dentro:
        b, n = por_cat[f["categoria"]]
        if n:
            print(f"{f['categoria']:36}{f['motor']:11}{b:>6}{n:>5}{100*b/n:>6.0f}%")

    bien_tot = sum(b for b, _ in por_ficha)
    print(f"\nrenglones correctos: {bien_tot}/{total_renglones} = "
          f"{100*bien_tot/total_renglones:.1f}%")

    dist = Counter(round(10 * b / n) for b, n in por_ficha)
    print("\nfichas por proporcion de renglones correctos:")
    acum = 0
    for k in sorted(dist, reverse=True):
        acum += dist[k]
        barra = "#" * dist[k]
        print(f"  {k*10:>3}% {dist[k]:>4} fichas  {barra}")
    perfectas = sum(1 for b, n in por_ficha if b == n)
    print(f"\nfichas sin un solo error: {perfectas} de {len(por_ficha)} "
          f"({100*perfectas/len(por_ficha):.0f}%)")
    ocho = sum(1 for b, n in por_ficha if b / n >= 0.8)
    print(f"fichas con 80% o mas correcto: {ocho} ({100*ocho/len(por_ficha):.0f}%)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contratos.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
