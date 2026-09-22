from django.conf import settings
from django.db import models


class Dependencia(models.Model):
    """Grupo interno de trabajo / dependencia que registra su propio Plan de Accion.

    Unidad de custodia de indicadores (monografia, parametro de gobernanza:
    "asignacion de custodia por dependencia").
    """

    nombre = models.CharField(max_length=255, unique=True)
    tipo = models.CharField(
        max_length=50,
        choices=[("grupo", "Grupo interno de trabajo"), ("despacho", "Despacho/Dirección")],
        default="grupo",
    )

    class Meta:
        verbose_name = "Dependencia"
        verbose_name_plural = "Dependencias"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ParametroGobernanza(models.Model):
    """Parametro derivado de la revision documental de la monografia.

    Cada instancia es la unidad que el criterio de "cobertura" (Sec. de
    validacion del prototipo) exige rastrear: debe poder expresarse como
    una regla, un atributo evaluable o un umbral dentro del sistema.
    """

    CATEGORIA_CHOICES = [
        ("gobernanza", "Gobernanza de datos"),
        ("calidad", "Calidad de datos"),
        ("auditoria", "Auditoría de datos"),
        ("representacion_semantica", "Representación semántica"),
    ]

    nombre = models.CharField(max_length=255)
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.TextField()
    fuente_bibliografica = models.CharField(
        max_length=255,
        blank=True,
        help_text="Referencia APA de la fuente de la que se deriva el parámetro.",
    )
    operacionalizado = models.BooleanField(
        default=False,
        help_text="Indica si el parámetro ya quedó expresado como regla/atributo/umbral en el prototipo.",
    )

    class Meta:
        verbose_name = "Parámetro de gobernanza"
        verbose_name_plural = "Parámetros de gobernanza"
        ordering = ["categoria", "nombre"]

    def __str__(self):
        return f"[{self.get_categoria_display()}] {self.nombre}"


class EjecucionAuditoria(models.Model):
    """Registro de una corrida completa del pipeline de auditoria (CU1-CU5).

    Persiste la evidencia del criterio de "operabilidad local": cada
    ejecucion deja constancia de que el procesamiento no requirio
    conexion a servicios externos.
    """

    vigencia = models.CharField(max_length=9, help_text="Ej. 2025, 2026")
    iniciada_en = models.DateTimeField(auto_now_add=True)
    finalizada_en = models.DateTimeField(null=True, blank=True)
    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    ejecucion_100_por_ciento_local = models.BooleanField(default=True)
    parametros_aplicados = models.ManyToManyField(ParametroGobernanza, blank=True)

    # Variables observables (Sec. de validacion, seis variables descriptivas).
    resumen_metricas = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Snapshot de las 6 variables observables: parámetros operacionalizados, "
            "hallazgos por tipo, correspondencia con caracterización manual, "
            "proporción con evidencia trazable, completitud de hoja de vida, "
            "confirmación de ejecución local."
        ),
    )

    class Meta:
        verbose_name = "Ejecución de auditoría"
        verbose_name_plural = "Ejecuciones de auditoría"
        ordering = ["-iniciada_en"]

    def __str__(self):
        return f"Auditoría {self.vigencia} — {self.iniciada_en:%Y-%m-%d %H:%M}"
