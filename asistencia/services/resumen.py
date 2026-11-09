"""Resúmenes para las pantallas de inicio: el del docente y el panel del administrador (RF-20).

Solo juntan datos que ya existen (grupos, clases de hoy, pendientes de RF-10, cuentas y
periodos): no calculan nada nuevo de asistencia. El del administrador cuenta usuarios y
periodos, no abre los grupos de los docentes: el administrador solo gestiona usuarios.
"""

from dataclasses import dataclass, field

from django.utils import timezone

from ..models import Grupo, Inscripcion, Periodo, Sesion, Usuario
from .pendientes import sesiones_pendientes
from .periodos import de_periodo_cerrado
from .registro import cuentas_pendientes


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


@dataclass
class ResumenDelAdministrador:
    hoy: object                                   # fecha de hoy en Tijuana
    saludo: str
    pendientes: int = 0                           # cuentas que esperan aprobación (RF-19)
    docentes: int = 0                             # docentes activos y aprobados
    administradores: int = 0                      # administradores activos
    desactivados: int = 0                         # cuentas dadas de baja (is_active=False)
    periodo: object = None                        # el periodo activo, o None si no hay
    grupos_del_periodo: int = 0                   # cuántos grupos tiene el periodo activo
    periodos: int = 0                             # periodos registrados


def resumen_del_administrador(ahora=None):
    """Cifras del panel del administrador (RF-20). `ahora` solo sirve para fijar la hora en las pruebas."""
    ahora = timezone.localtime(ahora)
    cuentas = Usuario.objects.filter(is_active=True, aprobado=True)
    periodo = Periodo.objects.filter(activo=True).first()
    return ResumenDelAdministrador(
        hoy=ahora.date(),
        saludo=saludo_de(ahora.hour),
        pendientes=cuentas_pendientes().count(),
        docentes=cuentas.filter(rol=Usuario.Rol.DOCENTE).count(),
        administradores=cuentas.filter(rol=Usuario.Rol.ADMINISTRADOR).count(),
        desactivados=Usuario.objects.filter(is_active=False).count(),
        periodo=periodo,
        grupos_del_periodo=Grupo.objects.filter(periodo=periodo.clave).count() if periodo else 0,
        periodos=Periodo.objects.count(),
    )
