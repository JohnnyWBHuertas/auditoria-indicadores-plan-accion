from django.contrib import admin

from .models import CargaArchivo, HistorialCambioIndicador, Indicador, LineaPAA, PlantillaMapeoColumnas


class LineaPAAInline(admin.TabularInline):
    model = LineaPAA
    extra = 0


class HistorialInline(admin.TabularInline):
    model = HistorialCambioIndicador
    extra = 0
    readonly_fields = ["campo", "valor_anterior", "valor_nuevo", "origen", "registrado_en"]
    can_delete = False


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ["nombre", "dependencia", "programa", "vigencia", "meta", "periodicidad"]
    list_filter = ["dependencia", "vigencia", "periodicidad"]
    search_fields = ["nombre", "objetivo", "formula"]
    inlines = [LineaPAAInline, HistorialInline]


@admin.register(PlantillaMapeoColumnas)
class PlantillaMapeoColumnasAdmin(admin.ModelAdmin):
    list_display = ["nombre", "vigencia", "activa"]
    list_filter = ["vigencia", "activa"]


@admin.register(CargaArchivo)
class CargaArchivoAdmin(admin.ModelAdmin):
    list_display = ["archivo", "vigencia", "estado", "filas_totales", "filas_cargadas", "filas_con_error", "cargado_en"]
    list_filter = ["estado", "vigencia"]
