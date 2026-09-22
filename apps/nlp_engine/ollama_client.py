"""Cliente Qwen2.5 via Ollama.

Uso restringido y deliberado (decision de arquitectura confirmada): este
modulo NUNCA calcula similitud semantica (eso es responsabilidad de
embeddings.py / sentence-transformers). Se usa exclusivamente para:

1. Clasificacion metodologica de casos ambiguos (indicador vs. actividad).
2. Generacion de explicaciones de hallazgos en lenguaje natural, para
   apoyar al auditor humano (nunca como determinacion autonoma).

Si Ollama no esta disponible, las funciones degradan a None/mensaje de
fallback en lugar de interrumpir el pipeline de auditoria: el hallazgo
basado en reglas ya es valido sin la explicacion del LLM.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _cliente():
    import ollama

    return ollama.Client(host=settings.OLLAMA["HOST"])


def clasificar_problema_metodologico(nombre_indicador: str) -> dict | None:
    """Determina si un nombre de indicador esta redactado como una actividad
    puntual en vez de una magnitud medible acumulable (heuristica del
    Informe de Duplicidad, resuelta por Qwen2.5 solo para casos que la
    regla lexica no puede clasificar con certeza).
    """
    prompt = (
        "Eres un auditor de indicadores de gestion publica en Colombia. "
        "Determina si el siguiente nombre de indicador esta redactado como "
        "una ACTIVIDAD puntual (verbo en infinitivo o accion puntual, ej. "
        "'Entregar...', 'Cierre de...', 'Creacion de...') en vez de un "
        "INDICADOR valido (magnitud cuantificable acumulable, ej. inicia en "
        "'Numero de', 'Porcentaje', 'Tasa', o termina en participio como "
        "'...realizados', '...implementados').\n\n"
        f'Nombre del indicador: "{nombre_indicador}"\n\n'
        "Responde solo con: CLASIFICACION: <actividad|indicador|ambiguo> "
        "seguido de JUSTIFICACION: <una frase breve>."
    )
    try:
        respuesta = _cliente().chat(
            model=settings.OLLAMA["MODEL"],
            messages=[{"role": "user", "content": prompt}],
        )
        texto = respuesta["message"]["content"]
    except Exception:
        logger.warning("No fue posible contactar Ollama para clasificación metodológica.", exc_info=True)
        return None

    return _parsear_clasificacion(texto)


def _parsear_clasificacion(texto: str) -> dict:
    clasificacion = "ambiguo"
    justificacion = texto.strip()
    for linea in texto.splitlines():
        if linea.upper().startswith("CLASIFICACION:"):
            valor = linea.split(":", 1)[1].strip().lower()
            if "actividad" in valor:
                clasificacion = "actividad"
            elif "indicador" in valor:
                clasificacion = "indicador"
        if linea.upper().startswith("JUSTIFICACION:"):
            justificacion = linea.split(":", 1)[1].strip()
    return {"clasificacion": clasificacion, "justificacion": justificacion, "respuesta_cruda": texto}


def explicar_hallazgo(
    tipo_hallazgo: str,
    regla: str,
    atributos_comparados: dict,
    evidencia_base: str,
) -> str:
    """Genera una explicacion en lenguaje natural para apoyar la revision
    del auditor humano. Nunca reemplaza evidencia_base (la evidencia
    determinista de la regla): la complementa.
    """
    prompt = (
        "Eres un asistente de auditoria de indicadores de gestion publica. "
        "Explica en maximo tres frases, en espanol claro y sin tecnicismos "
        "innecesarios, por que el siguiente hallazgo requiere revision de "
        f"un auditor humano.\n\nTipo de hallazgo: {tipo_hallazgo}\n"
        f"Regla aplicada: {regla}\n"
        f"Atributos comparados: {atributos_comparados}\n"
        f"Evidencia tecnica: {evidencia_base}\n\n"
        "No inventes datos que no esten en la evidencia tecnica."
    )
    try:
        respuesta = _cliente().chat(
            model=settings.OLLAMA["MODEL"],
            messages=[{"role": "user", "content": prompt}],
        )
        return respuesta["message"]["content"].strip()
    except Exception:
        logger.warning("No fue posible contactar Ollama para explicar el hallazgo.", exc_info=True)
        return ""
