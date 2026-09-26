#!/usr/bin/env python3
"""DetectorDePresencia: la capa de recuperacion, lista para la ficha.

Carga lo que `recuperacion.py` aprendio (terminos por categoria, umbral
calibrado, y el desempeno medido en prueba) y lo aplica a un contrato nuevo.

Tres reglas de honestidad, cableadas aqui y no en la interfaz:

1. Categoria sin umbral calibrable -> nunca decide sola.
2. Un "ausente" solo se afirma si el recall medido lo respalda. Con recall
   bajo el detector no ve la mitad de las que SI estan, asi que su silencio
   no es evidencia de ausencia: sale como ausente_por_confirmar.
3. Solo se ofrece salto al documento si la ubicacion acerto lo suficiente en
   prueba. Mandar al usuario al parrafo equivocado es peor que no ofrecerlo.
"""
import json
from pathlib import Path

import recuperacion as REC

RECALL_MINIMO_PARA_AFIRMAR_AUSENCIA = 60.0
UBICACION_MINIMA_PARA_SALTAR        = 50.0


class DetectorDePresencia:
    def __init__(self, ruta="recuperacion_resultados.json"):
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        self.pistas = d["pistas"]
        self.umbrales = d["umbrales"]
        self.desempeno = {r["categoria"]: r for r in d["test"]}
        self._cache = {}

    def soporta(self, categoria):
        return categoria in self.pistas

    def evaluar(self, categoria, texto):
        """-> (estado, confianza, inicio|None)"""
        perf = self.desempeno.get(categoria)
        umbral = self.umbrales.get(categoria)
        if umbral is None or perf is None:
            return "por_confirmar", None, None

        puntaje, donde = REC.puntuar(texto, self.pistas[categoria], self._cache)
        conf = perf["balanceada"]
        ubica = perf.get("ubica")

        if puntaje >= umbral:
            inicio = donde if (ubica or 0) >= UBICACION_MINIMA_PARA_SALTAR else None
            return "encontrada", conf, inicio
        if perf["recall"] >= RECALL_MINIMO_PARA_AFIRMAR_AUSENCIA:
            return "ausente", conf, None
        return "ausente_por_confirmar", conf, None
