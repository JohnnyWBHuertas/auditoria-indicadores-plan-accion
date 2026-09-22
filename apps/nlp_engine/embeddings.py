"""Motor de embeddings (CU2): capa independiente del LLM.

Decision de arquitectura: la similitud semantica se calcula con
sentence-transformers (Reimers & Gurevych, 2019), nunca con Qwen2.5. Esto
preserva la trazabilidad metodologica entre el marco teorico citado en la
monografia y su implementacion, y aisla el motor de embeddings de
cualquier cambio en el modelo de lenguaje usado para explicaciones.
"""

from __future__ import annotations

import itertools

import numpy as np
from django.conf import settings

from apps.ingesta.models import Indicador

from .models import EmbeddingIndicador, ParCandidato

_modelo_cargado = None


def get_embedding_model():
    """Carga perezosa y unica del modelo (evita recargar en cada llamada)."""
    global _modelo_cargado
    if _modelo_cargado is None:
        from sentence_transformers import SentenceTransformer

        _modelo_cargado = SentenceTransformer(settings.NLP_ENGINE["EMBEDDING_MODEL"])
    return _modelo_cargado


def texto_para_embedding(indicador: Indicador) -> str:
    partes = [indicador.nombre, indicador.objetivo]
    return " . ".join(p.strip() for p in partes if p and p.strip())


def generar_embeddings_pendientes() -> int:
    """Calcula embeddings para indicadores que aun no lo tienen. Devuelve el conteo."""
    modelo = get_embedding_model()
    nombre_modelo = settings.NLP_ENGINE["EMBEDDING_MODEL"]

    pendientes = Indicador.objects.filter(embedding__isnull=True)
    creados = 0
    for indicador in pendientes:
        texto = texto_para_embedding(indicador)
        if not texto:
            continue
        vector = modelo.encode(texto, normalize_embeddings=True).tolist()
        EmbeddingIndicador.objects.create(
            indicador=indicador,
            modelo=nombre_modelo,
            texto_fuente=texto,
            vector=vector,
        )
        creados += 1
    return creados


def similitud_coseno(vector_a: list[float], vector_b: list[float]) -> float:
    a = np.array(vector_a)
    b = np.array(vector_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def generar_pares_candidatos(vigencia: str, umbral: float | None = None) -> int:
    """Compara por pares los indicadores de una vigencia y persiste los
    candidatos por encima del umbral de duplicidad (CU2). Devuelve el
    conteo de pares nuevos generados.
    """
    umbral = umbral if umbral is not None else settings.NLP_ENGINE["UMBRAL_DUPLICIDAD"]
    nombre_modelo = settings.NLP_ENGINE["EMBEDDING_MODEL"]

    embeddings = list(
        EmbeddingIndicador.objects.filter(
            indicador__vigencia=vigencia, modelo=nombre_modelo
        ).select_related("indicador")
    )

    creados = 0
    for emb_a, emb_b in itertools.combinations(embeddings, 2):
        score = similitud_coseno(emb_a.vector, emb_b.vector)
        if score < umbral:
            continue
        indicador_a, indicador_b = sorted(
            [emb_a.indicador, emb_b.indicador], key=lambda i: i.pk
        )
        _, creado = ParCandidato.objects.get_or_create(
            indicador_a=indicador_a,
            indicador_b=indicador_b,
            modelo=nombre_modelo,
            defaults={"similitud_coseno": score},
        )
        if creado:
            creados += 1
    return creados
