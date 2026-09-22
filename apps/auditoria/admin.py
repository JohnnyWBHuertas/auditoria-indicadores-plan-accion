from django.contrib import admin

from .models import CorrespondenciaManual, Hallazgo, ReglaAuditoria


@admin.register(ReglaAuditoria)
class ReglaAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "tipo_hallazgo", "parametro_gobernanza", "activa"]
    list_filter = ["tipo_hallazgo", "activa"]


@admin.register(Hallazgo)
class HallazgoAdmin(admin.ModelAdmin):
    list_display = [
        "id", "tipo", "indicador_principal", "indicador_relacionado",
        "score_similitud", "estado", "creado_en",
    ]
    list_filter = ["tipo", "estado", "ejecucion"]
    search_fields = ["evidencia", "indicador_principal__nombre"]
    readonly_fields = ["creado_en"]


@admin.register(CorrespondenciaManual)
class CorrespondenciaManualAdmin(admin.ModelAdmin):
    list_display = ["hallazgo", "tipo_correspondencia", "registrado_en"]
    list_filter = ["tipo_correspondencia"]
