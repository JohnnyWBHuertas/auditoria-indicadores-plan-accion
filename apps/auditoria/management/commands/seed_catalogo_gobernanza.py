from django.core.management.base import BaseCommand

from apps.auditoria.models import ReglaAuditoria
from apps.gobernanza.models import ParametroGobernanza

PARAMETROS = [
    dict(
        nombre="Custodia de indicadores por dependencia",
        categoria="gobernanza",
        descripcion="Cada indicador queda bajo la responsabilidad de la dependencia que lo formuló.",
        fuente_bibliografica="Khatri y Brown (2010); DAMA International (2017)",
        operacionalizado=True,
    ),
    dict(
        nombre="Unicidad del indicador (versión única autorizada)",
        categoria="calidad",
        descripcion="Dos o más indicadores no deben representar la misma medición con identificadores distintos.",
        fuente_bibliografica="Loshin (2010); DAMA International (2017)",
        operacionalizado=True,
    ),
    dict(
        nombre="Consistencia de fórmula, unidad de medida y periodicidad",
        categoria="calidad",
        descripcion="Indicadores semánticamente equivalentes deben compartir método de cálculo, unidad y periodicidad.",
        fuente_bibliografica="ISO/IEC 25012 (2008); Batini et al. (2009)",
        operacionalizado=True,
    ),
    dict(
        nombre="Completitud de la hoja de vida del indicador",
        categoria="calidad",
        descripcion="Todo indicador debe diligenciar nombre, objetivo, fórmula, unidad de medida, línea base, meta, periodicidad, fuente y responsable.",
        fuente_bibliografica="DNP (2009); Función Pública (2021)",
        operacionalizado=True,
    ),
    dict(
        nombre="Trazabilidad y evidencia del hallazgo",
        categoria="auditoria",
        descripcion="Todo hallazgo debe informar la regla aplicada, los atributos comparados y la evidencia que lo sustenta.",
        fuente_bibliografica="Barredo Arrieta et al. (2020); Zhang et al. (2022)",
        operacionalizado=True,
    ),
    dict(
        nombre="Umbral de similitud semántica para duplicidad",
        categoria="representacion_semantica",
        descripcion="Representación vectorial de oraciones y umbral de coseno para separar coincidencia relevante de parecido casual.",
        fuente_bibliografica="Reimers y Gurevych (2019)",
        operacionalizado=True,
    ),
    dict(
        nombre="Estructura metodológica del nombre del indicador",
        categoria="calidad",
        descripcion="Un indicador válido se redacta como magnitud cuantificable acumulable, no como actividad puntual.",
        fuente_bibliografica="DNP (2009); Informe de Duplicidad de Indicadores PAA 2026 (caracterización institucional)",
        operacionalizado=True,
    ),
]

REGLAS = [
    dict(
        nombre="Similitud semántica sobre umbral de duplicidad",
        tipo_hallazgo="duplicidad",
        descripcion="Marca como duplicidad los pares cuya similitud de embeddings supera NLP_ENGINE.UMBRAL_DUPLICIDAD y no presentan coincidencia textual casi exacta.",
        parametro_nombre="Unicidad del indicador (versión única autorizada)",
    ),
    dict(
        nombre="Coincidencia textual casi exacta con variación marginal",
        tipo_hallazgo="clonacion",
        descripcion="Marca como clonación los pares con coincidencia textual >= UMBRAL_CLONACION_TEXTUAL en nombre+fórmula+meta y variación en dependencia, vigencia, meta o producto/actividad.",
        parametro_nombre="Custodia de indicadores por dependencia",
    ),
    dict(
        nombre="Equivalencia semántica con atributos técnicos divergentes",
        tipo_hallazgo="divergencia_operativa",
        descripcion="Marca como divergencia operativa los pares semánticamente equivalentes que difieren en unidad de medida o periodicidad (la fórmula, al ser texto libre, no se usa como disparador exacto).",
        parametro_nombre="Consistencia de fórmula, unidad de medida y periodicidad",
    ),
    dict(
        nombre="Verificación de completitud de la hoja de vida",
        tipo_hallazgo="incompletitud_atributos",
        descripcion="Marca como incompletitud los indicadores con campos obligatorios de la hoja de vida sin diligenciar.",
        parametro_nombre="Completitud de la hoja de vida del indicador",
    ),
    dict(
        nombre="Heurística léxica + clasificación Qwen2.5 para redacción como actividad",
        tipo_hallazgo="problema_metodologico",
        descripcion="Marca como problema metodológico los nombres redactados como actividad puntual en vez de indicador (regla léxica del Informe de Duplicidad, con desempate de Qwen2.5 en casos ambiguos).",
        parametro_nombre="Estructura metodológica del nombre del indicador",
    ),
]


class Command(BaseCommand):
    help = "Siembra el catálogo base de parámetros de gobernanza y reglas de auditoría (criterio de cobertura)."

    def handle(self, *args, **options):
        parametros_por_nombre = {}
        for datos in PARAMETROS:
            parametro, creado = ParametroGobernanza.objects.update_or_create(
                nombre=datos["nombre"], defaults=datos
            )
            parametros_por_nombre[datos["nombre"]] = parametro
            self.stdout.write(("Creado " if creado else "Actualizado ") + parametro.nombre)

        for datos in REGLAS:
            parametro = parametros_por_nombre[datos.pop("parametro_nombre")]
            regla, creado = ReglaAuditoria.objects.update_or_create(
                tipo_hallazgo=datos["tipo_hallazgo"],
                defaults={**datos, "parametro_gobernanza": parametro, "activa": True},
            )
            self.stdout.write(("Creada " if creado else "Actualizada ") + regla.nombre)

        self.stdout.write(self.style.SUCCESS("Catálogo de gobernanza y reglas sembrado."))
