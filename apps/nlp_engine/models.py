from django.db import models

from apps.ingesta.models import Indicador


class EmbeddingIndicador(models.Model):
    """Vector semantico de un indicador (CU2), generado con sentence-transformers.

    Se almacena independiente de cualquier hallazgo: el mismo embedding se
    reutiliza para deteccion de duplicidad y de divergencia operativa.
    """

    indicador = models.OneToOneField(
        Indicador, on_delete=models.CASCADE, related_name="embedding"
    )
    modelo = models.CharField(max_length=150)
    texto_fuente = models.TextField(
        help_text="Texto concatenado (nombre + objetivo) sobre el que se calculó el vector."
    )
    vector = models.JSONField(help_text="Lista de floats del embedding.")
    generado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Embedding de indicador"
        verbose_name_plural = "Embeddings de indicadores"

    def __str__(self):
        return f"Embedding({self.indicador_id}, {self.modelo})"


class ParCandidato(models.Model):
    """Par de indicadores senalado por similitud semantica (CU2).

    Es un candidato, no un hallazgo: la clasificacion final (duplicidad,
    divergencia operativa, o descarte por vocabulario compartido del
    sector) la aplica apps.auditoria a partir de este registro.
    """

    indicador_a = models.ForeignKey(
        Indicador, on_delete=models.CASCADE, related_name="pares_como_a"
    )
    indicador_b = models.ForeignKey(
        Indicador, on_delete=models.CASCADE, related_name="pares_como_b"
    )
    similitud_coseno = models.FloatField()
    modelo = models.CharField(max_length=150)
    generado_en = models.DateTimeField(auto_now_add=True)
    procesado = models.BooleanField(
        default=False, help_text="True cuando alguna ejecución de apps.auditoria ya evaluó este par."
    )

    class Meta:
        verbose_name = "Par candidato"
        verbose_name_plural = "Pares candidatos"
        unique_together = [("indicador_a", "indicador_b", "modelo")]
        indexes = [models.Index(fields=["procesado"])]

    def __str__(self):
        return f"{self.indicador_a_id} ~ {self.indicador_b_id} ({self.similitud_coseno:.3f})"
