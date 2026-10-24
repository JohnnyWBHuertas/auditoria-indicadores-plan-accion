from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

# Tres roles (RBAC), cada uno con permisos de modelo de Django:
#  - Administrador: todo lo del Auditor y, ademas, configura plantillas de mapeo
#    y el catalogo de parametros y reglas desde el sitio de administracion.
#  - Auditor: carga el reporte, ejecuta el analisis, revisa y exporta hallazgos.
#  - Consulta: solo lectura (tablero, hallazgos, comparacion y exportacion).
APPS_DEL_DOMINIO = ["gobernanza", "ingesta", "nlp_engine", "auditoria"]

PERMISOS_AUDITOR = [
    ("ingesta", "add_cargaarchivo"), ("ingesta", "view_cargaarchivo"),
    ("ingesta", "view_plantillamapeocolumnas"), ("ingesta", "view_indicador"),
    ("gobernanza", "add_ejecucionauditoria"), ("gobernanza", "view_ejecucionauditoria"),
    ("gobernanza", "view_parametrogobernanza"), ("gobernanza", "view_dependencia"),
    ("auditoria", "view_hallazgo"), ("auditoria", "change_hallazgo"),
    ("auditoria", "view_reglaauditoria"),
    ("auditoria", "add_correspondenciamanual"), ("auditoria", "change_correspondenciamanual"),
    ("auditoria", "view_correspondenciamanual"),
]

PERMISOS_CONSULTA = [
    ("ingesta", "view_cargaarchivo"), ("ingesta", "view_indicador"),
    ("gobernanza", "view_ejecucionauditoria"), ("gobernanza", "view_parametrogobernanza"), ("gobernanza", "view_dependencia"),
    ("auditoria", "view_hallazgo"), ("auditoria", "view_reglaauditoria"), ("auditoria", "view_correspondenciamanual"),
]


class Command(BaseCommand):
    help = (
        "Crea los grupos Administrador, Auditor y Consulta. Con --usuarios y --password crea además "
        "un usuario de demostración para cada rol (administrador, auditor y consulta)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--usuarios", action="store_true", help="Crear usuarios de demostración.")
        parser.add_argument("--password", help="Contraseña de los usuarios de demostración (obligatoria con --usuarios).")

    def handle(self, *args, **options):
        auditor, _ = Group.objects.get_or_create(name="Auditor")
        administrador, _ = Group.objects.get_or_create(name="Administrador")
        consulta, _ = Group.objects.get_or_create(name="Consulta")

        permisos_auditor = [
            Permission.objects.get(content_type__app_label=app, codename=codigo)
            for app, codigo in PERMISOS_AUDITOR
        ]
        auditor.permissions.set(permisos_auditor)
        consulta.permissions.set([
            Permission.objects.get(content_type__app_label=app, codename=codigo) for app, codigo in PERMISOS_CONSULTA
        ])
        administrador.permissions.set(Permission.objects.filter(content_type__app_label__in=APPS_DEL_DOMINIO))
        self.stdout.write(self.style.SUCCESS("Grupos Administrador, Auditor y Consulta listos."))

        if options["usuarios"]:
            if not options["password"]:
                raise CommandError("Indique --password para crear los usuarios de demostración.")
            Usuario = get_user_model()
            for nombre, grupo, es_staff in (("auditor", auditor, False), ("administrador", administrador, True), ("consulta", consulta, False)):
                usuario, creado = Usuario.objects.get_or_create(username=nombre, defaults={"is_staff": es_staff})
                usuario.is_staff = es_staff
                usuario.set_password(options["password"])
                usuario.save()
                usuario.groups.set([grupo])
                self.stdout.write(("Creado " if creado else "Actualizado ") + f"usuario {nombre} ({grupo.name}).")
