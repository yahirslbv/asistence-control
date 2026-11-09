"""Registro de docentes y aprobación de cuentas (RF-19 y RF-20).

Quien no tiene cuenta puede registrarse desde la pantalla de acceso, con tres condiciones:

- Su correo debe ser de un dominio permitido (`REGISTRO_DOMINIOS`, por defecto
  `uabc.edu.mx`). El dominio es exacto: `sub.uabc.edu.mx` o `uabc.edu.mx.otro.com` no
  valen.
- Recibe siempre el rol docente. El formulario no pregunta el rol, y este módulo no
  acepta otro: un administrador solo lo da de alta otro administrador (RF-16).
- La cuenta nace sin aprobar (`aprobado=False`) y no puede iniciar sesión hasta que un
  administrador la apruebe. Rechazarla la desactiva (`is_active=False`, regla 9.5: los
  usuarios no se borran).

No se confirma el correo por mensaje: la aplicación no envía correos. La aprobación del
administrador es el control que verifica que la persona sea quien dice ser.
"""

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.db import IntegrityError, transaction

from ..models import Usuario


class ErrorDeRegistro(Exception):
    """Base de los errores de este módulo; el mensaje se puede mostrar tal cual."""


class CorreoNoPermitido(ErrorDeRegistro):
    """El correo no es de un dominio que pueda registrarse solo."""


class CorreoYaRegistrado(ErrorDeRegistro):
    """Ya existe una cuenta con ese correo."""


class CuentaNoPendiente(ErrorDeRegistro):
    """La cuenta ya no espera aprobación (otro administrador ya la atendió)."""


def dominios_permitidos():
    """Los dominios de correo que pueden registrarse (en minúsculas)."""
    return tuple(settings.REGISTRO_DOMINIOS)


def registro_abierto():
    """Sin ningún dominio configurado el registro queda cerrado."""
    return bool(dominios_permitidos())


def normalizar_correo(correo):
    return (correo or '').strip().lower()


def dominio_permitido(correo):
    """True si el correo tiene la forma `algo@dominio` y el dominio es exactamente uno de los permitidos."""
    correo = normalizar_correo(correo)
    if correo.count('@') != 1:
        return False
    usuario, dominio = correo.split('@')
    return bool(usuario) and dominio in dominios_permitidos()


def correo_en_uso(correo):
    """True si ya hay una cuenta con ese correo o con ese nombre de usuario (que es el correo)."""
    correo = normalizar_correo(correo)
    return Usuario.objects.filter(email__iexact=correo).exists() or \
        Usuario.objects.filter(username__iexact=correo).exists()


def registrar_docente(*, nombre, apellido, correo, contrasena):
    """Crea una cuenta de docente pendiente de aprobación y la devuelve.

    El rol y la aprobación no se piden: siempre docente y sin aprobar. El nombre de
    usuario es el correo, que ya es único. La contraseña se guarda cifrada.
    """
    correo = normalizar_correo(correo)
    if not dominio_permitido(correo):
        raise CorreoNoPermitido(
            'Solo se admiten correos de ' + ' o '.join(f'@{d}' for d in dominios_permitidos()) + '.')
    try:
        with transaction.atomic():
            if correo_en_uso(correo):
                raise CorreoYaRegistrado('Ya existe una cuenta con ese correo.')
            return Usuario.objects.create_user(
                username=correo, email=correo, password=contrasena,
                first_name=nombre.strip(), last_name=apellido.strip(),
                rol=Usuario.Rol.DOCENTE, aprobado=False,
            )
    except IntegrityError:
        # Dos registros del mismo correo al mismo tiempo: gana uno y el otro llega aquí.
        raise CorreoYaRegistrado('Ya existe una cuenta con ese correo.')


def cuenta_pendiente(correo, contrasena):
    """True si el correo y la contraseña son de una cuenta activa que aún espera aprobación.

    Solo sirve para decirle a esa persona por qué no puede entrar. Exige la contraseña
    correcta: quien no la sabe no puede averiguar si el correo está registrado.
    """
    correo = normalizar_correo(correo)
    if not correo or not contrasena:
        return False
    try:
        usuario = Usuario.objects.get(email__iexact=correo)
    except Usuario.DoesNotExist:
        Usuario().set_password(contrasena)   # mismo costo de tiempo que con una cuenta real
        return False
    return usuario.is_active and not usuario.aprobado and usuario.check_password(contrasena)


def cuentas_pendientes():
    """Las cuentas que esperan aprobación, la más antigua primero."""
    return Usuario.objects.filter(aprobado=False, is_active=True).order_by('date_joined', 'pk')


def _cuenta_pendiente_bloqueada(usuario_id):
    try:
        return Usuario.objects.select_for_update().get(
            pk=usuario_id, aprobado=False, is_active=True)
    except Usuario.DoesNotExist:
        raise CuentaNoPendiente('Esa cuenta ya no está esperando aprobación.')


def _anotar(administrador, usuario, mensaje):
    """Deja la acción en el registro de acciones del admin de Django: quién la hizo y cuándo."""
    LogEntry.objects.log_actions(
        user_id=administrador.pk, queryset=[usuario], action_flag=CHANGE,
        change_message=mensaje)


def aprobar_cuenta(usuario_id, administrador):
    """Aprueba una cuenta pendiente: desde ahora puede iniciar sesión."""
    with transaction.atomic():
        usuario = _cuenta_pendiente_bloqueada(usuario_id)
        usuario.aprobado = True
        usuario.save(update_fields=['aprobado'])
        _anotar(administrador, usuario, 'Cuenta aprobada.')
    return usuario


def rechazar_cuenta(usuario_id, administrador):
    """Rechaza una cuenta pendiente: queda desactivada (no se borra) y no puede entrar.

    Si fue un error, el administrador la reactiva con «Activo» en el admin: vuelve a
    aparecer en el panel como pendiente y se puede aprobar.
    """
    with transaction.atomic():
        usuario = _cuenta_pendiente_bloqueada(usuario_id)
        usuario.is_active = False
        usuario.save(update_fields=['is_active'])
        _anotar(administrador, usuario, 'Cuenta rechazada: se desactivó.')
    return usuario
