from django.core.management.base import BaseCommand

from apps.ingesta.models import PlantillaMapeoColumnas

# Plantilla para el archivo datos_ejemplo/conjunto_control_2026.csv:
# columna del archivo -> campo de la hoja de vida del indicador.
MAPEO_CONJUNTO_CONTROL = {
    "Dependencia": "dependencia",
    "Programa": "programa",
    "Bien o servicio": "bien_servicio",
    "Indicador": "nombre",
    "Objetivo": "objetivo",
    "Fórmula": "formula",
    "Unidad de medida": "unidad_medida",
    "Línea base": "linea_base",
    "Meta": "meta",
    "Periodicidad": "periodicidad",
    "Fuente": "fuente",
    "Responsable": "responsable",
    "Producto, actividad o proyecto": "producto_actividad_proyecto",
    "Código PAA": "codigo_paa",
}


class Command(BaseCommand):
    help = "Crea la plantilla de mapeo de columnas del conjunto de control (datos_ejemplo/conjunto_control_2026.csv)."

    def handle(self, *args, **options):
        plantilla, creada = PlantillaMapeoColumnas.objects.update_or_create(
            nombre="Conjunto de control 2026",
            vigencia="2026",
            defaults={"mapeo_columnas": MAPEO_CONJUNTO_CONTROL, "activa": True},
        )
        self.stdout.write(self.style.SUCCESS(("Creada " if creada else "Actualizada ") + str(plantilla)))
