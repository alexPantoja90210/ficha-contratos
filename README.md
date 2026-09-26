# Revisor de contratos — 10 cláusulas, medidas

Lee un contrato en texto y devuelve una ficha de **10 cláusulas**: qué dice
cada una, cuáles no aparecen, y **con qué confianza** se afirma cada renglón.

Corre sin modelo, sin llaves de API y sin base de datos. Un contrato tarda
menos de un segundo.

```bash
python ficha.py contratos.json 433
```

```
[ok] Agreement Date        5/3/16          74%
[ok] Audit Rights          presente        75%
[ok] Governing Law         Maryland        92%
[ok] License Grant         presente        77%
[?]  Cap on Liability      revisar         84%
[  ] Warranty Duration     no aparece      76%
```

## Qué tan bien funciona

Medido sobre **101 contratos que el sistema nunca vio** (partición de prueba
de [CUAD](https://github.com/TheAtticusProject/cuad), 510 contratos
comerciales anotados por abogados), 950 renglones juzgables:

| | |
|---|---:|
| Renglones correctos | **76.7%** |
| Fichas con 80% o más correcto | 53% |
| Fichas sin un solo error | 12% |

Por categoría:

| Categoría | Motor | Acierto |
|---|---|---:|
| Governing Law | regla | 90% |
| Cap on Liability | presencia | 86% |
| No-Solicit of Employees | presencia | 80% |
| License Grant | presencia | 76% |
| Warranty Duration | presencia | 76% |
| Insurance | presencia | 76% |
| Agreement Date | regla | 74% |
| Audit Rights | presencia | 73% |
| Effective Date | regla | 67% |
| Document Name | regla | 66% |

## Por qué solo 10 de 41

CUAD define 41 categorías. Las otras 31 **no pasaron el corte**, y el corte
está escrito antes de mirar los resultados (`alcance.py`):

- por regla: acierto de punta a punta ≥ 65%
- por presencia: exactitud balanceada ≥ 70% **y** recall ≥ 70%

El recall está en el criterio a propósito. Una categoría que detecta bien pero
se le escapan las que sí están no puede afirmar ausencia — y una ficha que no
puede decir "no está" no sirve para revisar un contrato.

`python alcance.py` imprime las 41 con su número, dentro y fuera, para que la
decisión se pueda discutir en vez de creerse.

## Dos motores

| | |
|---|---|
| `localizador.py` + reglas | 4 categorías tipadas: título, partes, fechas, ley aplicable |
| `recuperacion.py` | 6 categorías de presencia, por términos discriminantes aprendidos |

El reparto no fue una corazonada. Salió de medir cada categoría en las dos
mitades del problema — **localizar** la cláusula y **normalizar** el valor — y
quedarse con el motor que ganó en cada una.

Un ejemplo de por qué importa: *Governing Law* vive en el 84% de profundidad
del contrato, y un lector que trunca a 8,000 caracteres la ve en el 8% de los
casos. Una expresión regular que recorre el documento entero la resuelve al
90%. *Parties*, que parecía la más fácil porque está en el primer párrafo, se
midió al 5.8% y quedó fuera: ahí es donde un modelo se gana su hora.

## Reglas de medición

Están cableadas en el código, no son buenas intenciones:

1. **Nada de exactitud promediada entre categorías.** Un detector que siempre
   responde "no está" saca 79.7% en este corpus. `piso_trivial.py` calcula, por
   categoría, el piso que hay que superar para que el número signifique algo.
2. **El corte train/val/test es por contrato, nunca por pregunta.** Cada
   contrato se pregunta 41 veces; partir preguntas al azar pondría el mismo
   texto de los dos lados de la línea.
3. **Los empates de términos se rompen por el término.** Python aleatoriza el
   hash de cadenas por proceso: sin esto el corte del top-40 cae distinto en
   cada corrida y el proyecto imprime un número diferente cada vez.
4. **Una categoría sin positivos suficientes para calibrar no se publica.** Se
   marca como no calibrable y va a revisión humana.

## Alcance y límites

No es asesoría legal. Localiza cláusulas y señala ausencias para que una
persona las lea. El corpus es de contratos comerciales en inglés bajo derecho
estadounidense; llevarlo a contratos en español es otro proyecto.

El salto al documento solo se ofrece cuando la ubicación acertó ≥50% en
prueba. Hoy casi ninguna categoría de presencia llega: el sistema dice si la
cláusula está, no dónde. Esa es la siguiente pieza.

## Archivos

| | |
|---|---|
| `ficha.py` | el producto: contrato → ficha de 10 renglones |
| `alcance.py` | qué entra y qué no, con el criterio y los números |
| `localizador.py` | encuentra la cláusula en el contrato crudo |
| `recuperacion.py` | aprende términos, calibra umbrales, evalúa |
| `presencia.py` | aplica lo aprendido, con las reglas de honestidad |
| `medir_ficha.py` | mide la ficha completa, renglón por renglón |
| `medir_e2e.py` | mide localización + normalización |
| `medir_reglas.py` | mide solo normalización |
| `piso_trivial.py` | el piso que cada categoría debe superar |
