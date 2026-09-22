from django.contrib import admin

from .models import EmbeddingIndicador, ParCandidato


@admin.register(EmbeddingIndicador)
class EmbeddingIndicadorAdmin(admin.ModelAdmin):
    list_display = ["indicador", "modelo", "generado_en"]
    list_filter = ["modelo"]


@admin.register(ParCandidato)
class ParCandidatoAdmin(admin.ModelAdmin):
    list_display = ["indicador_a", "indicador_b", "similitud_coseno", "procesado"]
    list_filter = ["procesado", "modelo"]
    ordering = ["-similitud_coseno"]
