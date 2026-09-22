from django.conf import settings
from django.db import models

from apps.gobernanza.models import EjecucionAuditoria, ParametroGobernanza
from apps.ingesta.models import Indicador


class ReglaAuditoria(models.Model):
    """Regla implementada que materializa un ParametroGobernanza.

    Es la pieza que responde el criterio de "cobertura": cada parametro
    identificado en la revision documental debe poder rastrearse hasta una
    fila de esta tabla (o quedar explicitamente como resultado negativo,
    ver monografia Sec. "Hallazgos esperados").
    """

    TIPO_HALLAZGO_CHOICES = [
        ("duplicidad", "Duplicidad"),
        ("clonacion", "Clonación"),
        ("divergencia_operativa", "Divergencia operativa"),
        ("incompletitud_atributos", "Incompletitud de atributos"),
        ("problema_metodologico", "Problema metodológico"),
    ]

    nombre = models.CharField(max_length=200)
    tipo_hallazgo = models.CharField(max_length=30, choices=TIPO_HALLAZGO_CHOICES)
    descripcion = models.TextField()
    parametro_gobernanza = models.ForeignKey(
        ParametroGobernanza, on_delete=models.PROTECT, related_name="reglas"
    )
    configuracion = models.JSONField(
        default=dict,
        blank=True,
        help_text="Umbrales y parámetros de ejecución de la regla (ej. umbral_similitud).",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Regla de auditoría"
        verbose_name_plural = "Reglas de auditoría"
        ordering = ["tipo_hallazgo", "nombre"]

    def __str__(self):
        return self.nombre


class Hallazgo(models.Model):
    """Senalamiento producido por el motor de auditoria.

    La trazabilidad (regla_aplicada + atributos_comparados + evidencia) es
    obligatoria: un hallazgo que no informe estos tres elementos "carece de
    valor en un procedimiento de auditoria" (monografia, hallazgo sobre
    explicabilidad). El estado de revision refleja que el prototipo señala,
    pero no determina de forma autonoma: la confirmacion es del auditor
    humano.
    """

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente de revisión"),
        ("confirmado", "Confirmado por auditor"),
        ("descartado", "Descartado por auditor"),
    ]

    tipo = models.CharField(max_length=30, choices=ReglaAuditoria.TIPO_HALLAZGO_CHOICES)
    ejecucion = models.ForeignKey(
        EjecucionAuditoria, on_delete=models.CASCADE, related_name="hallazgos"
    )
    regla_aplicada = models.ForeignKey(
        ReglaAuditoria, on_delete=models.PROTECT, related_name="hallazgos"
    )

    indicador_principal = models.ForeignKey(
        Indicador, on_delete=models.CASCADE, related_name="hallazgos_como_principal"
    )
    indicador_relacionado = models.ForeignKey(
        Indicador,
        on_delete=models.CASCADE,
        related_name="hallazgos_como_relacionado",
        null=True,
        blank=True,
        help_text="Nulo para hallazgos de un solo indicador (incompletitud, problema metodológico).",
    )

    atributos_comparados = models.JSONField(
        help_text="Snapshot de los valores comparados entre indicador_principal e indicador_relacionado."
    )
    score_similitud = models.FloatField(null=True, blank=True)
    evidencia = models.TextField(
        help_text="Justificación legible por humano: qué se comparó y por qué constituye un hallazgo."
    )
    explicacion_llm = models.TextField(
        blank=True,
        help_text="Explicación generada por Qwen2.5 (Ollama) para apoyar la revisión del auditor.",
    )

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    observacion_revision = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Hallazgo"
        verbose_name_plural = "Hallazgos"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["tipo", "estado"]),
            models.Index(fields=["ejecucion"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.indicador_principal_id}"


class CorrespondenciaManual(models.Model):
    """Comparacion de un Hallazgo contra la caracterizacion manual (Informe
    de Duplicidad). Materializa el criterio de "correspondencia" de la
    estrategia de validacion; se diligencia cuando se dispone del dataset
    real y de la caracterizacion de referencia.
    """

    TIPO_CHOICES = [
        ("coincidente", "Coincide con caracterización manual"),
        ("no_coincidente", "No coincide con caracterización manual"),
        ("adicional", "Hallazgo adicional no identificado manualmente"),
    ]

    hallazgo = models.OneToOneField(
        Hallazgo, on_delete=models.CASCADE, related_name="correspondencia"
    )
    tipo_correspondencia = models.CharField(max_length=20, choices=TIPO_CHOICES)
    observacion = models.TextField(blank=True)
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Correspondencia manual"
        verbose_name_plural = "Correspondencias manuales"

    def __str__(self):
        return f"{self.hallazgo_id} — {self.get_tipo_correspondencia_display()}"
