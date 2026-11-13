"""Comparacion de dos ejecuciones de auditoria (E11, V-M6).

Dos corridas con la misma huella de datos, el mismo modelo, las mismas reglas
y los mismos umbrales deben producir los mismos senalamientos. Los
hallazgos se comparan por contenido (indicadores, tipo y similitud), no por ID.
"""

from __future__ import annotations

from collections import Counter

from .models import Hallazgo


def _clave(i):
    return (i.dependencia.nombre, i.programa, i.bien_servicio, i.nombre, i.producto_actividad_proyecto, i.vigencia)


def firma_hallazgos(ejecucion) -> Counter:
    firma = Counter()
    for h in Hallazgo.objects.filter(ejecucion=ejecucion).select_related(
        "indicador_principal__dependencia", "indicador_relacionado__dependencia"
    ):
        firma[(
            h.tipo,
            _clave(h.indicador_principal),
            _clave(h.indicador_relacionado) if h.indicador_relacionado else None,
            None if h.score_similitud is None else round(h.score_similitud, 4),
        )] += 1
    return firma


def configuracion(ejecucion) -> dict:
    p = ejecucion.parametros_ejecucion or {}
    return {
        "vigencia": ejecucion.vigencia,
        "huella_datos": ejecucion.huella_datos,
        "modelo": ejecucion.modelo_embeddings,
        "revision_modelo": ejecucion.revision_modelo,
        "version_reglas": ejecucion.version_reglas,
        "version_aplicacion": ejecucion.version_aplicacion,
        "umbral_duplicidad": p.get("umbral_duplicidad"),
        "umbral_clonacion_textual": p.get("umbral_clonacion_textual"),
        "indicadores_procesados": ejecucion.indicadores_procesados,
    }


def comparar(a, b) -> dict:
    ca, cb = configuracion(a), configuracion(b)
    diferencias_config = {k: (ca[k], cb[k]) for k in ca if ca[k] != cb[k]}
    fa, fb = firma_hallazgos(a), firma_hallazgos(b)
    solo_a, solo_b = fa - fb, fb - fa
    return {
        "configuracion_igual": not diferencias_config,
        "diferencias_configuracion": diferencias_config,
        "hallazgos_a": sum(fa.values()),
        "hallazgos_b": sum(fb.values()),
        "solo_en_a": sum(solo_a.values()),
        "solo_en_b": sum(solo_b.values()),
        "resultados_iguales": not solo_a and not solo_b,
        "equivalentes": not diferencias_config and not solo_a and not solo_b,
    }
