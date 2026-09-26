#!/usr/bin/env python3
"""Capa de recuperacion para las 33 categorias de presencia.

Que hace
--------
Por categoria aprende, de los contratos de entrenamiento, que terminos
distinguen a los contratos que SI tienen la clausula de los que no. Luego
parte un contrato nuevo en ventanas solapadas, puntua cada una por densidad
de esos terminos, y se queda con la mejor: esa ventana es la ubicacion
propuesta, y su puntaje decide si la clausula esta o no.

Da las dos cosas que la ficha necesita -- presencia Y donde -- sin modelo,
sin llaves y en segundos. Y fija el piso que un modelo tendra que superar
para ganarse su hora.

Reglas de medicion (no negociables)
-----------------------------------
1. El corte train/val/test es POR CONTRATO, nunca por pregunta: cada contrato
   se pregunta 41 veces, y partir preguntas al azar pondria el mismo texto de
   los dos lados de la linea.
2. Nada de exactitud promediada entre categorias. El 79.7% que saca "responder
   siempre que no esta" la haria ver bien sin serlo.
3. La metrica es exactitud balanceada, y se reporta contra el piso trivial de
   cada categoria.
4. Los empates de terminos se rompen por el termino mismo. Python aleatoriza
   el hash de cadenas por proceso; sin esto el corte del top-K cae en distinto
   lugar en cada corrida y el repositorio imprime un numero diferente cada vez.

Uso:  python recuperacion.py contratos.json master_clauses.csv
"""
import ast, csv, io, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

VENTANA, PASO = 1600, 800
TOP_TERMINOS   = 40
SEMILLA_CORTE  = (0.60, 0.20)    # train, val; el resto es test

PALABRA = re.compile(r"[a-z][a-z\-']{2,}")
VACIAS = set("""the and for any all such that this with shall are not或 but its his her
their which have has had was were been being from into upon under over more most other
than then them they there these those you your our ous will would may can could should
each either neither both same very much many few less least also only just even still
per pursuant hereof hereto herein hereby thereof thereto therein whereas provided
agreement party parties section article exhibit schedule date dates day days
""".split())


def tokens(texto):
    return [t for t in PALABRA.findall(texto.lower()) if t not in VACIAS]


# ---------- datos ------------------------------------------------------------
def cargar(ruta_json, ruta_csv):
    contratos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = list(csv.DictReader(io.StringIO(
        Path(ruta_csv).read_text(encoding="utf-8-sig", errors="replace"))))
    stem = lambda n: n[:-4] if n.lower().endswith(".pdf") else n

    categorias = []
    for c in filas[0]:
        if c.endswith("-Answer") or c.endswith("- Answer") or c == "Filename":
            continue
        col = next((c + s for s in ("-Answer", "- Answer") if c + s in filas[0]), None)
        if not col:
            continue
        vals = {(f.get(col) or "").strip() for f in filas} - {""}
        if vals <= {"Yes", "No"}:
            categorias.append((c, col))

    datos = []
    for f in filas:
        texto = contratos.get(stem(f["Filename"]))
        if texto is None:
            continue
        etiquetas, oro = {}, {}
        for c, col in categorias:
            celda = (f.get(c) or "").strip()
            try:
                trozos = ast.literal_eval(celda) if celda else []
            except (ValueError, SyntaxError):
                trozos = [celda] if celda else []
            etiquetas[c] = bool(trozos)
            oro[c] = [str(t) for t in trozos]
        datos.append(dict(nombre=f["Filename"], texto=texto,
                          etiquetas=etiquetas, oro=oro))
    return datos, [c for c, _ in categorias]


def partir(datos):
    """Corte por contrato, determinista y sin azar: por orden de nombre."""
    orden = sorted(datos, key=lambda d: d["nombre"])
    n = len(orden)
    a, b = int(n * SEMILLA_CORTE[0]), int(n * (SEMILLA_CORTE[0] + SEMILLA_CORTE[1]))
    return orden[:a], orden[a:b], orden[b:]


# ---------- aprendizaje de terminos -----------------------------------------
def aprender(train, categorias):
    bolsas = {d["nombre"]: set(tokens(d["texto"])) for d in train}
    pistas = {}
    for cat in categorias:
        con, sin = Counter(), Counter()
        n_con = n_sin = 0
        for d in train:
            b = bolsas[d["nombre"]]
            if d["etiquetas"][cat]:
                con.update(b); n_con += 1
            else:
                sin.update(b); n_sin += 1
        if n_con < 5:
            pistas[cat] = []
            continue
        puntajes = []
        for t in set(con) | set(sin):
            p = (con[t] + 0.5) / (n_con + 1)
            q = (sin[t] + 0.5) / (n_sin + 1)
            puntajes.append((math.log(p / q), t))
        # desempate por el termino: sin esto el corte del top-K cambia por corrida
        puntajes.sort(key=lambda x: (-x[0], x[1]))
        pistas[cat] = [t for s, t in puntajes[:TOP_TERMINOS] if s > 0]
    return pistas


# ---------- puntuacion -------------------------------------------------------
def ventanas(texto):
    return [(i, texto[i:i + VENTANA]) for i in range(0, max(1, len(texto)), PASO)]

def puntuar(texto, pistas_cat, cache):
    """Mejor ventana y su puntaje: fraccion de terminos pista presentes."""
    if not pistas_cat:
        return 0.0, None
    if texto not in cache:
        cache[texto] = [(i, set(tokens(v))) for i, v in ventanas(texto)]
    mejor, donde = 0.0, None
    pistas_set = set(pistas_cat)
    for i, toks in cache[texto]:
        s = len(pistas_set & toks) / len(pistas_set)
        if s > mejor:
            mejor, donde = s, i
    return mejor, donde


MINIMO_PARA_CALIBRAR = 5   # positivos en validacion

def calibrar(val, categorias, pistas, cache):
    """Umbral por categoria que maximiza la exactitud balanceada.

    Con menos de MINIMO_PARA_CALIBRAR positivos en validacion el umbral no
    significa nada: la busqueda se va a los extremos y produce un detector que
    dice "si" a todo (exactitud 4%) o "no" a todo. Esas categorias se marcan
    como NO CALIBRABLES en vez de publicar un numero inventado.
    """
    umbrales, sin_calibrar = {}, set()
    for cat in categorias:
        puntos = [(puntuar(d["texto"], pistas[cat], cache)[0], d["etiquetas"][cat])
                  for d in val]
        pos = sum(1 for _, y in puntos if y)
        neg = len(puntos) - pos
        if pos < MINIMO_PARA_CALIBRAR or neg < MINIMO_PARA_CALIBRAR:
            umbrales[cat] = None
            sin_calibrar.add(cat)
            continue
        mejor = (0.0, 0.5)
        for u in [i / 40 for i in range(1, 41)]:
            vp = sum(1 for s, y in puntos if y and s >= u)
            vn = sum(1 for s, y in puntos if not y and s < u)
            bal = (vp / pos + vn / neg) / 2
            if bal > mejor[0]:
                mejor = (bal, u)
        umbrales[cat] = mejor[1]
    return umbrales, sin_calibrar


def evaluar(test, categorias, pistas, umbrales, cache, sin_calibrar):
    filas = []
    for cat in categorias:
        if cat in sin_calibrar:
            continue
        vp = vn = fp = fn = 0
        aciertan_lugar = con_lugar = 0
        for d in test:
            s, donde = puntuar(d["texto"], pistas[cat], cache)
            pred = s >= umbrales[cat]
            real = d["etiquetas"][cat]
            if real and pred:
                vp += 1
                oro = d["oro"][cat]
                if oro and donde is not None:
                    con_lugar += 1
                    trozo = d["texto"][donde:donde + VENTANA]
                    clave = " ".join(oro[0].split())[:60]
                    if clave and clave in " ".join(trozo.split()):
                        aciertan_lugar += 1
            elif real:
                fn += 1
            elif pred:
                fp += 1
            else:
                vn += 1
        pos, neg = vp + fn, vn + fp
        if not pos or not neg:
            continue
        sens, espec = vp / pos, vn / neg
        filas.append(dict(
            categoria=cat, n=pos + neg, positivos=pos,
            piso=100 * max(pos, neg) / (pos + neg),
            exactitud=100 * (vp + vn) / (pos + neg),
            balanceada=100 * (sens + espec) / 2,
            recall=100 * sens, especificidad=100 * espec,
            ubica=100 * aciertan_lugar / con_lugar if con_lugar else None))
    return filas


def main(ruta_json, ruta_csv):
    datos, categorias = cargar(ruta_json, ruta_csv)
    train, val, test = partir(datos)
    print(f"contratos {len(datos)}  train {len(train)}  val {len(val)}  test {len(test)}")
    print(f"categorias de presencia: {len(categorias)}\n")

    pistas = aprender(train, categorias)
    cache = {}
    umbrales, sin_calibrar = calibrar(val, categorias, pistas, cache)
    filas = evaluar(test, categorias, pistas, umbrales, cache, sin_calibrar)

    filas.sort(key=lambda r: r["balanceada"] - 50, reverse=True)
    print(f"{'categoria':36}{'n':>4}{'pos':>5}{'piso':>7}{'exact':>7}"
          f"{'balanc':>8}{'recall':>8}{'ubica':>7}")
    for r in filas:
        ub = f"{r['ubica']:.0f}%" if r["ubica"] is not None else "-"
        print(f"{r['categoria']:36}{r['n']:>4}{r['positivos']:>5}{r['piso']:>6.0f}%"
              f"{r['exactitud']:>6.0f}%{r['balanceada']:>7.1f}%{r['recall']:>7.0f}%{ub:>7}")

    bal = sum(r["balanceada"] for r in filas) / len(filas)
    sobre = sum(1 for r in filas if r["balanceada"] > 55)
    print(f"\nexactitud balanceada media : {bal:.1f}%   (el azar es 50%)")
    print(f"categorias por encima de 55%: {sobre} de {len(filas)}")
    if sin_calibrar:
        print(f"\nNO CALIBRABLES ({len(sin_calibrar)}): menos de "
              f"{MINIMO_PARA_CALIBRAR} positivos en validacion, el umbral no "
              f"significa nada.\n  " + ", ".join(sorted(sin_calibrar)))
        print("  Estas van directo a confirmacion humana: son tan raras que "
              "revisarlas a mano cuesta poco.")
    Path("recuperacion_resultados.json").write_text(
        json.dumps(dict(umbrales=umbrales, pistas=pistas, test=filas),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return filas

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "contratos.json",
         sys.argv[2] if len(sys.argv) > 2 else "master_clauses.csv")
