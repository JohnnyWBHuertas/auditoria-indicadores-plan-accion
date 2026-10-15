"""Motor de embeddings (CU2): unico modelo de inteligencia artificial del prototipo.

Decision de arquitectura: la similitud semantica se calcula con
sentence-transformers (Reimers & Gurevych, 2019), modelo
paraphrase-multilingual-mpnet-base-v2, ejecutado localmente. El modelo solo
propone pares candidatos; la clasificacion por tipo la hacen las reglas de
auditoria (apps.auditoria) y la decision final es del auditor.
"""

from __future__ import annotations

import numpy as np
from django.conf import settings

from apps.ingesta.models import Indicador

from .models import EmbeddingIndicador, ParCandidato

_modelo_cargado = None


class ModeloNoDisponible(RuntimeError):
    """El modelo de embeddings no pudo cargarse en este equipo (por ejemplo, una
    biblioteca nativa bloqueada por el sistema operativo o sin descargar)."""


def get_embedding_model():
    """Carga perezosa y unica del modelo (evita recargar en cada llamada)."""
    global _modelo_cargado
    if _modelo_cargado is None:
        try:
            from sentence_transformers import SentenceTransformer

            _modelo_cargado = SentenceTransformer(settings.NLP_ENGINE["EMBEDDING_MODEL"])
        except (ImportError, OSError) as exc:
            raise ModeloNoDisponible(
                f"No fue posible cargar el modelo de embeddings ({settings.NLP_ENGINE['EMBEDDING_MODEL']}): {str(exc).rstrip('. ')}. "
                "Ejecute 'python manage.py verificar_entorno' para ver qué componente falla."
            ) from exc
    return _modelo_cargado


def texto_para_embedding(indicador: Indicador) -> str:
    partes = [indicador.nombre, indicador.objetivo]
    return " . ".join(p.strip() for p in partes if p and p.strip())


def generar_embeddings_pendientes(tamano_lote: int = 32) -> int:
    """Calcula, por lotes, los embeddings de los indicadores que aun no lo
    tienen. Devuelve el conteo de embeddings creados."""
    pendientes = []
    textos = []
    for indicador in Indicador.objects.filter(embedding__isnull=True):
        texto = texto_para_embedding(indicador)
        if texto:
            pendientes.append(indicador)
            textos.append(texto)
    if not pendientes:
        return 0

    modelo = get_embedding_model()
    nombre_modelo = settings.NLP_ENGINE["EMBEDDING_MODEL"]
    vectores = modelo.encode(textos, batch_size=tamano_lote, normalize_embeddings=True)

    EmbeddingIndicador.objects.bulk_create(
        [
            EmbeddingIndicador(
                indicador=indicador,
                modelo=nombre_modelo,
                texto_fuente=texto,
                vector=vector.tolist(),
            )
            for indicador, texto, vector in zip(pendientes, textos, vectores)
        ]
    )
    return len(pendientes)


def similitud_coseno(vector_a: list[float], vector_b: list[float]) -> float:
    a = np.array(vector_a)
    b = np.array(vector_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def generar_pares_candidatos(vigencia: str, umbral: float | None = None, bloque: int = 500) -> int:
    """Compara todos los indicadores de una vigencia (examen poblacional
    completo) y persiste los pares cuya similitud coseno alcanza el umbral
    de duplicidad (CU2). La comparacion se hace por bloques de filas con
    producto matricial, de modo que el costo crece de forma manejable con el
    volumen. Devuelve el numero de pares candidatos de la vigencia.
    """
    umbral = umbral if umbral is not None else settings.NLP_ENGINE["UMBRAL_DUPLICIDAD"]
    nombre_modelo = settings.NLP_ENGINE["EMBEDDING_MODEL"]

    embeddings = list(
        EmbeddingIndicador.objects.filter(indicador__vigencia=vigencia, modelo=nombre_modelo)
        .order_by("indicador_id")
        .values_list("indicador_id", "vector")
    )
    if len(embeddings) < 2:
        return 0

    ids = np.array([e[0] for e in embeddings])
    matriz = np.array([e[1] for e in embeddings], dtype=np.float32)
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    matriz = matriz / normas

    n = len(ids)
    columnas = np.arange(n)
    pares = []
    for inicio in range(0, n, bloque):
        fin = min(inicio + bloque, n)
        similitudes = matriz[inicio:fin] @ matriz.T
        filas = np.arange(inicio, fin)[:, None]
        # solo la mitad superior (j > i): cada par se evalua una vez
        fi, cj = np.nonzero((similitudes >= umbral) & (columnas[None, :] > filas))
        for f, c in zip(fi, cj):
            pares.append(
                ParCandidato(
                    indicador_a_id=int(ids[inicio + f]),
                    indicador_b_id=int(ids[c]),
                    modelo=nombre_modelo,
                    similitud_coseno=float(similitudes[f, c]),
                )
            )

    ParCandidato.objects.bulk_create(pares, ignore_conflicts=True)
    return len(pares)
