from django.core.management.base import BaseCommand

from apps.auditoria.models import ReglaAuditoria
from apps.gobernanza.models import ParametroGobernanza

# Catalogo de los once parametros identificados en la revision documental,
# agrupados en los cinco tipos (uno por enfoque). El estado de
# operacionalizacion alimenta la variable observable 1 y el criterio de
# cobertura: parametros operacionalizados respecto del total identificado.
PARAMETROS = [
    dict(
        codigo="P01", nombre="Custodia por dependencia", categoria="gobernanza",
        descripcion="Cada indicador queda bajo la responsabilidad de la dependencia que lo formuló.",
        fuente_bibliografica="Khatri y Brown (2010); DAMA International (2017)",
        operacionalizacion="si",
        implementacion="Dependencia asociada a cada indicador; su variación es atributo de la regla de clonación.",
    ),
    dict(
        codigo="P02", nombre="Nomenclatura de indicadores", categoria="gobernanza",
        descripcion="Convención institucional para formular el nombre del indicador como magnitud medible.",
        fuente_bibliografica="Khatri y Brown (2010); DAMA International (2017)",
        operacionalizacion="parcial",
        implementacion="Solo se verifica la estructura léxica del nombre (P07); no existe una convención institucional que contrastar.",
    ),
    dict(
        codigo="P03", nombre="Aprobación previa al registro", categoria="gobernanza",
        descripcion="Un indicador nuevo se aprueba antes de registrarse en el Plan de Acción.",
        fuente_bibliografica="Khatri y Brown (2010); DAMA International (2017)",
        operacionalizacion="no",
        implementacion="Depende de un flujo institucional ajeno al prototipo; se plantea en las recomendaciones.",
    ),
    dict(
        codigo="P04", nombre="Unicidad del indicador (versión única)", categoria="datos_maestros",
        descripcion="Dos o más indicadores no deben representar la misma medición con identificadores distintos.",
        fuente_bibliografica="Loshin (2010); DAMA International (2017); Wang y Strong (1996)",
        operacionalizacion="si",
        implementacion="Reglas de duplicidad y de clonación sobre los pares candidatos del modelo de embeddings.",
    ),
    dict(
        codigo="P05", nombre="Consistencia de unidad de medida y periodicidad", categoria="calidad",
        descripcion="Indicadores semánticamente equivalentes deben compartir unidad de medida y periodicidad.",
        fuente_bibliografica="ISO/IEC 25012 (2008); Batini et al. (2009)",
        operacionalizacion="si",
        implementacion="Regla de divergencia operativa; la fórmula, al ser texto libre, no se compara por igualdad exacta.",
    ),
    dict(
        codigo="P06", nombre="Completitud de la hoja de vida", categoria="calidad",
        descripcion="Todo indicador debe diligenciar nombre, objetivo, fórmula, unidad de medida, línea base, meta, periodicidad, fuente y responsable.",
        fuente_bibliografica="ISO/IEC 25012 (2008); DNP (2009); Función Pública (2021)",
        operacionalizacion="si",
        implementacion="Regla de incompletitud de atributos sobre los nueve atributos exigidos.",
    ),
    dict(
        codigo="P07", nombre="Exactitud de la formulación (estructura del nombre)", categoria="calidad",
        descripcion="Un indicador válido se redacta como magnitud cuantificable acumulable, no como actividad puntual.",
        fuente_bibliografica="Wang y Strong (1996); ISO/IEC 25012 (2008); DNP (2009)",
        operacionalizacion="si",
        implementacion="Regla de problema metodológico (heurística léxica sobre el inicio del nombre).",
    ),
    dict(
        codigo="P08", nombre="Examen poblacional completo", categoria="auditoria",
        descripcion="La auditoría examina la totalidad de los indicadores de la vigencia, sin muestreo.",
        fuente_bibliografica="Vasarhelyi y Halper (1991); Appelbaum et al. (2017)",
        operacionalizacion="si",
        implementacion="ejecutar_auditoria compara todos los indicadores de la vigencia seleccionada.",
    ),
    dict(
        codigo="P09", nombre="Trazabilidad: regla, atributos y evidencia", categoria="auditoria",
        descripcion="Todo hallazgo debe informar la regla aplicada, los atributos comparados y la evidencia que lo sustenta.",
        fuente_bibliografica="Barredo Arrieta et al. (2020); Zhang et al. (2022)",
        operacionalizacion="si",
        implementacion="Campos obligatorios de Hallazgo (regla_aplicada, atributos_comparados, evidencia).",
    ),
    dict(
        codigo="P10", nombre="Revisión humana de cada hallazgo", categoria="auditoria",
        descripcion="El sistema señala; la decisión de confirmar o descartar es del auditor.",
        fuente_bibliografica="Kokina y Davenport (2017); Janssen et al. (2020)",
        operacionalizacion="si",
        implementacion="Estados pendiente, confirmado y descartado, con revisor y fecha de revisión.",
    ),
    dict(
        codigo="P11", nombre="Similitud semántica con umbral", categoria="pln",
        descripcion="Representación vectorial de oraciones y umbral de coseno para separar coincidencia relevante de parecido casual.",
        fuente_bibliografica="Reimers y Gurevych (2019)",
        operacionalizacion="si",
        implementacion="Modelo paraphrase-multilingual-mpnet-base-v2; umbrales 0.85 (duplicidad) y 0.95 (coincidencia textual).",
    ),
]

REGLAS = [
    dict(
        nombre="Similitud semántica sobre umbral de duplicidad",
        tipo_hallazgo="duplicidad",
        descripcion="Marca como duplicidad los pares cuya similitud de embeddings supera NLP_ENGINE.UMBRAL_DUPLICIDAD y no presentan coincidencia textual casi exacta ni diferencias de unidad o periodicidad.",
        parametro_codigo="P04",
    ),
    dict(
        nombre="Coincidencia textual casi exacta con variación marginal",
        tipo_hallazgo="clonacion",
        descripcion="Marca como clonación los pares con coincidencia textual >= UMBRAL_CLONACION_TEXTUAL en nombre, fórmula y meta y variación en dependencia, vigencia, meta o producto/actividad.",
        parametro_codigo="P04",
    ),
    dict(
        nombre="Equivalencia semántica con atributos técnicos divergentes",
        tipo_hallazgo="divergencia_operativa",
        descripcion="Marca como divergencia operativa los pares semánticamente equivalentes que difieren en unidad de medida o periodicidad (la fórmula, al ser texto libre, no se usa como disparador exacto).",
        parametro_codigo="P05",
    ),
    dict(
        nombre="Verificación de completitud de la hoja de vida",
        tipo_hallazgo="incompletitud_atributos",
        descripcion="Marca como incompletitud los indicadores con atributos obligatorios de la hoja de vida sin diligenciar.",
        parametro_codigo="P06",
    ),
    dict(
        nombre="Heurística léxica para nombres redactados como actividad",
        tipo_hallazgo="problema_metodologico",
        descripcion="Marca como problema metodológico los nombres que inician con un verbo o sustantivo de acción puntual en vez de describir una magnitud medible.",
        parametro_codigo="P07",
    ),
]


class Command(BaseCommand):
    help = "Siembra el catálogo de once parámetros y las cinco reglas de auditoría (criterio de cobertura)."

    def handle(self, *args, **options):
        parametros = {}
        for datos in PARAMETROS:
            parametro, creado = ParametroGobernanza.objects.update_or_create(
                codigo=datos["codigo"], defaults=datos
            )
            parametros[datos["codigo"]] = parametro
            self.stdout.write(("Creado " if creado else "Actualizado ") + str(parametro))

        for datos in REGLAS:
            datos = dict(datos)
            parametro = parametros[datos.pop("parametro_codigo")]
            regla, creado = ReglaAuditoria.objects.update_or_create(
                tipo_hallazgo=datos["tipo_hallazgo"],
                defaults={**datos, "parametro_gobernanza": parametro, "activa": True},
            )
            self.stdout.write(("Creada " if creado else "Actualizada ") + regla.nombre)

        self.stdout.write(self.style.SUCCESS("Catálogo de parámetros y reglas sembrado."))
