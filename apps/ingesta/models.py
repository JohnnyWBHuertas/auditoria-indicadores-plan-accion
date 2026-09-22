from django.conf import settings
from django.db import models

from apps.gobernanza.models import Dependencia


class PlantillaMapeoColumnas(models.Model):
    """Plantilla configurable de mapeo columna-origen -> campo de hoja de vida.

    La estructura del archivo exportado del sistema institucional puede
    cambiar entre vigencias, por lo que la ingesta se disena desacoplada
    del formato exacto del archivo (decision de arquitectura: sin dataset
    de referencia fijo, el cargue se resuelve por plantilla, no por
    posicion de columna).
    """

    nombre = models.CharField(max_length=150)
    vigencia = models.CharField(max_length=9)
    # {"columna_origen": "campo_hoja_de_vida", ...}
    mapeo_columnas = models.JSONField()
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plantilla de mapeo de columnas"
        verbose_name_plural = "Plantillas de mapeo de columnas"
        ordering = ["-creada_en"]

    def __str__(self):
        return f"{self.nombre} ({self.vigencia})"


class CargaArchivo(models.Model):
    """Traza de cada cargue de archivo (CU1): evidencia de que la estructura
    de la hoja de vida se preservo durante la normalizacion."""

    ESTADO_CHOICES = [
        ("procesando", "Procesando"),
        ("completado", "Completado"),
        ("completado_con_errores", "Completado con errores"),
        ("fallido", "Fallido"),
    ]

    archivo = models.FileField(upload_to="cargas/")
    plantilla = models.ForeignKey(PlantillaMapeoColumnas, on_delete=models.PROTECT)
    vigencia = models.CharField(max_length=9)
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    cargado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default="procesando")
    filas_totales = models.PositiveIntegerField(default=0)
    filas_cargadas = models.PositiveIntegerField(default=0)
    filas_con_error = models.PositiveIntegerField(default=0)
    detalle_errores = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Carga de archivo"
        verbose_name_plural = "Cargas de archivo"
        ordering = ["-cargado_en"]

    def __str__(self):
        return f"Carga {self.vigencia} — {self.archivo.name}"


class Indicador(models.Model):
    """Hoja de vida del indicador: entidad maestra del prototipo.

    Campos tomados de la definicion operativa de la monografia (nombre,
    objetivo, formula, unidad de medida, linea base, meta, periodicidad,
    fuente, responsable) mas los atributos organizacionales del Plan de
    Accion (dependencia, programa, bien/servicio, producto/actividad).
    """

    PERIODICIDAD_CHOICES = [
        ("mensual", "Mensual"),
        ("trimestral", "Trimestral"),
        ("semestral", "Semestral"),
        ("anual", "Anual"),
        ("no_especificada", "No especificada"),
    ]

    nombre = models.CharField(max_length=500)
    objetivo = models.TextField(blank=True)
    formula = models.TextField(blank=True)
    unidad_medida = models.CharField(max_length=150, blank=True)
    linea_base = models.CharField(max_length=150, blank=True)
    meta = models.CharField(max_length=150, blank=True)
    periodicidad = models.CharField(
        max_length=20, choices=PERIODICIDAD_CHOICES, default="no_especificada"
    )
    fuente = models.CharField(max_length=255, blank=True)
    responsable = models.CharField(max_length=255, blank=True)

    dependencia = models.ForeignKey(
        Dependencia, on_delete=models.PROTECT, related_name="indicadores"
    )
    programa = models.CharField(max_length=255, blank=True)
    bien_servicio = models.CharField(max_length=255, blank=True)
    producto_actividad_proyecto = models.CharField(max_length=500, blank=True)
    vigencia = models.CharField(max_length=9)

    carga_origen = models.ForeignKey(
        CargaArchivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="indicadores"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Indicador"
        verbose_name_plural = "Indicadores"
        ordering = ["dependencia__nombre", "nombre"]
        indexes = [
            models.Index(fields=["dependencia", "programa", "bien_servicio"]),
            models.Index(fields=["vigencia"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.dependencia})"

    def atributos_diligenciados(self) -> dict:
        """Base del calculo de completitud (dimension de calidad, ISO/IEC 25012)."""
        campos_exigidos = [
            "nombre", "objetivo", "formula", "unidad_medida",
            "linea_base", "meta", "periodicidad", "fuente", "responsable",
        ]
        return {campo: bool(getattr(self, campo)) for campo in campos_exigidos}


class LineaPAA(models.Model):
    """Linea del Plan Anual de Adquisiciones asociada a un indicador.

    Relacion muchos-a-uno por diseno institucional (un indicador puede
    tener varias lineas PAA; el fan-out promedio observado en el Informe
    de Duplicidad fue de 7.0 lineas por indicador).
    """

    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name="lineas_paa")
    codigo_paa = models.CharField(max_length=100)
    vigencia = models.CharField(max_length=9)

    class Meta:
        verbose_name = "Línea PAA"
        verbose_name_plural = "Líneas PAA"
        unique_together = [("indicador", "codigo_paa")]

    def __str__(self):
        return self.codigo_paa


class HistorialCambioIndicador(models.Model):
    """Historial de modificaciones de la hoja de vida (append-only).

    Sin este registro la trazabilidad que exige la auditoria es inviable
    (definicion de "hoja de vida del indicador" en la monografia).
    """

    indicador = models.ForeignKey(Indicador, on_delete=models.CASCADE, related_name="historial")
    campo = models.CharField(max_length=100)
    valor_anterior = models.TextField(blank=True)
    valor_nuevo = models.TextField(blank=True)
    origen = models.CharField(
        max_length=30,
        choices=[("carga_archivo", "Carga de archivo"), ("edicion_manual", "Edición manual")],
    )
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de cambio"
        verbose_name_plural = "Historial de cambios"
        ordering = ["-registrado_en"]

    def __str__(self):
        return f"{self.indicador_id} — {self.campo} ({self.registrado_en:%Y-%m-%d})"
