"""Pase de lista y corrección de asistencia (RF-08, RF-09 y RF-11).

Un pase de lista se guarda con un solo envío, dentro de una transacción, y deja
la sesión en `realizada` en ese mismo momento. Una sesión realizada solo admite
correcciones. Una sesión cancelada no admite registros.

Se bloquea la fila de la sesión mientras se guarda, así que dos envíos al mismo
tiempo se atienden de uno en uno: el segundo ya encuentra la sesión realizada y
no duplica nada. La restricción única `(sesion, alumno)` sigue siendo la defensa
final (regla 9.1 del CLAUDE.md).

Las correcciones no escriben en la bitácora: lo hace el disparador de la base de
datos, que toma el autor de `registrado_por`. Por eso todo UPDATE de un estado
asigna `registrado_por` (regla 9.3).
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ..models import Alumno, Asistencia, BitacoraCambio, Sesion

ESTADOS_VALIDOS = frozenset(Asistencia.Estado.values)


class ErrorDePaseDeLista(Exception):
    """Base de los errores de este módulo; el mensaje se puede mostrar tal cual."""


class SesionNoAdmiteRegistros(ErrorDePaseDeLista):
    """La sesión está cancelada."""


class SesionFutura(ErrorDePaseDeLista):
    """La sesión es de una fecha posterior a hoy: aún no se puede tomar lista."""


class ConflictoDeSesion(ErrorDePaseDeLista):
    """La sesión no está en el estado que el formulario suponía, por ejemplo
    porque otro envío ya guardó el pase de lista. No se guardó nada."""


class DatosInvalidos(ErrorDePaseDeLista):
    """El envío trae un estado inexistente o no trae ningún alumno válido."""


class JustificanteImpideCambio(ErrorDePaseDeLista):
    """El registro tiene un justificante, que solo admite el estado justificado."""


@dataclass
class FilaDeLista:
    alumno: Alumno
    registro: Asistencia | None   # None: todavía no tiene registro en la sesión
    estado: str | None            # el que se preselecciona en el formulario


@dataclass
class ResultadoPase:
    registrados: int
    sin_enviar: int   # alumnos de la lista que el envío no traía; quedan sin registrar


@dataclass
class ResultadoCorreccion:
    cambiados: int    # registros cuyo estado cambió
    nuevos: int       # alumnos que no tenían registro y ahora sí


def lista_de_la_sesion(sesion):
    """Alumnos que se muestran en el pase de lista de la sesión, por nombre.

    - Sesión programada (primera captura): los inscritos actuales del grupo,
      todos en «presente».
    - Sesión realizada (corrección): sus registros existentes, aunque el alumno
      ya se haya dado de baja, más los inscritos actuales sin registro cuya
      alta sea igual o anterior a la fecha de la sesión, sin estado
      preseleccionado.
    """
    if sesion.estado == Sesion.Estado.REALIZADA:
        return _lista_de_correccion(sesion)
    return _lista_de_primera_captura(sesion)


def _lista_de_primera_captura(sesion):
    alumnos = (
        Alumno.objects.filter(inscripciones__grupo_id=sesion.grupo_id)
        .order_by('nombre', 'matricula')
    )
    return [FilaDeLista(a, None, Asistencia.Estado.PRESENTE) for a in alumnos]


def _lista_de_correccion(sesion):
    registros = {r.alumno_id: r for r in Asistencia.objects.filter(sesion=sesion)}
    alumnos = (
        Alumno.objects.filter(
            Q(pk__in=list(registros))
            | Q(inscripciones__grupo_id=sesion.grupo_id,
                inscripciones__fecha_alta__lte=sesion.fecha)
        )
        .distinct()
        .order_by('nombre', 'matricula')
    )
    filas = []
    for alumno in alumnos:
        registro = registros.get(alumno.pk)
        filas.append(FilaDeLista(alumno, registro, registro.estado if registro else None))
    return filas


def historial_de_cambios(sesion):
    """Correcciones de la sesión, la más reciente primero. Solo lectura."""
    return (
        BitacoraCambio.objects.filter(asistencia__sesion=sesion)
        .select_related('asistencia__alumno', 'usuario')
        .order_by('-fecha_cambio', '-id_bitacora')
    )


def registrar_pase_de_lista(sesion_id, enviados, usuario):
    """Guarda el pase de lista de una sesión programada (RF-08 y RF-09).

    `enviados` es {alumno_id: estado} tal como llegó del formulario. Los alumnos
    que no están en la lista de la sesión se ignoran; un estado que no sea uno
    de los cuatro rechaza todo el envío. Los alumnos de la lista que el envío no
    trae quedan sin registrar (los marca la alerta de RF-10).
    """
    try:
        with transaction.atomic():
            sesion = _bloquear(sesion_id)
            _asegurar_admite_registros(sesion)
            if sesion.estado != Sesion.Estado.PROGRAMADA:
                raise ConflictoDeSesion(
                    'Esta sesión ya tenía el pase de lista guardado, así que no '
                    'se duplicó nada. Se cargó para corregirla.')

            filas = lista_de_la_sesion(sesion)
            elegidos = _estados_validos(filas, enviados)
            if not elegidos:
                raise DatosInvalidos('No hay alumnos para registrar en esta sesión.')

            # Sin ignore_conflicts: en MySQL descartaría en silencio una fila
            # que viole una restricción. Un duplicado debe fallar y deshacerse.
            Asistencia.objects.bulk_create([
                Asistencia(sesion_id=sesion.pk, alumno_id=alumno_id, estado=estado,
                           registrado_por_id=usuario.pk)
                for alumno_id, estado in elegidos.items()
            ])
            sesion.estado = Sesion.Estado.REALIZADA
            sesion.save(update_fields=['estado'])
    except IntegrityError:
        raise ConflictoDeSesion(
            'La sesión cambió mientras se capturaba y no se guardó nada. '
            'Se cargó su estado actual.')
    return ResultadoPase(registrados=len(elegidos), sin_enviar=len(filas) - len(elegidos))


def corregir_pase_de_lista(sesion_id, enviados, usuario):
    """Corrige el pase de lista de una sesión realizada (RF-11).

    Solo se actualizan los registros cuyo estado cambió, y a cada uno se le
    asigna `registrado_por` para que el disparador anote quién hizo el cambio.
    Los registros sin cambio no se tocan. Un alumno sin registro que llegue con
    estado recibe su registro nuevo.
    """
    try:
        with transaction.atomic():
            sesion = _bloquear(sesion_id)
            _asegurar_admite_registros(sesion)
            if sesion.estado != Sesion.Estado.REALIZADA:
                raise ConflictoDeSesion(
                    'Esta sesión todavía no tiene el pase de lista guardado. '
                    'Se cargó para tomarlo.')

            filas = lista_de_la_sesion(sesion)
            elegidos = _estados_validos(filas, enviados)

            cambiados, nuevos = [], []
            for fila in filas:
                estado = elegidos.get(fila.alumno.pk)
                if estado is None:
                    continue
                if fila.registro is None:
                    nuevos.append(Asistencia(
                        sesion_id=sesion.pk, alumno_id=fila.alumno.pk, estado=estado,
                        registrado_por_id=usuario.pk))
                elif fila.registro.estado != estado:
                    if fila.registro.justificante and estado != Asistencia.Estado.JUSTIFICADO:
                        raise JustificanteImpideCambio(
                            f'El registro de {fila.alumno.nombre} tiene un justificante '
                            'adjunto, que solo admite el estado justificado. Quita '
                            'primero el justificante para cambiarlo.')
                    fila.registro.estado = estado
                    fila.registro.registrado_por_id = usuario.pk
                    cambiados.append(fila.registro)

            if cambiados:
                Asistencia.objects.bulk_update(cambiados, ['estado', 'registrado_por'])
            if nuevos:
                Asistencia.objects.bulk_create(nuevos)
    except IntegrityError:
        raise ConflictoDeSesion(
            'La sesión cambió mientras se corregía y no se guardó nada. '
            'Se cargó su estado actual.')
    return ResultadoCorreccion(cambiados=len(cambiados), nuevos=len(nuevos))


def _bloquear(sesion_id):
    """Lee la sesión bloqueando su fila hasta que termine la transacción."""
    return Sesion.objects.select_for_update(of=('self',)).get(pk=sesion_id)


def sesion_es_futura(sesion):
    """True si la fecha de la sesión es posterior a hoy (hora de Tijuana). Una
    sesión de hoy ya admite pase de lista, aunque todavía no empiece."""
    return sesion.fecha > timezone.localdate()


def _asegurar_admite_registros(sesion):
    if sesion.estado == Sesion.Estado.CANCELADA:
        raise SesionNoAdmiteRegistros(
            'La sesión está cancelada y no admite registros de asistencia.')
    if sesion_es_futura(sesion):
        raise SesionFutura(
            'No se puede tomar lista de una sesión futura: el pase de lista de '
            f'esta sesión se habilita el {sesion.fecha:%d/%m/%Y}.')


def _estados_validos(filas, enviados):
    """{alumno_id: estado} de los alumnos de la lista que vienen en el envío.

    No se confía en el POST: un alumno que no está en la lista de la sesión se
    ignora, y un estado que no sea uno de los cuatro rechaza todo el envío.
    """
    en_la_lista = {fila.alumno.pk for fila in filas}
    elegidos = {}
    for alumno_id, estado in enviados.items():
        if alumno_id not in en_la_lista:
            continue
        if estado not in ESTADOS_VALIDOS:
            raise DatosInvalidos(
                'El formulario trae un estado que no existe. No se guardó nada.')
        elegidos[alumno_id] = estado
    return elegidos
