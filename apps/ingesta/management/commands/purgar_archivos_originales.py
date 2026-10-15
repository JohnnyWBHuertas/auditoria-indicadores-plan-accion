from django.core.management.base import BaseCommand

from apps.ingesta.models import CargaArchivo
from apps.ingesta.services import descartar_original


class Command(BaseCommand):
    help = (
        "Elimina del disco los archivos originales de las cargas ya procesadas (pueden contener datos personales). "
        "Los indicadores y el historial de cargas se conservan."
    )

    def handle(self, *args, **options):
        eliminados = 0
        for carga in CargaArchivo.objects.exclude(archivo=""):
            if not carga.nombre_archivo:
                carga.nombre_archivo = carga.archivo.name.rsplit("/", 1)[-1]
                carga.save(update_fields=["nombre_archivo"])
            descartar_original(carga)
            eliminados += 1
        self.stdout.write(self.style.SUCCESS(f"{eliminados} archivo(s) original(es) eliminado(s)."))
