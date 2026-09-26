#!/usr/bin/env python3
"""Calcula el PISO TRIVIAL de cada categoria de presencia de CUAD.

El piso trivial es lo que saca un sistema que siempre responde la clase
mayoritaria -- normalmente "No, esa clausula no esta". Cualquier resultado
por debajo de ese piso vale menos que no hacer nada.

Existe para una sola cosa: impedir que publiquemos un numero que parece
bueno y no lo es. Correrlo ANTES de construir, no despues.

Uso:  python piso_trivial.py master_clauses.csv [salida.csv]
"""
import csv, io, sys
from pathlib import Path

AVISO_SESGO = 75.0     # por encima: la exactitud deja de ser informativa
UTIL        = 65.0     # por debajo: un numero de exactitud si significa algo

def columna_respuesta(fila, categoria):
    for suf in ("-Answer", "- Answer"):
        if categoria + suf in fila:
            return categoria + suf
    return None

def main(ruta, salida=None):
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta).read_text(encoding="utf-8-sig", errors="replace"))))
    reporte = []
    for cat in list(filas[0]):
        if cat.endswith("-Answer") or cat.endswith("- Answer") or cat == "Filename":
            continue
        col = columna_respuesta(filas[0], cat)
        if not col:
            continue
        vals = [(f.get(col) or "").strip() for f in filas]
        vals = [v for v in vals if v]
        if not vals or not set(vals) <= {"Yes", "No"}:
            continue
        si, no = vals.count("Yes"), vals.count("No")
        piso = 100 * max(si, no) / len(vals)
        reporte.append({
            "categoria": cat,
            "si": si, "no": no, "total": len(vals),
            "piso_trivial_pct": round(piso, 1),
            "clase_mayoritaria": "Yes" if si >= no else "No",
            # con clase minoritaria escasa, la exactitud miente: lo que importa
            # es cuantas de las que SI estan logramos encontrar
            "metrica_valida": "exactitud" if piso < UTIL else "recall_clase_minoritaria",
            "confirmaciones_humanas": min(si, no),
        })
    reporte.sort(key=lambda r: -r["piso_trivial_pct"])

    ancho = max(len(r["categoria"]) for r in reporte)
    print(f"{'categoria':{ancho}}{'Yes':>6}{'No':>6}{'piso':>8}  metrica valida")
    for r in reporte:
        print(f"{r['categoria']:{ancho}}{r['si']:>6}{r['no']:>6}"
              f"{r['piso_trivial_pct']:>7.1f}%  {r['metrica_valida']}")

    pisos = [r["piso_trivial_pct"] for r in reporte]
    print(f"\ncategorias de presencia        : {len(reporte)}")
    print(f"piso trivial promedio          : {sum(pisos)/len(pisos):.1f}%")
    print(f"con sesgo >= {AVISO_SESGO:.0f}% (exactitud miente): "
          f"{sum(1 for p in pisos if p >= AVISO_SESGO)}")
    print(f"balanceadas (< {UTIL:.0f}%, exactitud sirve): "
          f"{sum(1 for p in pisos if p < UTIL)}")
    print(f"confirmaciones humanas si se confirma solo la clase escasa: "
          f"{sum(r['confirmaciones_humanas'] for r in reporte)} de "
          f"{len(reporte)*len(filas)} celdas")

    print("\nREGLA: no publicar exactitud promediada entre categorias. "
          "Reportar por categoria\nel avance sobre su piso, y en las sesgadas "
          "el recall de la clase minoritaria.")

    if salida:
        with open(salida, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(reporte[0]))
            w.writeheader()
            w.writerows(reporte)
        print(f"\nescrito: {salida}")
    return reporte

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "master_clauses.csv",
         sys.argv[2] if len(sys.argv) > 2 else "piso_trivial.csv")
