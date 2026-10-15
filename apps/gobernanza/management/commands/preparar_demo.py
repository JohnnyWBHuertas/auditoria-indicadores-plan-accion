from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.ingesta.models import Indicador

# Contrasena solo para la demostracion local con los usuarios `auditor` y `administrador`.
CLAVE_DEMO = "demo"


class Command(BaseCommand):
    help = (
        "Deja el prototipo listo para demostrarlo con el conjunto de control sintético: aplica las migraciones, "
        "siembra el catálogo de parámetros y reglas, crea los grupos y los usuarios de demostración, crea la plantilla "
        "de mapeo y carga los nueve indicadores de control (vigencia 2026). Con --auditar ejecuta además la auditoría. "
        "Es repetible: puede ejecutarse varias veces sin duplicar datos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--password", default=CLAVE_DEMO, help=f"Contraseña de los usuarios de demostración (por defecto «{CLAVE_DEMO}»).")
        parser.add_argument("--auditar", action="store_true", help="Ejecuta la auditoría sobre la vigencia 2026 (descarga el modelo la primera vez).")

    def handle(self, *args, **options):
        from apps.auditoria.validacion import VIGENCIA, cargar_conjunto_control

        def paso(texto):
            self.stdout.write(self.style.MIGRATE_HEADING(texto))

        paso("1/5 Migraciones")
        call_command("migrate", verbosity=0, interactive=False)

        paso("2/5 Catálogo de parámetros y reglas de auditoría")
        call_command("seed_catalogo_gobernanza", stdout=self.stdout)

        paso("3/5 Grupos y usuarios de demostración")
        call_command("seed_roles", usuarios=True, password=options["password"], stdout=self.stdout)

        paso("4/5 Plantilla de mapeo y conjunto de control")
        if Indicador.objects.filter(vigencia=VIGENCIA).exists():
            call_command("seed_plantilla_demo", stdout=self.stdout)
            self.stdout.write("El conjunto de control ya estaba cargado.")
        else:
            carga = cargar_conjunto_control()
            self.stdout.write(f"Carga {carga.get_estado_display().lower()}: {carga.filas_cargadas} indicadores normalizados (vigencia {VIGENCIA}).")

        if options["auditar"]:
            paso("5/5 Auditoría de la vigencia " + VIGENCIA)
            from apps.auditoria.reglas import ejecutar_auditoria
            from apps.nlp_engine.embeddings import ModeloNoDisponible

            try:
                ejecucion = ejecutar_auditoria(VIGENCIA)
            except ModeloNoDisponible as exc:
                raise CommandError(str(exc))
            self.stdout.write(f"Auditoría lista: {ejecucion.hallazgos.count()} hallazgos.")
        else:
            paso("5/5 Auditoría omitida (use --auditar para ejecutarla ahora)")

        self.stdout.write(self.style.SUCCESS(
            "\nListo. Inicie el servidor con «python manage.py runserver» e ingrese en http://localhost:8000/ "
            f"con el usuario «auditor» o «administrador» (contraseña «{options['password']}»)."
        ))
