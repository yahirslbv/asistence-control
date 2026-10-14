"""Ayudas comunes para las pruebas."""

from contextlib import contextmanager
from datetime import date, datetime, time
from html.parser import HTMLParser
from unittest import mock
from zoneinfo import ZoneInfo

from asistencia.models import Alumno, Grupo, Inscripcion, Sesion, Usuario

PASSWORD = 'clave-de-prueba-123'

TIJUANA = ZoneInfo('America/Tijuana')


def momento(fecha, hora):
    """Un instante, con zona, a esa fecha y hora de Tijuana."""
    return datetime.combine(fecha, hora, tzinfo=TIJUANA)


# «Ahora» de las pruebas que dependen de la fecha: martes 20/10/2026, 18:00 en Tijuana.
AHORA = momento(date(2026, 10, 20), time(18, 0))
HOY = AHORA.date()


@contextmanager
def hora_fija(instante=AHORA):
    """Fija «ahora» (timezone.now) mientras dura el bloque."""
    with mock.patch('django.utils.timezone.now', return_value=instante):
        yield


class RelojFijoMixin:
    """Fija «ahora» en AHORA durante toda la clase, incluido `setUpTestData`.

    El pase de lista solo se permite hasta hoy, y estas pruebas usan sesiones
    con fechas fijas: sin esto dependerían del día en que se corran. Va antes
    de TestCase en la lista de clases base.

    Solo se parchea `django.utils.timezone.now`: la hora que escribe el
    disparador de la bitácora (`NOW()` de MySQL) sigue siendo la real.
    """

    instante = AHORA

    @classmethod
    def setUpClass(cls):
        reloj = mock.patch('django.utils.timezone.now', return_value=cls.instante)
        reloj.start()
        cls.addClassCleanup(reloj.stop)
        super().setUpClass()


def crear_docente(correo='docente@asistencia.test', username='docente'):
    return Usuario.objects.create_user(
        username=username, email=correo, password=PASSWORD,
        rol=Usuario.Rol.DOCENTE,
    )


def crear_administrador(correo='admin@asistencia.test', username='admin'):
    return Usuario.objects.create_user(
        username=username, email=correo, password=PASSWORD,
        rol=Usuario.Rol.ADMINISTRADOR, is_staff=True,
    )


def crear_grupo(docente, clave='ADM-101', materia='Administración de Proyectos',
                periodo='2026-2'):
    return Grupo.objects.create(
        clave=clave, materia=materia, periodo=periodo, docente=docente,
    )


def crear_sesion(grupo, fecha=date(2026, 10, 19), inicio=time(8, 0), fin=time(10, 0),
                 estado=Sesion.Estado.PROGRAMADA):
    return Sesion.objects.create(
        grupo=grupo, fecha=fecha, hora_inicio=inicio, hora_fin=fin, estado=estado)


def inscribir_alumnos(grupo, cantidad, primera_matricula=1200000,
                      fecha_alta=date(2026, 10, 1)):
    """Inscribe `cantidad` alumnos llamados «Alumno 00», «Alumno 01»..., que
    quedan en ese orden. Reutiliza al alumno si la matrícula ya existe."""
    alumnos = []
    for i in range(cantidad):
        alumno, _ = Alumno.objects.get_or_create(
            matricula=str(primera_matricula + i), defaults={'nombre': f'Alumno {i:02d}'})
        Inscripcion.objects.create(grupo=grupo, alumno=alumno, fecha_alta=fecha_alta)
        alumnos.append(alumno)
    return alumnos


class _ExtractorDeTabla(HTMLParser):
    """Saca el texto de las celdas de la tabla con cierto id, por sección."""

    def __init__(self, id_tabla):
        super().__init__(convert_charrefs=True)
        self.id_tabla = id_tabla
        self.dentro = False
        self.seccion = None
        self.secciones = {'thead': [], 'tbody': [], 'tfoot': []}
        self.fila = None
        self.celda = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and dict(attrs).get('id') == self.id_tabla:
            self.dentro = True
        elif self.dentro and tag in self.secciones:
            self.seccion = tag
        elif self.dentro and tag == 'tr':
            self.fila = []
        elif self.dentro and tag in ('td', 'th'):
            self.celda = []

    def handle_endtag(self, tag):
        if not self.dentro:
            return
        if tag == 'table':
            self.dentro = False
        elif tag in self.secciones:
            self.seccion = None
        elif tag == 'tr' and self.fila is not None:
            self.secciones[self.seccion].append(self.fila)
            self.fila = None
        elif tag in ('td', 'th') and self.celda is not None:
            self.fila.append(' '.join(''.join(self.celda).split()))
            self.celda = None

    def handle_data(self, data):
        if self.celda is not None:
            self.celda.append(data)


def celdas_de_la_tabla(html, id_tabla='tabla-reporte'):
    """{'encabezado': [...], 'filas': [[...]], 'pie': [[...]]} con el texto de
    cada celda de la tabla `id_tabla` tal como se ve en la pantalla."""
    if isinstance(html, bytes):
        html = html.decode('utf-8')
    extractor = _ExtractorDeTabla(id_tabla)
    extractor.feed(html)
    return {
        'encabezado': extractor.secciones['thead'][0] if extractor.secciones['thead'] else [],
        'filas': extractor.secciones['tbody'],
        'pie': extractor.secciones['tfoot'],
    }


def datos_del_pase(modo, estados):
    """Cuerpo del POST del pase de lista: {alumno_id: estado} -> campos del formulario."""
    datos = {'modo': modo}
    datos.update({f'estado_{alumno_id}': estado for alumno_id, estado in estados.items()})
    return datos
