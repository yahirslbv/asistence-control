"""Reportes de asistencia por alumno, grupo y periodo (RF-13 y RF-14).

Reglas (CLAUDE.md, sección 9.2):
- Cuentan como asistencia presente, retardo y justificado.
- Solo cuentan las sesiones realizadas.
- Porcentaje = asistencias / registros de asistencia × 100.

Decisiones de este módulo:
- Se reporta solo a los alumnos con inscripción actual en el grupo. Los
  registros de un alumno dado de baja no entran al porcentaje del grupo ni salen
  en la tabla (siguen visibles en la sesión).
- Un alumno sin registros muestra «Sin registros», no 0 %, y no se marca.
- El cálculo es con enteros y Decimal, nunca con float. El porcentaje se muestra
  con un decimal TRUNCADO (79.96 no se ve como 80.0) y la marca de «bajo el
  mínimo» se decide con enteros: asistencias × 100 < mínimo × registros.
- El porcentaje del grupo es el ponderado: asistencias totales / registros
  totales de los inscritos actuales.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q

from ..models import Alumno, Asistencia, Grupo, Inscripcion, Sesion
from .pendientes import sesiones_pendientes
from .tablas import TablaDeReporte

SIN_REGISTROS = 'Sin registros'
BAJO_EL_MINIMO = 'Bajo el mínimo'
CUMPLE = 'Cumple'
SIN_SITUACION = '—'
SIN_REGISTRO_EN_SESION = 'Sin registro'

ESTADO_REALIZADA = Sesion.Estado.REALIZADA


# --- Funciones puras ---------------------------------------------------------

def minimo_de_asistencia():
    """Porcentaje mínimo (ASISTENCIA_MINIMA), leído al momento de usarlo."""
    return settings.ASISTENCIA_MINIMA


def porcentaje_truncado(asistencias, registros):
    """Porcentaje con un decimal, truncado (no redondeado), o None sin registros.

    Todo en enteros: 1999 de 2500 da 79.9 (no 80.0).
    """
    if registros <= 0:
        return None
    decimas = (asistencias * 1000) // registros
    return Decimal(decimas).scaleb(-1)


def esta_bajo_el_minimo(asistencias, registros, minimo=None):
    """True si el porcentaje es estrictamente menor al mínimo. Sin registros
    nunca se marca. Se compara con enteros, sin dividir."""
    if minimo is None:
        minimo = minimo_de_asistencia()
    return registros > 0 and asistencias * 100 < minimo * registros


def texto_de_porcentaje(porcentaje):
    return SIN_REGISTROS if porcentaje is None else f'{porcentaje} %'


def aviso_de_pendientes(pendientes):
    """Texto del aviso cuando el grupo tiene sesiones que el porcentaje no
    incluye por completo (RF-10), o None si no hay."""
    n = len(pendientes)
    if not n:
        return None
    if n == 1:
        return ('Hay 1 sesión sin pase de lista o con el pase incompleto: '
                'el porcentaje no la incluye por completo.')
    return (f'Hay {n} sesiones sin pase de lista o con el pase incompleto: '
            'el porcentaje no las incluye por completo.')


# --- Reporte del grupo -------------------------------------------------------

@dataclass(frozen=True)
class FilaDeAlumno:
    alumno: Alumno
    registros: int
    presentes: int
    retardos: int
    ausentes: int
    justificados: int
    asistencias: int
    porcentaje: Decimal | None
    bajo_el_minimo: bool

    @property
    def porcentaje_texto(self):
        return texto_de_porcentaje(self.porcentaje)

    @property
    def situacion(self):
        if self.registros == 0:
            return SIN_SITUACION
        return BAJO_EL_MINIMO if self.bajo_el_minimo else CUMPLE


@dataclass
class ReporteDeGrupo:
    grupo: Grupo
    minimo: int
    filas: list[FilaDeAlumno]
    sesiones_realizadas: int
    registros: int
    asistencias: int
    porcentaje: Decimal | None       # el ponderado del grupo
    alumnos_bajo_el_minimo: int
    pendientes: list = field(default_factory=list)

    @property
    def porcentaje_texto(self):
        return texto_de_porcentaje(self.porcentaje)

    @property
    def aviso(self):
        return aviso_de_pendientes(self.pendientes)

    @property
    def presentes(self):
        return sum(f.presentes for f in self.filas)

    @property
    def retardos(self):
        return sum(f.retardos for f in self.filas)

    @property
    def ausentes(self):
        return sum(f.ausentes for f in self.filas)

    @property
    def justificados(self):
        return sum(f.justificados for f in self.filas)


def reporte_del_grupo(grupo, ahora=None):
    """Reporte de asistencia de un grupo. Número fijo de consultas: no crece
    con el número de alumnos ni de sesiones."""
    minimo = minimo_de_asistencia()
    alumnos = list(
        Alumno.objects.filter(inscripciones__grupo=grupo).order_by('nombre', 'matricula'))
    conteos = _conteos_por_alumno(grupo)

    filas = [_fila_de_alumno(alumno, conteos.get(alumno.pk), minimo) for alumno in alumnos]
    registros = sum(f.registros for f in filas)
    asistencias = sum(f.asistencias for f in filas)

    return ReporteDeGrupo(
        grupo=grupo,
        minimo=minimo,
        filas=filas,
        sesiones_realizadas=Sesion.objects.filter(grupo=grupo, estado=ESTADO_REALIZADA).count(),
        registros=registros,
        asistencias=asistencias,
        porcentaje=porcentaje_truncado(asistencias, registros),
        alumnos_bajo_el_minimo=sum(1 for f in filas if f.bajo_el_minimo),
        # grupo.docente_id basta: evita cargar al docente solo para filtrar.
        pendientes=sesiones_pendientes(grupo.docente_id, grupo=grupo, ahora=ahora),
    )


def _agregados():
    """Columnas agregadas que se repiten en las consultas de conteo."""
    return dict(
        registros=Count('pk'),
        presentes=Count('pk', filter=Q(estado=Asistencia.Estado.PRESENTE)),
        retardos=Count('pk', filter=Q(estado=Asistencia.Estado.RETARDO)),
        ausentes=Count('pk', filter=Q(estado=Asistencia.Estado.AUSENTE)),
        justificados=Count('pk', filter=Q(estado=Asistencia.Estado.JUSTIFICADO)),
        asistencias=Count('pk', filter=Q(estado__in=Asistencia.CUENTAN_COMO_ASISTENCIA)),
    )


def _conteos_por_alumno(grupo):
    """{alumno_id: conteos} de las sesiones realizadas del grupo, solo de los
    inscritos actuales.

    Una sola consulta sobre `asistencia`. Se filtra por una subconsulta de las
    inscripciones, sin unir tablas de muchos a muchos: así ningún conteo se
    multiplica.
    """
    filas = (
        Asistencia.objects.filter(
            sesion__grupo=grupo,
            sesion__estado=ESTADO_REALIZADA,
            alumno_id__in=Inscripcion.objects.filter(grupo=grupo).values('alumno_id'),
        )
        .values('alumno_id')
        .annotate(**_agregados())
    )
    return {fila['alumno_id']: fila for fila in filas}


def _fila_de_alumno(alumno, conteo, minimo):
    conteo = conteo or dict(
        registros=0, presentes=0, retardos=0, ausentes=0, justificados=0, asistencias=0)
    return FilaDeAlumno(
        alumno=alumno,
        registros=conteo['registros'],
        presentes=conteo['presentes'],
        retardos=conteo['retardos'],
        ausentes=conteo['ausentes'],
        justificados=conteo['justificados'],
        asistencias=conteo['asistencias'],
        porcentaje=porcentaje_truncado(conteo['asistencias'], conteo['registros']),
        bajo_el_minimo=esta_bajo_el_minimo(
            conteo['asistencias'], conteo['registros'], minimo),
    )


COLUMNAS_DEL_GRUPO = [
    'Matrícula', 'Nombre', 'Registros', 'Presentes', 'Retardos', 'Ausentes',
    'Justificados', 'Asistencias', 'Porcentaje', 'Situación',
]


def tabla_del_grupo(reporte):
    """El reporte del grupo como tabla, para pantalla y exportaciones."""
    grupo = reporte.grupo
    filas = [
        [f.alumno.matricula, f.alumno.nombre, f.registros, f.presentes, f.retardos,
         f.ausentes, f.justificados, f.asistencias, f.porcentaje_texto, f.situacion]
        for f in reporte.filas
    ]
    filas.append([
        '', 'Grupo (ponderado)', reporte.registros, reporte.presentes, reporte.retardos,
        reporte.ausentes, reporte.justificados, reporte.asistencias,
        reporte.porcentaje_texto, '',
    ])
    notas = [
        f'Sesiones realizadas consideradas: {reporte.sesiones_realizadas}. '
        'Solo se reporta a los alumnos inscritos actualmente.',
        'Presente, retardo y justificado cuentan como asistencia. '
        'Los porcentajes se truncan a un decimal.',
        f'Alumnos bajo el mínimo: {reporte.alumnos_bajo_el_minimo}.',
    ]
    if reporte.aviso:
        notas.append(reporte.aviso)
    return TablaDeReporte(
        titulo=f'Reporte de asistencia · {grupo.clave}',
        subtitulo=(f'{grupo.materia} · Periodo {grupo.periodo} · '
                   f'Mínimo de asistencia: {reporte.minimo} %'),
        columnas=COLUMNAS_DEL_GRUPO,
        filas=filas,
        notas=notas,
        marcadas=frozenset(i for i, f in enumerate(reporte.filas) if f.bajo_el_minimo),
        con_totales=True,
        nombre_base=f'reporte_{grupo.clave}_{grupo.periodo}',
    )


# --- Reporte del periodo (pantalla «Reportes») -------------------------------

@dataclass(frozen=True)
class ResumenDeGrupo:
    grupo: Grupo
    alumnos: int                    # inscritos actuales
    registros: int
    asistencias: int
    porcentaje: Decimal | None      # el ponderado del grupo
    alumnos_bajo_el_minimo: int

    @property
    def porcentaje_texto(self):
        return texto_de_porcentaje(self.porcentaje)


@dataclass
class ReporteDelPeriodo:
    periodo: str
    minimo: int
    resumenes: list[ResumenDeGrupo]


def periodos_del_docente(docente):
    """Periodos en que el docente tiene grupos, del más reciente al más antiguo.

    Se ordenan como texto, de mayor a menor: con el formato AAAA-N (2026-2) el
    orden alfabético es el cronológico.
    """
    periodos = Grupo.objects.filter(docente=docente).values_list('periodo', flat=True)
    return sorted(set(periodos), reverse=True)


def reporte_del_periodo(docente, periodo):
    """Porcentaje y alumnos bajo el mínimo de cada grupo del docente en el
    periodo. Número fijo de consultas, sin importar cuántos grupos haya."""
    minimo = minimo_de_asistencia()
    grupos = list(Grupo.objects.filter(docente=docente, periodo=periodo).order_by('clave'))
    ids = [g.pk for g in grupos]

    inscritos = Inscripcion.objects.filter(grupo_id__in=ids).values_list('grupo_id', 'alumno_id')
    alumnos_por_grupo = {}
    pares_vigentes = set()
    for grupo_id, alumno_id in inscritos:
        alumnos_por_grupo[grupo_id] = alumnos_por_grupo.get(grupo_id, 0) + 1
        pares_vigentes.add((grupo_id, alumno_id))

    conteos = (
        Asistencia.objects.filter(sesion__grupo_id__in=ids, sesion__estado=ESTADO_REALIZADA)
        .values('sesion__grupo_id', 'alumno_id')
        .annotate(registros=Count('pk'),
                  asistencias=Count('pk', filter=Q(estado__in=Asistencia.CUENTAN_COMO_ASISTENCIA)))
    )
    registros, asistencias, bajo = {}, {}, {}
    for fila in conteos:
        grupo_id = fila['sesion__grupo_id']
        if (grupo_id, fila['alumno_id']) not in pares_vigentes:
            continue   # alumno dado de baja: no entra al reporte
        registros[grupo_id] = registros.get(grupo_id, 0) + fila['registros']
        asistencias[grupo_id] = asistencias.get(grupo_id, 0) + fila['asistencias']
        if esta_bajo_el_minimo(fila['asistencias'], fila['registros'], minimo):
            bajo[grupo_id] = bajo.get(grupo_id, 0) + 1

    resumenes = [
        ResumenDeGrupo(
            grupo=grupo,
            alumnos=alumnos_por_grupo.get(grupo.pk, 0),
            registros=registros.get(grupo.pk, 0),
            asistencias=asistencias.get(grupo.pk, 0),
            porcentaje=porcentaje_truncado(asistencias.get(grupo.pk, 0), registros.get(grupo.pk, 0)),
            alumnos_bajo_el_minimo=bajo.get(grupo.pk, 0),
        )
        for grupo in grupos
    ]
    return ReporteDelPeriodo(periodo=periodo, minimo=minimo, resumenes=resumenes)


# --- Reporte del alumno en el grupo ------------------------------------------

@dataclass(frozen=True)
class SesionDelAlumno:
    sesion: Sesion
    estado: str | None              # None: no tiene registro en esa sesión

    @property
    def estado_texto(self):
        return Asistencia.Estado(self.estado).label if self.estado else SIN_REGISTRO_EN_SESION


@dataclass
class ReporteDeAlumno:
    grupo: Grupo
    alumno: Alumno
    minimo: int
    fila: FilaDeAlumno               # los mismos números que ve el reporte del grupo
    sesiones: list[SesionDelAlumno]
    pendientes: list = field(default_factory=list)

    @property
    def aviso(self):
        return aviso_de_pendientes(self.pendientes)


def reporte_del_alumno(grupo, alumno, ahora=None):
    """Porcentaje del alumno en el grupo y su detalle sesión por sesión, solo de
    sesiones realizadas. El alumno debe estar inscrito (lo valida la vista)."""
    minimo = minimo_de_asistencia()
    sesiones = list(
        Sesion.objects.filter(grupo=grupo, estado=ESTADO_REALIZADA)
        .order_by('fecha', 'hora_inicio'))
    estados = dict(
        Asistencia.objects.filter(
            alumno=alumno, sesion__grupo=grupo, sesion__estado=ESTADO_REALIZADA)
        .values_list('sesion_id', 'estado'))

    cuenta = lambda *validos: sum(1 for e in estados.values() if e in validos)   # noqa: E731
    P, R, A, J = (Asistencia.Estado.PRESENTE, Asistencia.Estado.RETARDO,
                  Asistencia.Estado.AUSENTE, Asistencia.Estado.JUSTIFICADO)
    conteo = dict(
        registros=len(estados), presentes=cuenta(P), retardos=cuenta(R),
        ausentes=cuenta(A), justificados=cuenta(J),
        asistencias=sum(1 for e in estados.values() if e in Asistencia.CUENTAN_COMO_ASISTENCIA),
    )
    return ReporteDeAlumno(
        grupo=grupo,
        alumno=alumno,
        minimo=minimo,
        fila=_fila_de_alumno(alumno, conteo, minimo),
        sesiones=[SesionDelAlumno(s, estados.get(s.pk)) for s in sesiones],
        pendientes=sesiones_pendientes(grupo.docente_id, grupo=grupo, ahora=ahora),
    )


def tabla_del_alumno(reporte):
    """El reporte del alumno como tabla, para pantalla y exportaciones."""
    grupo, alumno, fila = reporte.grupo, reporte.alumno, reporte.fila
    filas = [
        [s.sesion.fecha.strftime('%d/%m/%Y'),
         f'{s.sesion.hora_inicio:%H:%M} – {s.sesion.hora_fin:%H:%M}',
         s.estado_texto]
        for s in reporte.sesiones
    ]
    resumen = (f'Porcentaje: {fila.porcentaje_texto}'
               + (f' ({fila.asistencias} de {fila.registros} registros)' if fila.registros else '')
               + f' · Mínimo de asistencia: {reporte.minimo} %'
               + (f' · {BAJO_EL_MINIMO}' if fila.bajo_el_minimo else ''))
    notas = [
        'Solo se muestran las sesiones realizadas. Presente, retardo y justificado '
        'cuentan como asistencia. El porcentaje se trunca a un decimal.',
    ]
    if reporte.aviso:
        notas.append(reporte.aviso)
    return TablaDeReporte(
        titulo=f'Reporte de asistencia · {alumno.nombre}',
        subtitulo=(f'{alumno.matricula} · {grupo.clave} · {grupo.materia} · '
                   f'Periodo {grupo.periodo} · {resumen}'),
        columnas=['Fecha', 'Horario', 'Estado'],
        filas=filas,
        notas=notas,
        nombre_base=f'reporte_{grupo.clave}_{grupo.periodo}_{alumno.matricula}',
    )
