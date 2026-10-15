from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CargaArchivoForm
from .models import CargaArchivo
from .services import procesar_archivo


@login_required
def cargar_archivo(request):
    """CU1: cargar el reporte de una vigencia y normalizar la hoja de vida,
    verificando que la estructura se preserve (ver CargaArchivo.filas_*)."""
    if request.method == "POST":
        form = CargaArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            carga: CargaArchivo = form.save(commit=False)
            carga.cargado_por = request.user
            carga.nombre_archivo = request.FILES["archivo"].name
            carga.save()
            procesar_archivo(carga)
            carga.refresh_from_db()
            if carga.estado == "fallido":
                messages.error(request, f"La carga falló: {carga.detalle_errores}")
            else:
                messages.success(
                    request,
                    f"Carga {carga.get_estado_display()}: {carga.filas_cargadas}/{carga.filas_totales} filas normalizadas.",
                )
            return redirect("ingesta:historial")
    else:
        form = CargaArchivoForm()

    return render(request, "ingesta/cargar.html", {"form": form})


@login_required
def historial(request):
    cargas = CargaArchivo.objects.select_related("plantilla").order_by("-cargado_en")[:50]
    return render(request, "ingesta/historial.html", {"cargas": cargas})
