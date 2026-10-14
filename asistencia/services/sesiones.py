"""Consultas y operaciones sobre las sesiones de un grupo (RF-06 y RF-07)."""

from ..models import Sesion


class SesionNoModificable(Exception):
    """La sesión ya no está programada, así que no se edita ni se cancela."""


def asegurar_programada(sesion):
    """RF-07: solo una sesión programada se puede editar o cancelar."""
    if sesion.estado != Sesion.Estado.PROGRAMADA:
        raise SesionNoModificable(
            'Solo se puede editar o cancelar una sesión programada; '
            f'esta ya está {sesion.get_estado_display().lower()}.'
        )


def cancelar_sesion(sesion):
    """Pasa una sesión programada a cancelada. No se borra: queda en el
    calendario y sigue ocupando su fecha y hora de inicio."""
    asegurar_programada(sesion)
    sesion.estado = Sesion.Estado.CANCELADA
    sesion.save(update_fields=['estado'])


def calendario_de_sesiones(grupo, desde=None, hasta=None):
    """Sesiones del grupo en orden cronológico, opcionalmente entre dos
    fechas (ambas incluidas)."""
    sesiones = Sesion.objects.filter(grupo=grupo)
    if desde is not None:
        sesiones = sesiones.filter(fecha__gte=desde)
    if hasta is not None:
        sesiones = sesiones.filter(fecha__lte=hasta)
    return sesiones.order_by('fecha', 'hora_inicio')
