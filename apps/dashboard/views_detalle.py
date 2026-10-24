"""Detalle de las variables observables del tablero (una pagina por tarjeta)."""

from collections import Counter, defaultdict

from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from apps.auditoria.models import CorrespondenciaManual, Hallazgo, ReglaAuditoria
from apps.auditoria.presentacion import ETIQUETAS
from apps.auditoria.reglas import es_trazable
from apps.gobernanza.models import EjecucionAuditoria, ParametroGobernanza
from apps.ingesta.models import Indicador
from apps.gobernanza.permisos import requiere_permiso

LIMITE = 300


@requiere_permiso("gobernanza.view_ejecucionauditoria")
def parametros(request, pk):
    """Variable 1: matriz parametro -> regla -> hallazgos."""
    ejecucion = get_object_or_404(EjecucionAuditoria, pk=pk)
    por_parametro = {
        f["regla_aplicada__parametro_gobernanza_id"]: f["n"]
        for f in ejecucion.hallazgos.values("regla_aplicada__parametro_gobernanza_id").annotate(n=Count("id"))
    }
    reglas = defaultdict(list)
    for regla in ReglaAuditoria.objects.filter(activa=True):
        reglas[regla.parametro_gobernanza_id].append(regla)
    aplicados = set(ejecucion.parametros_aplicados.values_list("pk", flat=True))

    filas = []
    for p in ParametroGobernanza.objects.all():
        rs = reglas.get(p.pk, [])
        filas.append({
            "parametro": p,
            "reglas": rs,
            "tipos": sorted({r.tipo_hallazgo for r in rs}),
            "hallazgos": por_parametro.get(p.pk, 0) if rs else None,
            "aplicado": p.pk in aplicados,
        })
    conteo = Counter(p["parametro"].operacionalizacion for p in filas)
    return render(request, "dashboard/detalle_parametros.html", {
        "ejecucion": ejecucion, "filas": filas,
        "si": conteo["si"], "parcial": conteo["parcial"], "no": conteo["no"], "total": len(filas),
    })


@requiere_permiso("gobernanza.view_ejecucionauditoria")
def correspondencia(request, pk):
    """Variable 3: avance del contraste con la caracterizacion manual."""
    ejecucion = get_object_or_404(EjecucionAuditoria, pk=pk)
    hallazgos = ejecucion.hallazgos.select_related("indicador_principal__dependencia", "correspondencia")
    registrados = {c.hallazgo_id: c for c in CorrespondenciaManual.objects.filter(hallazgo__ejecucion=ejecucion)}

    grupos = {
        "sin_registrar": "Sin registrar",
        "coincidente": "Coincidentes",
        "no_coincidente": "No coincidentes",
        "adicional": "Adicionales",
    }
    clasificados = {clave: [] for clave in grupos}
    for h in hallazgos:
        c = registrados.get(h.pk)
        clasificados[c.tipo_correspondencia if c else "sin_registrar"].append(h)

    grupo = request.GET.get("grupo", "sin_registrar")
    if grupo not in grupos:
        grupo = "sin_registrar"
    return render(request, "dashboard/detalle_correspondencia.html", {
        "ejecucion": ejecucion,
        "grupos": [(clave, etiqueta, len(clasificados[clave])) for clave, etiqueta in grupos.items()],
        "grupo": grupo,
        "grupo_etiqueta": grupos[grupo],
        "hallazgos": clasificados[grupo][:LIMITE],
        "total_grupo": len(clasificados[grupo]),
        "total": sum(len(v) for v in clasificados.values()),
        "limite": LIMITE,
    })


@requiere_permiso("gobernanza.view_ejecucionauditoria")
def trazabilidad(request, pk):
    """Variable 4: cada hallazgo informa regla, atributos comparados y evidencia."""
    ejecucion = get_object_or_404(EjecucionAuditoria, pk=pk)
    hallazgos = list(ejecucion.hallazgos.select_related("indicador_principal", "regla_aplicada"))
    por_tipo = defaultdict(lambda: {"total": 0, "trazables": 0})
    for h in hallazgos:
        fila = por_tipo[h.get_tipo_display()]
        fila["total"] += 1
        fila["trazables"] += int(es_trazable(h))
    excepciones = [h for h in hallazgos if not es_trazable(h)]
    return render(request, "dashboard/detalle_trazabilidad.html", {
        "ejecucion": ejecucion,
        "total": len(hallazgos),
        "con_regla": sum(1 for h in hallazgos if h.regla_aplicada_id),
        "con_atributos": sum(1 for h in hallazgos if h.atributos_comparados),
        "con_evidencia": sum(1 for h in hallazgos if (h.evidencia or "").strip()),
        "trazables": len(hallazgos) - len(excepciones),
        "por_tipo": [{"tipo": t, **v} for t, v in sorted(por_tipo.items())],
        "excepciones": excepciones[:LIMITE],
    })


def _pct(parte, total):
    return round(parte * 100 / total) if total else 0


@requiere_permiso("gobernanza.view_ejecucionauditoria")
def completitud(request, pk):
    """Variable 5: que atributos de la hoja de vida faltan, en que dependencias."""
    ejecucion = get_object_or_404(EjecucionAuditoria, pk=pk)
    indicadores = list(Indicador.objects.filter(vigencia=ejecucion.vigencia).select_related("dependencia"))

    por_atributo = Counter()           # atributo -> indicadores que lo tienen
    por_dependencia = defaultdict(lambda: {"indicadores": 0, "llenos": 0, "exigidos": 0})
    con_faltantes = []
    for i in indicadores:
        atributos = i.atributos_diligenciados()
        faltan = [c for c, ok in atributos.items() if not ok]
        for campo, ok in atributos.items():
            por_atributo[campo] += int(ok)
        d = por_dependencia[i.dependencia.nombre]
        d["indicadores"] += 1
        d["llenos"] += len(atributos) - len(faltan)
        d["exigidos"] += len(atributos)
        if faltan:
            con_faltantes.append((i, faltan))

    total = len(indicadores)
    filtro = request.GET.get("atributo")
    if filtro and filtro in ETIQUETAS:
        lista = [(i, f) for i, f in con_faltantes if filtro in f]
    else:
        filtro, lista = None, con_faltantes
    lista.sort(key=lambda par: (-len(par[1]), par[0].dependencia.nombre, par[0].nombre))

    campos = list(indicadores[0].atributos_diligenciados()) if indicadores else []
    return render(request, "dashboard/detalle_completitud.html", {
        "ejecucion": ejecucion,
        "total": total,
        "atributos": sorted(
            [{"campo": c, "etiqueta": ETIQUETAS.get(c, c), "tienen": por_atributo[c], "pct": _pct(por_atributo[c], total)} for c in campos],
            key=lambda a: a["pct"],
        ),
        "dependencias": sorted(
            [{"nombre": n, "indicadores": v["indicadores"], "pct": _pct(v["llenos"], v["exigidos"])} for n, v in por_dependencia.items()],
            key=lambda d: (d["pct"], d["nombre"]),
        ),
        "lista": [{"indicador": i, "faltan": [ETIQUETAS.get(c, c) for c in f]} for i, f in lista[:LIMITE]],
        "total_lista": len(lista),
        "filtro": filtro,
        "filtro_etiqueta": ETIQUETAS.get(filtro, "") if filtro else "",
        "limite": LIMITE,
    })
