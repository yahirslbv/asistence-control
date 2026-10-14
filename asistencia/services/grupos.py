"""Lógica de negocio de los grupos (RF-03)."""

from ..models import Asistencia, BitacoraCambio


def impacto_de_eliminar(grupo):
    """Cuenta lo que se borra en cascada al eliminar un grupo.

    Eliminar un grupo borra sus sesiones, inscripciones, registros de
    asistencia y la bitácora de esos registros (regla 5 del CLAUDE.md). La
    pantalla de confirmación muestra estas cifras antes de borrar.
    """
    return {
        'sesiones': grupo.sesiones.count(),
        'inscripciones': grupo.inscripciones.count(),
        'asistencias': Asistencia.objects.filter(sesion__grupo=grupo).count(),
        'cambios': BitacoraCambio.objects.filter(asistencia__sesion__grupo=grupo).count(),
    }
