"""Comparacion de vigencias: indicadores, hallazgos y variacion entre ellas."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.auditoria.models import Hallazgo
from apps.gobernanza.models import EjecucionAuditoria
from apps.ingesta.models import Indicador


def variacion(actual, anterior):
    """Variacion porcentual de `actual` respecto de `anterior` (None si no hay base)."""
    if actual is None or anterior in (None, 0):
        return None
    return round((actual - anterior) * 100 / anterior, 1)


def resumen_por_vigencia(vigencias):
    """Para cada vigencia: indicadores y hallazgos de su ultima ejecucion."""
    filas = []
    previo = None  # hallazgos de la vigencia anterior que tiene auditoria
    for v in vigencias:
        indicadores = Indicador.objects.filter(vigencia=v).count()
        ejecucion = EjecucionAuditoria.objects.filter(vigencia=v).order_by("-iniciada_en", "-pk").first()
        hallazgos = ejecucion.hallazgos.count() if ejecucion else None
        por_tipo = (
            dict(ejecucion.hallazgos.values_list("tipo").annotate(n=Count("id")).values_list("tipo", "n"))
            if ejecucion else {}
        )
        involucrados = None
        if ejecucion:
            # indicadores que aparecen en algun hallazgo, como principal o como relacionado
            ids = set(ejecucion.hallazgos.values_list("indicador_principal_id", flat=True))
            ids |= set(ejecucion.hallazgos.values_list("indicador_relacionado_id", flat=True))
            ids.discard(None)
            involucrados = len(ids)
        filas.append({
            "vigencia": v,
            "indicadores": indicadores,
            "involucrados": involucrados,
            "pct_involucrados": round(involucrados * 100 / indicadores) if involucrados is not None and indicadores else None,
            "ejecucion": ejecucion,
            "hallazgos": hallazgos,
            "por_tipo": por_tipo,
            "por_indicador": round(hallazgos / indicadores, 2) if hallazgos is not None and indicadores else None,
            "variacion": variacion(hallazgos, previo),
        })
        if hallazgos is not None:
            previo = hallazgos
    return filas


@login_required
def comparar(request):
    disponibles = list(Indicador.objects.order_by("vigencia").values_list("vigencia", flat=True).distinct())
    seleccion = sorted(v for v in set(request.GET.getlist("vigencias")) if v in disponibles)
    sin_seleccion = not seleccion
    if sin_seleccion:
        seleccion = disponibles  # por defecto, todas las vigencias cargadas

    filas = resumen_por_vigencia(seleccion)
    tipos = Hallazgo._meta.get_field("tipo").choices
    tabla_tipos = [
        {"etiqueta": etiqueta, "valores": [f["por_tipo"].get(clave) if f["ejecucion"] else None for f in filas]}
        for clave, etiqueta in tipos
    ]
    grafica = {
        "etiquetas": [f["vigencia"] for f in filas],
        "indicadores": [f["indicadores"] for f in filas],
        "hallazgos": [f["hallazgos"] for f in filas],
        "variacion": [f["variacion"] for f in filas],
    }
    return render(request, "dashboard/comparar.html", {
        "disponibles": disponibles,
        "seleccion": seleccion,
        "sin_seleccion": sin_seleccion,
        "filas": filas,
        "tabla_tipos": tabla_tipos,
        "total_indicadores": sum(f["indicadores"] for f in filas),
        "sin_auditoria": [f["vigencia"] for f in filas if f["ejecucion"] is None],
        "grafica": grafica,
    })
