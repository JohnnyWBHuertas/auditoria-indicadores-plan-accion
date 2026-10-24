"""Control de acceso basado en roles (RBAC) del prototipo.

Los roles son grupos de Django (Administrador, Auditor y Consulta) y cada
funcionalidad exige un permiso de modelo concreto; ver ``seed_roles``.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def requiere_permiso(*permisos):
    """Exige sesion iniciada y todos los permisos indicados (403 si faltan)."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.has_perms(permisos):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return login_required(envoltura)

    return decorador
