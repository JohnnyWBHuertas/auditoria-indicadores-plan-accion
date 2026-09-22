from django.contrib import admin

from .models import Dependencia, EjecucionAuditoria, ParametroGobernanza


@admin.register(Dependencia)
class DependenciaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "tipo"]
    search_fields = ["nombre"]


@admin.register(ParametroGobernanza)
class ParametroGobernanzaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "categoria", "operacionalizado"]
    list_filter = ["categoria", "operacionalizado"]
    search_fields = ["nombre", "descripcion"]


@admin.register(EjecucionAuditoria)
class EjecucionAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["vigencia", "iniciada_en", "finalizada_en", "ejecucion_100_por_ciento_local"]
    list_filter = ["vigencia", "ejecucion_100_por_ciento_local"]
