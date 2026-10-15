"""Reglas de los usuarios y sus roles (RF-16).

El administrador da de alta usuarios desde el admin de Django y les asigna un
rol. El rol manda siempre sobre el acceso al admin:
- administrador: `is_staff` y los permisos de ver, agregar y modificar usuario
  (solo eso: el administrador solo gestiona usuarios);
- docente: sin `is_staff` y sin esos permisos.

Los usuarios no se borran (regla 9.5 del CLAUDE.md): se desactivan.
"""

from django.contrib.auth.models import Permission
from django.db import transaction

from ..models import Usuario

CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR = ('add_usuario', 'change_usuario', 'view_usuario')


class ErrorDeUsuario(Exception):
    """El cambio no se permite; el mensaje se puede mostrar tal cual."""


def aplicar_rol(usuario):
    """Ajusta `is_staff` según el rol (no guarda).

    Un superusuario conserva `is_staff`: si no, un `createsuperuser` (que crea el
    rol docente) quedaría fuera del admin al guardarlo.
    """
    if usuario.is_superuser:
        usuario.is_staff = True
    else:
        usuario.is_staff = usuario.rol == Usuario.Rol.ADMINISTRADOR


def _permisos_de_usuario():
    return Permission.objects.filter(
        content_type__app_label='asistencia',
        content_type__model='usuario',
        codename__in=CODIGOS_DE_PERMISO_DEL_ADMINISTRADOR,
    )


def sincronizar_permisos(usuario):
    """Da o quita los permisos de gestionar usuarios según el rol. El usuario
    ya debe estar guardado. El administrador queda con esos tres y ninguno más."""
    if usuario.rol == Usuario.Rol.ADMINISTRADOR:
        usuario.user_permissions.set(_permisos_de_usuario())
    else:
        usuario.user_permissions.remove(*_permisos_de_usuario())


def validar_cambio(usuario, rol_nuevo, activo_nuevo, quien):
    """Lanza ErrorDeUsuario si el cambio no se permite:

    - nadie se desactiva a sí mismo;
    - no se desactiva ni se le quita el rol al último administrador activo, para
      que el sistema nunca se quede sin quien gestione usuarios.

    Debe llamarse dentro de una transacción (el admin ya lo hace): bloquea las
    filas de los administradores activos, así dos cambios simultáneos se
    atienden de uno en uno y el segundo ve el resultado del primero.
    """
    if usuario.pk is None:
        return   # un alta no puede dejar al sistema sin administradores
    if quien is not None and quien.pk == usuario.pk and not activo_nuevo:
        raise ErrorDeUsuario('No puedes desactivarte a ti mismo.')

    with transaction.atomic():
        activos = list(
            Usuario.objects.select_for_update()
            .filter(rol=Usuario.Rol.ADMINISTRADOR, is_active=True))
    era_administrador = any(u.pk == usuario.pk for u in activos)
    sigue_siendo = rol_nuevo == Usuario.Rol.ADMINISTRADOR and activo_nuevo
    quedan = [u for u in activos if u.pk != usuario.pk]
    if era_administrador and not sigue_siendo and not quedan:
        raise ErrorDeUsuario(
            'No se puede desactivar ni quitar el rol al último administrador '
            'activo: el sistema se quedaría sin quien gestione usuarios.')
