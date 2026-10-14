"""Sesiones sin pase de lista o con el pase incompleto (RF-10)."""

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from ..models import Asistencia, Inscripcion, Sesion


def sesiones_pendientes(docente, grupo=None, ahora=None):
    """Sesiones pasadas del docente que necesitan atención, de la más antigua
    a la más reciente. Es una sola consulta, sin importar cuántas sean.

    Una sesión es pendiente si ya pasó y cumple una de estas condiciones:
    - está programada y no tiene ningún registro;
    - está realizada y algún inscrito actual, con alta igual o anterior a la
      fecha de la sesión, no tiene registro en ella (pase incompleto).

    «Ya pasó» se mide en la zona horaria del proyecto: la fecha es anterior a
    hoy, o es hoy y la hora de fin ya transcurrió. Las canceladas no cuentan.
    `ahora` (un datetime con zona) solo sirve para fijar la hora en las pruebas.
    """
    ahora = timezone.localtime(ahora)
    hoy, hora = ahora.date(), ahora.time()
    ya_paso = Q(fecha__lt=hoy) | Q(fecha=hoy, hora_fin__lte=hora)

    registros = Asistencia.objects.filter(sesion_id=OuterRef('pk'))
    inscrito_sin_registro = Inscripcion.objects.filter(
        grupo_id=OuterRef('grupo_id'), fecha_alta__lte=OuterRef('fecha'),
    ).filter(
        ~Exists(Asistencia.objects.filter(
            sesion_id=OuterRef(OuterRef('pk')), alumno_id=OuterRef('alumno_id')))
    )

    sesiones = (
        Sesion.objects.filter(grupo__docente=docente)
        .exclude(estado=Sesion.Estado.CANCELADA)
        .filter(ya_paso)
        .annotate(
            tiene_registros=Exists(registros),
            tiene_faltantes=Exists(inscrito_sin_registro),
        )
        .filter(
            Q(estado=Sesion.Estado.PROGRAMADA, tiene_registros=False)
            | Q(estado=Sesion.Estado.REALIZADA, tiene_faltantes=True)
        )
        .select_related('grupo')
        .order_by('fecha', 'hora_inicio', 'grupo__clave')
    )
    if grupo is not None:
        sesiones = sesiones.filter(grupo=grupo)
    return list(sesiones)
