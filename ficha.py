#!/usr/bin/env python3
"""Ficha de revision de un contrato: las 41 clausulas, cuales estan y cuales no.

Recibe el TEXTO COMPLETO de un contrato y devuelve 41 entradas con estado,
valor, confianza medida y -- cuando se puede prometer -- donde esta.

Dos motores detras de la misma ficha:
  LocalizadorDeTexto   reglas sobre 6 categorias tipadas (fechas, ley, titulo)
  DetectorDePresencia  recuperacion por terminos sobre las 33 de presencia

Estados
-------
  encontrada              resuelta, cierra sola
  ausente                 no esta, y el recall medido respalda afirmarlo
  por_confirmar           hay candidata o la categoria es cara: la ve una persona
  ausente_por_confirmar   parece no estar, pero el detector no ve lo bastante
                          como para afirmarlo
  pendiente_modelo        la regla se midio y perdio; toca a un modelo

Uso:  python ficha.py contratos.json [indice]
"""
import json, sys
from pathlib import Path

import medir_reglas as R
from localizador import LocalizadorDeTexto, clave
from reglas_texto import partes_de_texto
from presencia import DetectorDePresencia
from alcance import decidir

CONFIG = {c["categoria"]: c for c in
          json.loads(Path("categorias_cubetas.json").read_text(encoding="utf-8"))}
POR_CLAVE = {clave(k): v for k, v in CONFIG.items()}

# El alcance lo decide la medicion (ver alcance.py), no el gusto.
DENTRO, FUERA = decidir()
ALCANCE = {clave(f["categoria"]): f for f in DENTRO}

REGLAS = {
    "document name":                     (R.regla_nombre,     71.9),
    "governing law":                     (R.regla_ley,        91.7),
    "agreement date":                    (R.regla_fecha,      73.6),
    "effective date":                    (R.regla_fecha,      68.0),
    "notice period to terminate renewal":(R.regla_preaviso,   61.2),
    "renewal term":                      (R.regla_renovacion, 60.6),
    "parties":                           (partes_de_texto,     5.8),
}
UMBRAL_CONFIANZA = 50.0

# el nombre difiere entre los dos archivos de CUAD
def equivalente(categoria, claves):
    k = clave(categoria)
    return next((c for c in claves if clave(c) == k), None)


def entrada(categoria, loc, det, texto):
    cfg = POR_CLAVE.get(clave(categoria), {})
    cubeta = cfg.get("cubeta", "recuperacion")
    k = clave(categoria)
    base = dict(categoria=categoria, cubeta=cubeta)

    # --- categorias con regla ------------------------------------------------
    if k in REGLAS:
        regla, confianza = REGLAS[k]
        if confianza < UMBRAL_CONFIANZA:
            return {**base, "estado": "pendiente_modelo", "valor": None,
                    "texto": None, "confianza": confianza, "inicio": None}
        frs = loc.fragmentos(categoria)
        valor = regla(frs) if frs else None
        if not valor:
            estado = "ausente" if cubeta != "humano" else "por_confirmar"
            return {**base, "estado": estado, "valor": None, "texto": None,
                    "confianza": confianza, "inicio": None}
        return {**base,
                "estado": "por_confirmar" if cubeta == "humano" else "encontrada",
                "valor": valor, "texto": " ".join(frs[0].split())[:300],
                "confianza": confianza, "inicio": None}

    # --- categorias de presencia --------------------------------------------
    nombre_det = equivalente(categoria, det.pistas)
    if nombre_det is None:
        return {**base, "estado": "por_confirmar", "valor": None,
                "texto": None, "confianza": None, "inicio": None}

    estado, conf, inicio = det.evaluar(nombre_det, texto)
    # una categoria cara nunca se cierra sola, aunque el detector este seguro
    if cubeta == "humano" and estado in ("encontrada", "ausente"):
        estado = "por_confirmar" if estado == "encontrada" else "ausente_por_confirmar"
    frag = " ".join(texto[inicio:inicio + 400].split()) if inicio is not None else None
    return {**base, "estado": estado, "valor": "presente" if "encontrada" in estado
            else None, "texto": frag, "confianza": conf, "inicio": inicio}


def ficha(texto, completo=False):
    """completo=True devuelve las 41; por defecto solo las 10 del alcance."""
    loc = LocalizadorDeTexto(texto)
    det = DetectorDePresencia()
    cats = CONFIG if completo else [c for c in CONFIG if clave(c) in ALCANCE]
    salida = []
    for c in cats:
        e = entrada(c, loc, det, texto)
        a = ALCANCE.get(clave(c))
        if a:
            e["confianza"] = a["medida"]
            e["motor"] = a["motor"]
        salida.append(e)
    return salida


SIMBOLO = {"encontrada": "[ok]", "ausente": "[  ]", "por_confirmar": "[?]",
           "ausente_por_confirmar": "[?-]", "pendiente_modelo": "[M]"}
LEYENDA = {"ausente": "no aparece",
           "por_confirmar": "revisar",
           "ausente_por_confirmar": "no la veo, confirmar",
           "pendiente_modelo": "la regla perdio: toca al modelo"}

def imprimir(f, titulo):
    print("=" * 78); print(titulo[:76]); print("=" * 78)
    orden = {"encontrada": 0, "por_confirmar": 1, "ausente_por_confirmar": 2,
             "ausente": 3, "pendiente_modelo": 4}
    for e in sorted(f, key=lambda e: (orden[e["estado"]], e["categoria"])):
        conf = f"{e['confianza']:.0f}%" if e["confianza"] else "  -"
        salto = " ->" if e["inicio"] is not None else "   "
        val = e["valor"] or LEYENDA.get(e["estado"], "")
        print(f"  {SIMBOLO[e['estado']]:5}{e['categoria']:34}{str(val)[:26]:28}{conf:>5}{salto}")
    n = lambda *s: sum(1 for e in f if e["estado"] in s)
    print("-" * 78)
    print(f"  cierran solas {n('encontrada','ausente')}   "
          f"a revision {n('por_confirmar','ausente_por_confirmar')}   "
          f"pendientes {n('pendiente_modelo')}   total {len(f)}")
    print(f"  fuera del alcance, sin medicion que las respalde: {len(FUERA)} categorias")


def main(ruta, indice=0):
    contratos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    nombre = sorted(contratos)[int(indice)]
    f = ficha(contratos[nombre])
    imprimir(f, nombre)
    Path("ficha_ejemplo.json").write_text(
        json.dumps({"contrato": nombre, "entradas": f}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return f

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contratos.json",
         sys.argv[2] if len(sys.argv) > 2 else 0)
