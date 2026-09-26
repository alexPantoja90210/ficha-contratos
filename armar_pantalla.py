#!/usr/bin/env python3
"""Arma la pantalla: elige que contratos se muestran y reconstruye el HTML.

Los tres de fabrica son ejemplos de la particion de prueba, elegidos porque
entre los tres cubren los casos interesantes: uno con Governing Law al 1% del
documento y otro con la misma clausula al 85%.

  python armar_pantalla.py                          # los tres de fabrica
  python armar_pantalla.py --listar                 # indices y nombres disponibles
  python armar_pantalla.py --agregar 12 --quitar VEONEER
  python armar_pantalla.py --contratos 480 433 465  # reemplaza la lista entera

Un contrato se nombra por su indice (orden alfabetico del corpus) o por
cualquier trozo de su nombre, siempre que ese trozo identifique a uno solo.
Despues de correr esto, hay que publicar `revisor.html`.
"""
import argparse, json, os, re, sys
from pathlib import Path

# El proyecto lee sus datos con rutas relativas (categorias_cubetas.json,
# recuperacion_resultados.json, plantilla.html), asi que el script se planta
# en su propia carpeta y se puede invocar desde donde sea.
AQUI = Path(__file__).resolve().parent
os.chdir(AQUI)
sys.path.insert(0, str(AQUI))

import medir_reglas as R, recuperacion as REC
from localizador import LocalizadorDeTexto, clave
from presencia import DetectorDePresencia
from alcance import decidir, INGENUO
import ficha as F

BASE = [
    "VirtuosoSurgicalInc_20191227_1-A_EX1A-6 MAT CTRCT_11933379_EX1A-6 MAT CTRCT_License Agreement",
    "TALCOTTRESOLUTIONLIFEINSURANCECO-SEPARATEACCOUNTTWELVE_04_30_2020-EX-99.8(L)-SERVICE AGREEMENT",
    "VEONEER,INC_02_21_2020-EX-10.11-JOINT VENTURE AGREEMENT",
]

# Una sola cifra por categoria en toda la pagina: la de la particion de prueba
# (medir_ficha.py). Nunca la de los 510, para no publicar dos numeros del mismo.
PRUEBA = {"Governing Law": 90, "Cap on Liability": 86, "License Grant": 76,
          "Insurance": 76, "Agreement Date": 74, "Audit Rights": 73,
          "Effective Date": 67, "Document Name": 66}

MAX_TEXTO = 60000          # lo que se incrusta del contrato
FECHA = re.compile(
    r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{1,2}\s*(?:st|nd|rd|th|t\s*h)?\s+day\s+of\s+[A-Za-z]+,?\s*\d{4})")


# El corpus vive fuera del repositorio (27 MB). Se busca donde suele estar,
# en vez de exigir que se escriba la ruta en cada corrida.
CANDIDATOS_CORPUS = [
    Path("contratos.json"),
    AQUI / "contratos.json",
    AQUI.parent / "cuad" / "contratos.json",
    Path("C:/dev/cuad/contratos.json"),
    Path.home() / "dev" / "cuad" / "contratos.json",
]

def corpus_por_omision():
    for c in CANDIDATOS_CORPUS:
        if c.is_file():
            return str(c)
    return None


def resolver(clave_usuario, nombres):
    """Indice o trozo de nombre -> nombre completo. Falla si es ambiguo."""
    s = str(clave_usuario)
    if s.isdigit():
        i = int(s)
        if not 0 <= i < len(nombres):
            sys.exit(f"indice fuera de rango: {i} (hay {len(nombres)})")
        return nombres[i]
    coinciden = [n for n in nombres if s.lower() in n.lower()]
    if not coinciden:
        sys.exit(f"ningun contrato coincide con {s!r}")
    if len(coinciden) > 1:
        print(f"{s!r} es ambiguo, coincide con {len(coinciden)}:", file=sys.stderr)
        for n in coinciden[:6]:
            print("   ", n, file=sys.stderr)
        sys.exit(1)
    return coinciden[0]


def prueba_de(cat):
    return next((v for k, v in PRUEBA.items() if clave(k) == clave(cat)), None)

def ingenuo_de(cat):
    return next((v for k, v in INGENUO.items() if clave(k) == clave(cat)), None)


def rango_regla(texto, valor, cat):
    """Solo se resalta lo que de verdad corresponde al valor mostrado."""
    if not valor:
        return None
    if "date" in clave(cat):
        for fr in LocalizadorDeTexto(texto).fragmentos(cat):
            base = texto.find(fr[:150])
            if base < 0:
                continue
            for m in FECHA.finditer(fr):
                if R.extrae_fecha(m.group(0)) == valor:
                    return [base + m.start(), base + m.end()]
        return None
    for cand in (valor, valor.split(";")[0].strip()):
        i = texto.lower().find(cand.lower())
        if i >= 0:
            return [i, i + len(cand)]
    return None


def armar(nombres_elegidos, contratos, dentro, det, cache):
    salida = []
    for nombre in nombres_elegidos:
        texto = contratos[nombre]
        largo = len(texto)
        entradas = []
        for e in F.ficha(texto):
            cat = e["categoria"]
            motor = next(d["motor"] for d in dentro if clave(d["categoria"]) == clave(cat))
            rango = pasaje = prof = None
            if motor == "regla":
                rango = rango_regla(texto, e["valor"], cat)
                if rango:
                    prof = round(100 * rango[0] / largo)
            else:
                nd = next((c for c in det.pistas if clave(c) == clave(cat)), None)
                if nd and e["estado"] == "encontrada":
                    _, donde = REC.puntuar(texto, det.pistas[nd], cache)
                    if donde is not None:
                        pasaje = " ".join(texto[donde:donde + 340].split())
                        prof = round(100 * donde / largo)
            entradas.append(dict(categoria=cat, motor=motor, estado=e["estado"],
                                 valor=e["valor"], confianza=prueba_de(cat),
                                 ingenuo=ingenuo_de(cat), rango=rango,
                                 pasaje=pasaje, prof=prof))
        salida.append(dict(nombre=nombre, texto=texto[:MAX_TEXTO],
                           largo=largo, entradas=entradas))
    return salida


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default=None,
                    help="contratos.json; si se omite se busca en las rutas usuales")
    ap.add_argument("--plantilla", default="plantilla.html")
    ap.add_argument("--salida", default="revisor.html")
    ap.add_argument("--contratos", nargs="*", help="reemplaza la lista entera")
    ap.add_argument("--agregar", nargs="*", default=[])
    ap.add_argument("--quitar", nargs="*", default=[])
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()

    ruta = a.corpus or corpus_por_omision()
    if not ruta:
        print("No encuentro contratos.json. Lo busque en:", file=sys.stderr)
        for c in CANDIDATOS_CORPUS:
            print(f"   {c}", file=sys.stderr)
        sys.exit("Pasa la ruta con --corpus, o reconstruyelo (ver README).")
    if not Path(ruta).is_file():
        sys.exit(f"No existe: {ruta}")
    contratos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    nombres = sorted(contratos)

    if a.listar:
        prueba = int(len(nombres) * 0.8)
        for i, n in enumerate(nombres):
            marca = "prueba" if i >= prueba else "      "
            print(f"{i:>4} {marca}  {n[:92]}")
        return

    elegidos = [resolver(c, nombres) for c in (a.contratos if a.contratos else BASE)]
    for c in a.agregar:
        n = resolver(c, nombres)
        if n not in elegidos:
            elegidos.append(n)
    for c in a.quitar:
        n = resolver(c, nombres)
        if n not in elegidos:
            sys.exit(f"no estaba en la lista: {n}")
        elegidos.remove(n)
    if not elegidos:
        sys.exit("la pantalla quedaria sin contratos")

    dentro, fuera = decidir()
    det = DetectorDePresencia()
    datos = armar(elegidos, contratos, dentro, det, {})

    evid = [dict(cat=f["categoria"], pct=prueba_de(f["categoria"]),
                 ing=ingenuo_de(f["categoria"])) for f in dentro]
    evid.sort(key=lambda r: -r["pct"])
    fuera_out = [dict(categoria=f["categoria"], motor=f["motor"],
                      medida=f["medida"], recall=f.get("recall")) for f in fuera]

    html = Path(a.plantilla).read_text(encoding="utf-8")
    for marca, valor in (("__DATOS__", datos), ("__EVID__", evid), ("__FUERA__", fuera_out)):
        if marca not in html:
            sys.exit(f"la plantilla no tiene {marca}")
        html = html.replace(marca, json.dumps(valor, ensure_ascii=False))
    Path(a.salida).write_text(html, encoding="utf-8")

    print(f"{len(datos)} contratos en la pantalla:")
    for c in datos:
        m = sum(1 for e in c["entradas"] if e["rango"])
        p = sum(1 for e in c["entradas"] if e["pasaje"])
        print(f"  {c['nombre'][:62]:64} {m} marcas, {p} pasajes")
    print(f"\n{a.salida}  ({Path(a.salida).stat().st_size//1024} KB) — falta publicarlo")

if __name__ == "__main__":
    main()
