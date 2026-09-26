#!/usr/bin/env python3
"""El alcance del producto, decidido por medicion y no por gusto.

Una categoria entra a la ficha solo si puede cerrarse sola con evidencia:

  por regla      acierto de punta a punta >= 65% sobre los 510 contratos
  por presencia  exactitud balanceada >= 70% Y recall >= 70% en la particion
                 de prueba, y umbral calibrable
  ademas, toda   debe ganarle al PARSEO INGENUO (baseline_ingenuo.py): la
                 primera linea, la primera fecha, el primer estado nombrado,
                 o "no esta" siempre. Una categoria que no le gana a eso no
                 justifica existir, por buena que se vea su balanceada.

Recall entra en el criterio a proposito: una categoria que detecta bien pero
se le escapan las que si estan no puede afirmar ausencia, y una ficha que no
puede decir "no esta" no sirve para revisar un contrato.

Lo que no pasa el corte no se borra: queda fuera del alcance, listado, con su
numero. Un alcance es una decision defendible, no una lista de lo que salio.
"""
import json
from pathlib import Path

MINIMO_REGLA      = 65.0
MINIMO_BALANCEADA = 70.0
MINIMO_RECALL     = 70.0

# Acierto del parseo ingenuo y del producto, misma particion de prueba.
# Fuente: baseline_ingenuo.py y medir_ficha.py.
INGENUO = {
    "Document Name": 5, "Governing Law": 38, "Cap On Liability": 42,
    "Agreement Date": 53, "License Grant": 55, "Audit Rights": 56,
    "Effective Date": 50, "Insurance": 65, "No-Solicit Of Employees": 90,
    "Warranty Duration": 83,
}
PRODUCTO = {
    "Document Name": 66, "Governing Law": 90, "Cap On Liability": 86,
    "Agreement Date": 74, "License Grant": 76, "Audit Rights": 73,
    "Effective Date": 67, "Insurance": 76, "No-Solicit Of Employees": 80,
    "Warranty Duration": 76,
}

def le_gana_al_ingenuo(cat):
    """None cuando no hay medicion del ingenuo para esa categoria."""
    if cat not in INGENUO:
        return None
    return PRODUCTO[cat] > INGENUO[cat]

# acierto de punta a punta medido en medir_e2e.py
REGLAS_MEDIDAS = {
    "Governing Law":                      91.7,
    "Agreement Date":                     73.6,
    "Document Name":                      71.9,
    "Effective Date":                      68.0,
    "Notice Period to Terminate Renewal":  61.2,
    "Renewal Term":                        60.6,
    "Parties":                              5.8,
}

def decidir(ruta="recuperacion_resultados.json"):
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    perf = {r["categoria"]: r for r in d["test"]}

    dentro, fuera = [], []
    for cat, pct in REGLAS_MEDIDAS.items():
        fila = dict(categoria=cat, motor="regla", medida=pct, criterio="acierto e2e",
                    ingenuo=INGENUO.get(cat))
        gana = le_gana_al_ingenuo(cat)
        (dentro if pct >= MINIMO_REGLA and gana is not False else fuera).append(fila)

    for cat, r in perf.items():
        fila = dict(categoria=cat, motor="presencia", medida=r["balanceada"],
                    recall=r["recall"], criterio="balanceada y recall",
                    ingenuo=INGENUO.get(cat))
        gana = le_gana_al_ingenuo(cat)
        if (r["balanceada"] >= MINIMO_BALANCEADA and r["recall"] >= MINIMO_RECALL
                and gana is not False):
            dentro.append(fila)
        else:
            fuera.append(fila)

    dentro.sort(key=lambda f: -f["medida"])
    fuera.sort(key=lambda f: -f["medida"])
    return dentro, fuera

if __name__ == "__main__":
    dentro, fuera = decidir()
    print(f"DENTRO DEL ALCANCE ({len(dentro)})")
    for f in dentro:
        ing = f"  ingenuo {f['ingenuo']}%" if f.get("ingenuo") is not None else ""
        print(f"  {f['categoria']:36}{f['motor']:11}{f['medida']:5.1f}%{ing}")
    print(f"\nFUERA ({len(fuera)}) -- con su numero, para que la decision se pueda discutir")
    for f in fuera:
        rec = f"  recall {f['recall']:.0f}%" if "recall" in f else ""
        ing = (f"  PIERDE contra el ingenuo ({f['ingenuo']}%)"
               if f.get("ingenuo") is not None and PRODUCTO.get(f["categoria"], 0) <= f["ingenuo"]
               else "")
        print(f"  {f['categoria']:36}{f['motor']:11}{f['medida']:5.1f}%{rec}{ing}")
