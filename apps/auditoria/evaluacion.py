"""Evaluacion acotada del detector sobre una muestra etiquetada (V-M2, V-M3; E01, E02, E07).

Reutiliza los embeddings guardados y varia solo el parametro de decision (umbral
de similitud). Los umbrales 0,80, 0,85 y 0,90 son escenarios de experimentacion:
no reemplazan el umbral del sistema. Las metricas describen el comportamiento
sobre la muestra y no se extrapolan a todos los indicadores institucionales.
"""

from __future__ import annotations

from sklearn.metrics import f1_score, precision_score, recall_score

UMBRALES_POR_DEFECTO = (0.80, 0.85, 0.90)
ETIQUETAS_POSITIVAS = {"D", "1", "SI", "SÍ", "TRUE"}


def es_positiva(etiqueta) -> bool:
    return str(etiqueta).strip().upper() in ETIQUETAS_POSITIVAS


def matriz_confusion(y_true, y_pred, pesos=None):
    pesos = pesos or [1.0] * len(y_true)
    tp = sum(w for t, p, w in zip(y_true, y_pred, pesos) if t and p)
    fp = sum(w for t, p, w in zip(y_true, y_pred, pesos) if not t and p)
    fn = sum(w for t, p, w in zip(y_true, y_pred, pesos) if t and not p)
    tn = sum(w for t, p, w in zip(y_true, y_pred, pesos) if not t and not p)
    return tp, fp, fn, tn


def metricas(y_true, similitudes, umbral, pesos=None) -> dict:
    """Precision, exhaustividad (recall) y F1 del detector con el umbral dado."""
    y_pred = [s >= umbral for s in similitudes]
    kw = {"zero_division": 0, "sample_weight": pesos}
    tp, fp, fn, tn = matriz_confusion(y_true, y_pred, pesos)
    return {
        "umbral": umbral,
        "precision": round(float(precision_score(y_true, y_pred, **kw)), 4),
        "exhaustividad": round(float(recall_score(y_true, y_pred, **kw)), 4),
        "f1": round(float(f1_score(y_true, y_pred, **kw)), 4),
        "vp": round(tp, 2), "fp": round(fp, 2), "fn": round(fn, 2), "vn": round(tn, 2),
    }


def evaluar(filas, umbrales=UMBRALES_POR_DEFECTO) -> dict:
    """filas: lista de dicts con 'similitud', 'positiva' (bool) y, opcional, 'peso'.

    Devuelve las metricas sin ponderar (la muestra tal cual) y ponderadas por el
    peso de cada estrato (estimacion sobre los pares de la poblacion muestreada),
    mas los pares que cambian de clasificacion entre umbrales consecutivos.
    """
    y = [bool(f["positiva"]) for f in filas]
    s = [float(f["similitud"]) for f in filas]
    pesos = [float(f.get("peso") or 1.0) for f in filas]
    hay_pesos = any(abs(p - 1.0) > 1e-9 for p in pesos)
    resultado = {
        "n": len(filas),
        "positivas": sum(y),
        "sin_ponderar": [metricas(y, s, u) for u in umbrales],
        "ponderadas": [metricas(y, s, u, pesos) for u in umbrales] if hay_pesos else [],
        "cambios": [],
        "falsos_positivos": {},
        "falsos_negativos": {},
    }
    ordenados = sorted(umbrales)
    for a, b in zip(ordenados, ordenados[1:]):
        resultado["cambios"].append({
            "de": a, "a": b,
            "pares": [i for i, f in enumerate(filas) if (s[i] >= a) != (s[i] >= b)],
        })
    for u in umbrales:
        resultado["falsos_positivos"][u] = [i for i, f in enumerate(filas) if s[i] >= u and not y[i]]
        resultado["falsos_negativos"][u] = [i for i, f in enumerate(filas) if s[i] < u and y[i]]
    return resultado
