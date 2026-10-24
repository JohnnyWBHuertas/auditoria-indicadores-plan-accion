from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.auditoria.models import CorrespondenciaManual, Hallazgo
from apps.auditoria.presentacion import presentar
from apps.auditoria.reglas import conteo_correspondencia, ejecutar_auditoria
from apps.gobernanza.models import Dependencia, EjecucionAuditoria
from apps.gobernanza.permisos import requiere_permiso
from apps.nlp_engine.embeddings import ModeloNoDisponible
from apps.ingesta.models import Indicador


def _porcentaje(proporcion):
    return None if proporcion is None else round(proporcion * 100)


@requiere_permiso("gobernanza.view_ejecucionauditoria")
def inicio(request):
    """CU5 (parte 1): consulta de resultados en el tablero."""
    ultima_ejecucion = EjecucionAuditoria.objects.order_by("-iniciada_en", "-pk").first()
    vigencias_disponibles = (
        Indicador.objects.values_list("vigencia", flat=True).distinct().order_by("-vigencia")
    )

    if request.method == "POST" and request.POST.get("accion") == "ejecutar_auditoria":
        if not request.user.has_perm("gobernanza.add_ejecucionauditoria"):
            raise PermissionDenied
        vigencia = request.POST.get("vigencia")
        if vigencia:
            try:
                ejecucion = ejecutar_auditoria(vigencia, usuario=request.user)
            except ModeloNoDisponible as exc:
                messages.error(request, str(exc))
                return redirect("dashboard:inicio")
            messages.success(
                request, f"Auditoría ejecutada sobre la vigencia {vigencia}: {ejecucion.hallazgos.count()} hallazgos."
            )
            return redirect("dashboard:inicio")
        messages.error(request, "Seleccione una vigencia con indicadores cargados.")

    contexto = {
        "ultima_ejecucion": ultima_ejecucion,
        "vigencias_disponibles": vigencias_disponibles,
        "total_indicadores": Indicador.objects.count(),
    }
    if ultima_ejecucion:
        metricas = ultima_ejecucion.resumen_metricas
        contexto.update(
            pct_evidencia=_porcentaje(metricas.get("proporcion_evidencia_trazable")),
            pct_completitud=_porcentaje(metricas.get("completitud_hoja_de_vida")),
            correspondencia=conteo_correspondencia(ultima_ejecucion),
            hallazgos_por_dependencia=list(
                ultima_ejecucion.hallazgos.values(
                    "indicador_principal__dependencia_id", "indicador_principal__dependencia__nombre"
                )
                .annotate(total=Count("id"))
                .order_by("-total", "indicador_principal__dependencia__nombre")
            ),
        )
    return render(request, "dashboard/inicio.html", contexto)


@requiere_permiso("auditoria.view_hallazgo")
def hallazgos(request):
    """CU5 (parte 2): listado filtrable de hallazgos con su evidencia."""
    qs = Hallazgo.objects.select_related(
        "indicador_principal__dependencia", "indicador_relacionado", "regla_aplicada", "ejecucion"
    ).order_by("-creado_en")

    tipo = request.GET.get("tipo")
    estado = request.GET.get("estado")
    dependencia = request.GET.get("dependencia")
    ejecucion = request.GET.get("ejecucion")
    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if dependencia:
        qs = qs.filter(indicador_principal__dependencia_id=dependencia)
    ejecucion_seleccionada = None
    if ejecucion and ejecucion.isdigit():
        qs = qs.filter(ejecucion_id=ejecucion)
        ejecucion_seleccionada = EjecucionAuditoria.objects.filter(pk=ejecucion).first()

    contexto = {
        "total": qs.count(),
        "ejecucion_seleccionada": ejecucion_seleccionada,
        "hallazgos": qs[:300],
        "tipo_choices": Hallazgo._meta.get_field("tipo").choices,
        "estado_choices": Hallazgo.ESTADO_CHOICES,
        "dependencias": Dependencia.objects.all(),
        "tipo_seleccionado": tipo,
        "estado_seleccionado": estado,
        "dependencia_seleccionada": dependencia,
    }
    return render(request, "dashboard/hallazgos.html", contexto)


@requiere_permiso("auditoria.view_hallazgo")
def hallazgo_detalle(request, pk):
    hallazgo = get_object_or_404(
        Hallazgo.objects.select_related(
            "indicador_principal__dependencia", "indicador_relacionado__dependencia", "regla_aplicada"
        ),
        pk=pk,
    )

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion in {"confirmar", "descartar"}:
            if not request.user.has_perm("auditoria.change_hallazgo"):
                raise PermissionDenied
            hallazgo.estado = "confirmado" if accion == "confirmar" else "descartado"
            hallazgo.revisado_por = request.user
            hallazgo.revisado_en = timezone.now()
            hallazgo.observacion_revision = request.POST.get("observacion", "")
            hallazgo.save()
            messages.success(request, "Hallazgo actualizado.")
            return redirect("dashboard:hallazgo_detalle", pk=pk)
        if accion == "correspondencia":
            if not request.user.has_perms(["auditoria.add_correspondenciamanual", "auditoria.change_correspondenciamanual"]):
                raise PermissionDenied
            tipo = request.POST.get("tipo_correspondencia")
            if tipo in dict(CorrespondenciaManual.TIPO_CHOICES):
                CorrespondenciaManual.objects.update_or_create(
                    hallazgo=hallazgo,
                    defaults={
                        "tipo_correspondencia": tipo,
                        "observacion": request.POST.get("observacion_correspondencia", ""),
                    },
                )
                ejecucion = hallazgo.ejecucion
                ejecucion.resumen_metricas["correspondencia_manual"] = conteo_correspondencia(ejecucion)
                ejecucion.save(update_fields=["resumen_metricas"])
                messages.success(request, "Correspondencia con la caracterización manual registrada.")
            else:
                messages.error(request, "Seleccione un tipo de correspondencia válido.")
            return redirect("dashboard:hallazgo_detalle", pk=pk)

    contexto = {
        "hallazgo": hallazgo,
        "detalle": presentar(hallazgo),
        "correspondencia": getattr(hallazgo, "correspondencia", None),
        "correspondencia_choices": CorrespondenciaManual.TIPO_CHOICES,
    }
    return render(request, "dashboard/hallazgo_detalle.html", contexto)
