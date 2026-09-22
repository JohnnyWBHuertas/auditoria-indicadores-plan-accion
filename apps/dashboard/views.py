from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.auditoria.models import Hallazgo
from apps.auditoria.reglas import ejecutar_auditoria
from apps.gobernanza.models import EjecucionAuditoria
from apps.ingesta.models import Indicador


def inicio(request):
    """CU5 (parte 1): consulta de resultados en el tablero."""
    ultima_ejecucion = EjecucionAuditoria.objects.order_by("-iniciada_en").first()
    vigencias_disponibles = (
        Indicador.objects.values_list("vigencia", flat=True).distinct().order_by("-vigencia")
    )

    if request.method == "POST" and request.POST.get("accion") == "ejecutar_auditoria":
        vigencia = request.POST.get("vigencia")
        if vigencia:
            ejecucion = ejecutar_auditoria(vigencia, usuario=request.user if request.user.is_authenticated else None)
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
    return render(request, "dashboard/inicio.html", contexto)


def hallazgos(request):
    """CU5 (parte 2): listado filtrable de hallazgos con su evidencia."""
    qs = Hallazgo.objects.select_related(
        "indicador_principal", "indicador_relacionado", "regla_aplicada", "ejecucion"
    ).order_by("-creado_en")

    tipo = request.GET.get("tipo")
    estado = request.GET.get("estado")
    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)

    contexto = {
        "hallazgos": qs[:300],
        "tipo_choices": Hallazgo._meta.get_field("tipo").choices,
        "estado_choices": Hallazgo.ESTADO_CHOICES,
        "tipo_seleccionado": tipo,
        "estado_seleccionado": estado,
    }
    return render(request, "dashboard/hallazgos.html", contexto)


def hallazgo_detalle(request, pk):
    hallazgo = get_object_or_404(
        Hallazgo.objects.select_related("indicador_principal", "indicador_relacionado", "regla_aplicada"),
        pk=pk,
    )

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion in {"confirmar", "descartar"}:
            hallazgo.estado = "confirmado" if accion == "confirmar" else "descartado"
            hallazgo.revisado_por = request.user if request.user.is_authenticated else None
            hallazgo.revisado_en = timezone.now()
            hallazgo.observacion_revision = request.POST.get("observacion", "")
            hallazgo.save()
            messages.success(request, "Hallazgo actualizado.")
            return redirect("dashboard:hallazgo_detalle", pk=pk)

    return render(request, "dashboard/hallazgo_detalle.html", {"hallazgo": hallazgo})
