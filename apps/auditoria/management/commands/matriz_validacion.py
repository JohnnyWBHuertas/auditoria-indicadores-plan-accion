from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.validacion import ejecutar_matriz, exportar_matriz_xlsx
from apps.nlp_engine.embeddings import ModeloNoDisponible


class Command(BaseCommand):
    help = (
        "Ejecuta los casos de prueba de la matriz de validación funcional sobre el conjunto de control "
        "(nueve indicadores) y, opcionalmente, exporta la matriz a Excel (Anexo D). Corre sobre una base de datos temporal: no toca los datos del proyecto."
    )

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Ruta del .xlsx donde exportar la matriz.")
        parser.add_argument(
            "--sin-modelo", action="store_true",
            help="Simula los pares candidatos en lugar de cargar el modelo de embeddings.",
        )

    def handle(self, *args, **options):
        usar_modelo = not options["sin_modelo"]
        try:
            filas = ejecutar_matriz(usar_modelo=usar_modelo, aislada=True)
        except (ImportError, OSError, ModeloNoDisponible) as exc:
            raise CommandError(f"No fue posible cargar el modelo de embeddings: {exc}")

        for f in filas:
            marca = self.style.SUCCESS("CUMPLE   ") if f["estado"] == "Cumple" else self.style.ERROR("NO CUMPLE")
            self.stdout.write(f"{f['caso']} {marca} {f['modulo']}: {f['obtenido']}")

        cumplen = sum(1 for f in filas if f["estado"] == "Cumple")
        self.stdout.write(f"\n{cumplen} de {len(filas)} casos cumplen.")
        if options["salida"]:
            exportar_matriz_xlsx(filas, options["salida"], usar_modelo)
            self.stdout.write(f"Matriz exportada a {options['salida']}")
        if cumplen != len(filas):
            raise CommandError("Hay casos que no cumplen.")

