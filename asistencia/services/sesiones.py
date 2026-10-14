"""Consultas y operaciones sobre las sesiones de un grupo (RF-06 y RF-07)."""

from ..models import Sesion


def calendario_de_sesiones(grupo, desde=None, hasta=None):
    """Sesiones del grupo en orden cronológico, opcionalmente entre dos
    fechas (ambas incluidas)."""
    sesiones = Sesion.objects.filter(grupo=grupo)
    if desde is not None:
        sesiones = sesiones.filter(fecha__gte=desde)
    if hasta is not None:
        sesiones = sesiones.filter(fecha__lte=hasta)
    return sesiones.order_by('fecha', 'hora_inicio')
