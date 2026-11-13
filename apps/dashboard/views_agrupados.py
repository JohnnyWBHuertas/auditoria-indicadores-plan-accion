from django.shortcuts import get_object_or_404, render

from apps.auditoria.agrupacion import CLASES, resumen_agrupacion
from apps.gobernanza.models import EjecucionAuditoria
from apps.gobernanza.permisos import requiere_permiso


@requiere_permiso("auditoria.view_hallazgo")
def agrupados(request, pk):
    """Pares señalados presentados por grupo de indicadores con el mismo nombre. No modifica ni oculta ningún hallazgo."""
    ejecucion = get_object_or_404(EjecucionAuditoria, pk=pk)
    resumen = resumen_agrupacion(ejecucion)
    clase = request.GET.get("clase")
    grupos = [g for g in resumen["grupos"] if not clase or g["clase"] == clase]
    return render(request, "dashboard/agrupados.html", {
        "ejecucion": ejecucion, "resumen": resumen, "grupos": grupos, "clases": CLASES, "clase_seleccionada": clase,
    })
