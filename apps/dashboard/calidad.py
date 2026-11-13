"""Cifras del tablero de calidad y priorizacion (mejora 5 del jurado V).

Todas se calculan con consultas directas sobre la base (sin uniones que
dupliquen filas), para poder compararlas con el conteo de cada filtro.
"""

from __future__ import annotations

from django.db.models import Count, Q

from apps.auditoria.models import Hallazgo
from apps.ingesta.models import Indicador

ATRIBUTOS = [
    ("nombre", "Nombre"), ("objetivo", "Objetivo"), ("formula", "Fórmula"), ("unidad_medida", "Unidad de medida"),
    ("linea_base", "Línea base"), ("meta", "Meta"), ("periodicidad", "Periodicidad"), ("fuente", "Fuente"),
    ("responsable", "Responsable"),
]
TOP_DEPENDENCIAS = 10


def completitud_por_atributo(vigencia):
    indicadores = Indicador.objects.filter(vigencia=vigencia)
    total = indicadores.count()
    filas = []
    for campo, etiqueta in ATRIBUTOS:
        vacio = Q(**{campo: ""}) | Q(**{campo + "__isnull": True})
        if campo == "periodicidad":
            vacio = Q(periodicidad="no_especificada") | Q(periodicidad="")
        faltan = indicadores.filter(vacio).count()
        filas.append({
            "campo": campo, "etiqueta": etiqueta, "diligenciados": total - faltan, "total": total,
            "porcentaje": round(100 * (total - faltan) / total, 1) if total else None,
        })
    return filas


def datos_calidad(ejecucion) -> dict:
    hallazgos = Hallazgo.objects.filter(ejecucion=ejecucion)
    por_tipo = {r["tipo"]: r["n"] for r in hallazgos.values("tipo").annotate(n=Count("pk"))}
    # «valor faltante» es un subresultado de la regla de divergencia: se cuenta aparte, sin sumarlo a la divergencia
    faltantes = hallazgos.filter(tipo="divergencia_operativa", atributos_comparados__clasificacion="valor_faltante").count()
    if faltantes:
        por_tipo["divergencia_operativa"] -= faltantes
        por_tipo["valor_faltante"] = faltantes
    por_estado = {r["estado"]: r["n"] for r in hallazgos.values("estado").annotate(n=Count("pk"))}
    total = sum(por_tipo.values())
    revisados = por_estado.get("confirmado", 0) + por_estado.get("descartado", 0)
    dependencias = list(
        hallazgos.values("indicador_principal__dependencia_id", "indicador_principal__dependencia__nombre")
        .annotate(total=Count("pk"))
        .order_by("-total", "indicador_principal__dependencia__nombre")[:TOP_DEPENDENCIAS]
    )
    return {
        "total": total,
        "por_tipo": por_tipo,
        "por_estado": {e: por_estado.get(e, 0) for e in ("pendiente", "confirmado", "descartado")},
        "revisados": revisados,
        "pct_revisados": round(100 * revisados / total, 1) if total else 0,
        "dependencias": [
            {"id": d["indicador_principal__dependencia_id"], "nombre": d["indicador_principal__dependencia__nombre"], "total": d["total"]}
            for d in dependencias
        ],
        "completitud": completitud_por_atributo(ejecucion.vigencia),
    }
