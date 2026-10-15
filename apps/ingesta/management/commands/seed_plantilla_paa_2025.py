from django.core.management.base import BaseCommand

from apps.ingesta.models import PlantillaMapeoColumnas

# Plantilla para "Asociacion de indicadores con paa - 2025.xlsx" (exportacion del
# sistema institucional: una fila por linea del PAA, con las columnas de la hoja de
# vida del indicador cuando la linea tiene indicador asociado).
#
# Decisiones de mapeo:
#  - dependencia <- grupo_nombre: es la unidad que registra su propio Plan de Accion.
#  - La vigencia no se mapea: el archivo trae "Ano 2025" y se usa la vigencia de la carga.
#  - responsable no existe en el archivo; queda sin mapear (el atributo se reportara
#    como no diligenciado en todos los indicadores).
#  - Las filas sin indicador (lineas del PAA sin indicador asociado) se omiten.
MAPEO_PAA_2025 = {
    "grupo_nombre": "dependencia",
    "programa": "programa",
    "bien_servicio": "bien_servicio",
    "indicador": "nombre",
    "objetivo": "objetivo",
    "formula": "formula",
    "unidad_medida": "unidad_medida",
    "linea_base": "linea_base",
    "meta_indicador": "meta",
    "periodo_medicion": "periodicidad",
    "fuente_informacion": "fuente",
    "producto_cls": "producto_actividad_proyecto",
    "codigo_paa": "codigo_paa",
}


class Command(BaseCommand):
    help = "Crea la plantilla de mapeo del reporte 'Asociación de indicadores con PAA - 2025'."

    def handle(self, *args, **options):
        plantilla, creada = PlantillaMapeoColumnas.objects.update_or_create(
            nombre="Asociación de indicadores con PAA 2025",
            vigencia="2025",
            defaults={"mapeo_columnas": MAPEO_PAA_2025, "activa": True},
        )
        self.stdout.write(self.style.SUCCESS(("Creada " if creada else "Actualizada ") + str(plantilla)))
