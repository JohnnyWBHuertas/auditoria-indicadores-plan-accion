from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.comparacion import comparar
from apps.gobernanza.models import EjecucionAuditoria


class Command(BaseCommand):
    help = (
        "Compara dos ejecuciones de auditoría: configuración registrada (modelo, reglas, umbrales, huella de "
        "los datos) y señalamientos obtenidos. Indica si son equivalentes y qué cambió si no lo son."
    )

    def add_arguments(self, parser):
        parser.add_argument("ejecucion_a", type=int)
        parser.add_argument("ejecucion_b", type=int)

    def handle(self, *args, **options):
        try:
            a = EjecucionAuditoria.objects.get(pk=options["ejecucion_a"])
            b = EjecucionAuditoria.objects.get(pk=options["ejecucion_b"])
        except EjecucionAuditoria.DoesNotExist:
            raise CommandError("Alguna de las ejecuciones no existe.")
        r = comparar(a, b)
        self.stdout.write(f"Ejecución {a.pk} ({a.iniciada_en:%Y-%m-%d %H:%M}) frente a ejecución {b.pk} ({b.iniciada_en:%Y-%m-%d %H:%M})")
        self.stdout.write(f"Señalamientos: {r['hallazgos_a']} frente a {r['hallazgos_b']}; solo en A: {r['solo_en_a']}; solo en B: {r['solo_en_b']}")
        if r["diferencias_configuracion"]:
            self.stdout.write("Configuración distinta:")
            for k, (va, vb) in r["diferencias_configuracion"].items():
                self.stdout.write(f"  {k}: {va} -> {vb}")
        else:
            self.stdout.write("Configuración registrada: idéntica (modelo, reglas, umbrales y datos de entrada).")
        if r["equivalentes"]:
            self.stdout.write(self.style.SUCCESS("EQUIVALENTES: misma configuración y mismos señalamientos."))
        elif r["configuracion_igual"]:
            raise CommandError("Misma configuración pero resultados distintos: la auditoría no es repetible.")
        else:
            self.stdout.write(self.style.WARNING("Configuración distinta: las diferencias de resultado son esperables."))
