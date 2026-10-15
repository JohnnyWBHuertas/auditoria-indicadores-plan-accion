from django.core.management.base import BaseCommand

from apps.gobernanza.models import Dependencia
from apps.ingesta.datos_control import INDICADORES_DEMO, VIGENCIA_DEMO
from apps.ingesta.models import Indicador


class Command(BaseCommand):
    help = "Carga indicadores sintéticos de demostración (no son el dataset real del Ministerio)."

    def handle(self, *args, **options):
        creados = 0
        for original in INDICADORES_DEMO:
            datos = dict(original)
            dependencia, _ = Dependencia.objects.get_or_create(nombre=datos.pop("dependencia_nombre"))
            _, fue_creado = Indicador.objects.get_or_create(
                nombre=datos["nombre"],
                dependencia=dependencia,
                producto_actividad_proyecto=datos["producto_actividad_proyecto"],
                vigencia=VIGENCIA_DEMO,
                defaults={**datos, "vigencia": VIGENCIA_DEMO},
            )
            creados += int(fue_creado)

        self.stdout.write(self.style.SUCCESS(f"Indicadores sintéticos listos ({creados} nuevos, vigencia {VIGENCIA_DEMO})."))
