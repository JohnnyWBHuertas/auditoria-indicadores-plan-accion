"""Muestra estratificada de pares de indicadores para su etiquetado (V-M3; E02).

Se parte de los embeddings guardados y se arman estratos por similitud y por
coincidencia de nombre. Cada estrato lleva su peso (tamano del estrato dividido
por el numero de pares muestreados), de modo que las metricas ponderadas
estimen el comportamiento sobre todos los pares de las vigencias muestreadas.
La muestra con indicadores reales no se versiona: contiene texto institucional.
"""

from __future__ import annotations

import random

import numpy as np

from apps.ingesta.models import Indicador
from apps.nlp_engine.models import EmbeddingIndicador

from .agrupacion import normalizar_nombre

TAMANOS_POR_DEFECTO = {
    "S1 similitud >= 0,90 (nombres distintos)": 25,
    "S2 similitud 0,85 a 0,90 (nombres distintos)": 25,
    "S3 similitud 0,80 a 0,85 (nombres distintos)": 25,
    "S4 mismo nombre, misma dependencia": 10,
    "S5 mismo nombre, otra dependencia": 10,
    "S6 similitud 0,70 a 0,80 (negativos difíciles)": 15,
    "S7 similitud menor de 0,70 (azar)": 10,
}


def _estrato(sim, mismo_nombre, misma_dep):
    if mismo_nombre:
        return "S4 mismo nombre, misma dependencia" if misma_dep else "S5 mismo nombre, otra dependencia"
    if sim >= 0.90:
        return "S1 similitud >= 0,90 (nombres distintos)"
    if sim >= 0.85:
        return "S2 similitud 0,85 a 0,90 (nombres distintos)"
    if sim >= 0.80:
        return "S3 similitud 0,80 a 0,85 (nombres distintos)"
    if sim >= 0.70:
        return "S6 similitud 0,70 a 0,80 (negativos difíciles)"
    return "S7 similitud menor de 0,70 (azar)"


def poblacion_de_pares(vigencias):
    """Devuelve {estrato: [(vigencia, id_a, id_b, similitud), ...]} con todos los pares de cada vigencia."""
    pools = {k: [] for k in TAMANOS_POR_DEFECTO}
    for vig in vigencias:
        filas = list(
            EmbeddingIndicador.objects.filter(indicador__vigencia=vig)
            .order_by("indicador_id")
            .values_list("indicador_id", "vector", "indicador__nombre", "indicador__dependencia_id")
        )
        if len(filas) < 2:
            continue
        ids = [f[0] for f in filas]
        m = np.array([f[1] for f in filas], dtype=np.float32)
        m /= np.where(np.linalg.norm(m, axis=1, keepdims=True) == 0, 1, np.linalg.norm(m, axis=1, keepdims=True))
        s = m @ m.T
        nombres = [normalizar_nombre(f[2]) for f in filas]
        deps = [f[3] for f in filas]
        iu, ju = np.triu_indices(len(ids), 1)
        for i, j in zip(iu, ju):
            sim = float(s[i, j])
            pools[_estrato(sim, nombres[i] == nombres[j], deps[i] == deps[j])].append((vig, ids[i], ids[j], sim))
    return pools


def generar_muestra(vigencias, semilla=42, tamanos=None):
    tamanos = tamanos or TAMANOS_POR_DEFECTO
    rng = random.Random(semilla)
    pools = poblacion_de_pares(vigencias)
    muestra = []
    for estrato, n in tamanos.items():
        pool = pools.get(estrato, [])
        elegidos = rng.sample(pool, min(n, len(pool))) if pool else []
        peso = (len(pool) / len(elegidos)) if elegidos else 0.0
        for vig, a, b, sim in sorted(elegidos):
            muestra.append({"estrato": estrato, "peso": round(peso, 4), "vigencia": vig, "id_a": a, "id_b": b, "similitud": round(sim, 4)})
    poblacion = {k: len(v) for k, v in pools.items()}
    return muestra, poblacion


def detalle_indicadores(muestra):
    ids = {f["id_a"] for f in muestra} | {f["id_b"] for f in muestra}
    return {
        i.pk: i for i in Indicador.objects.filter(pk__in=ids).select_related("dependencia")
    }
