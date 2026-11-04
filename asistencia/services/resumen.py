"""Resumen del día para el inicio del docente.

Solo junta datos que ya existen (grupos, clases de hoy y pendientes de RF-10):
no calcula nada nuevo de asistencia.
"""

from dataclasses import dataclass, field

from django.utils import timezone

from ..models import Grupo, Inscripcion, Sesion
from .pendientes import sesiones_pendientes
from .periodos import de_periodo_cerrado


@dataclass
class ResumenDelDocente:
    hoy: object                                   # fecha de hoy en Tijuana
    saludo: str                                   # «Buenos días», «Buenas tardes» o «Buenas noches»
    sesiones_de_hoy: list = field(default_factory=list)
    grupos: int = 0                               # grupos de periodos que no están congelados
    alumnos: int = 0                              # alumnos distintos en esos grupos
    pendientes: int = 0                           # sesiones sin lista o con la lista incompleta (RF-10)


def saludo_de(hora):
    if hora < 12:
        return 'Buenos días'
    if hora < 19:
        return 'Buenas tardes'
    return 'Buenas noches'


def resumen_del_docente(docente, ahora=None):
    """Datos del inicio: las clases de hoy (sin las canceladas ni las de un
    periodo inactivo), cuántos grupos y alumnos tiene y cuántas sesiones esperan
    su lista. `ahora` (un datetime con zona) solo sirve para fijar la hora en las pruebas."""
    ahora = timezone.localtime(ahora)
    hoy = ahora.date()

    pendientes = sesiones_pendientes(docente, ahora=ahora, solo_atendibles=True)
    ids_pendientes = {sesion.pk for sesion in pendientes}

    de_hoy = list(
        Sesion.objects.filter(grupo__docente=docente, fecha=hoy)
        .exclude(estado=Sesion.Estado.CANCELADA)
        .exclude(de_periodo_cerrado('grupo__periodo'))
        .select_related('grupo')
        .order_by('hora_inicio', 'grupo__clave')
    )
    for sesion in de_hoy:
        sesion.hecha = sesion.estado == Sesion.Estado.REALIZADA
        sesion.pendiente = sesion.pk in ids_pendientes

    grupos = Grupo.objects.filter(docente=docente).exclude(de_periodo_cerrado('periodo'))
    alumnos = (
        Inscripcion.objects.filter(grupo__in=grupos)
        .values('alumno_id').distinct().count()
    )
    return ResumenDelDocente(
        hoy=hoy, saludo=saludo_de(ahora.hour), sesiones_de_hoy=de_hoy,
        grupos=grupos.count(), alumnos=alumnos, pendientes=len(pendientes),
    )
