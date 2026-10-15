"""Consultas que no crecen con el tamaño de los datos (RNF-07, fase H).

El pase de lista, su corrección, los reportes del grupo y los servicios de
pendientes ya tienen su prueba de conteo en test_pase_de_lista, test_correccion,
test_reportes y test_pendientes. Aquí van las pantallas y exportaciones que
faltaban: lista de grupos, detalle, lista de sesiones, reportes y descargas.

Cada prueba compara un grupo chico con uno de 50 alumnos y 48 sesiones (un
semestre de tres sesiones por semana): el número de consultas debe ser el mismo.
La medición de tiempos con MySQL se hace aparte y se documenta en
docs/informe_pruebas.md; estas pruebas protegen contra un N+1.
"""

from datetime import date, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Asistencia, Sesion

from .utils import (
    PASSWORD, RelojFijoMixin, crear_docente, crear_grupo, inscribir_alumnos,
)

PRESENTE = Asistencia.Estado.PRESENTE
AUSENTE = Asistencia.Estado.AUSENTE
INICIO_DEL_SEMESTRE = date(2026, 8, 3)


class ConsultasPorTamanoBase(RelojFijoMixin, TestCase):

    def setUp(self):
        self.docente = crear_docente()
        self.client.login(username='docente@asistencia.test', password=PASSWORD)
        self.contador = 0

    def grupo_con(self, alumnos, sesiones, clave):
        """Grupo con `alumnos` inscritos y `sesiones` realizadas, todas con
        registro de todos (uno de cada siete, ausente)."""
        self.contador += 1
        grupo = crear_grupo(self.docente, clave=clave)
        lista = inscribir_alumnos(
            grupo, alumnos, primera_matricula=5000000 + self.contador * 1000)
        Sesion.objects.bulk_create([
            Sesion(grupo=grupo, fecha=INICIO_DEL_SEMESTRE + timedelta(days=i),
                   hora_inicio='08:00', hora_fin='10:00', estado=Sesion.Estado.REALIZADA)
            for i in range(sesiones)
        ])
        realizadas = list(grupo.sesiones.order_by('fecha'))   # MySQL no devuelve los id
        Asistencia.objects.bulk_create([
            Asistencia(sesion=sesion, alumno=alumno, registrado_por=self.docente,
                       estado=AUSENTE if (i + j) % 7 == 0 else PRESENTE)
            for j, sesion in enumerate(realizadas) for i, alumno in enumerate(lista)
        ])
        return grupo, lista

    def consultas(self, url):
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, url)
        return len(capturadas)

    def comparar(self, chico, grande, limite):
        self.assertEqual(
            chico, grande, 'el número de consultas crece con el tamaño de los datos')
        self.assertLessEqual(grande, limite)


class PantallasDeGruposTests(ConsultasPorTamanoBase):

    def test_el_detalle_del_grupo_no_depende_de_alumnos_ni_de_sesiones(self):
        chico, _ = self.grupo_con(5, 3, 'CH-DET')
        grande, _ = self.grupo_con(50, 48, 'GR-DET')

        self.comparar(
            self.consultas(reverse('grupo_detalle', args=[chico.pk])),
            self.consultas(reverse('grupo_detalle', args=[grande.pk])), 12)

    def test_la_lista_de_sesiones_no_depende_del_numero_de_sesiones(self):
        chico, _ = self.grupo_con(5, 3, 'CH-SES')
        grande, _ = self.grupo_con(50, 48, 'GR-SES')

        self.comparar(
            self.consultas(reverse('sesiones', args=[chico.pk])),
            self.consultas(reverse('sesiones', args=[grande.pk])), 12)

    def test_la_lista_de_grupos_no_depende_del_numero_de_grupos_ni_de_su_tamano(self):
        self.grupo_con(5, 3, 'L-1')
        con_uno = self.consultas(reverse('grupos'))
        for i in range(2, 9):
            self.grupo_con(50, 48, f'L-{i}')
        con_ocho = self.consultas(reverse('grupos'))

        self.comparar(con_uno, con_ocho, 12)


class PantallasDeReportesTests(ConsultasPorTamanoBase):

    def test_el_inicio_de_reportes_no_depende_del_numero_de_grupos(self):
        self.grupo_con(5, 3, 'R-1')
        con_uno = self.consultas(reverse('reportes'))
        for i in range(2, 9):
            self.grupo_con(50, 48, f'R-{i}')
        con_ocho = self.consultas(reverse('reportes'))

        self.comparar(con_uno, con_ocho, 12)

    def test_el_reporte_de_un_alumno_no_depende_del_numero_de_sesiones(self):
        chico, alumnos_chico = self.grupo_con(5, 3, 'CH-ALU')
        grande, alumnos_grande = self.grupo_con(50, 48, 'GR-ALU')

        self.comparar(
            self.consultas(reverse('reporte_alumno', args=[chico.pk, alumnos_chico[0].pk])),
            self.consultas(reverse('reporte_alumno', args=[grande.pk, alumnos_grande[0].pk])), 12)


class ExportacionesTests(ConsultasPorTamanoBase):

    def descargar(self, url):
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
            b''.join(respuesta.streaming_content)   # el archivo se genera al leerlo
        self.assertEqual(respuesta.status_code, 200, url)
        return len(capturadas)

    def test_exportar_el_reporte_del_grupo_no_depende_del_numero_de_alumnos(self):
        chico, _ = self.grupo_con(5, 3, 'CH-EXP')
        grande, _ = self.grupo_con(50, 48, 'GR-EXP')

        for formato in ('pdf', 'xlsx'):
            with self.subTest(formato=formato):
                self.comparar(
                    self.descargar(reverse('reporte_grupo_exportar', args=[chico.pk, formato])),
                    self.descargar(reverse('reporte_grupo_exportar', args=[grande.pk, formato])), 12)

    def test_exportar_el_reporte_de_un_alumno_no_depende_del_numero_de_sesiones(self):
        chico, alumnos_chico = self.grupo_con(5, 3, 'CH-EXA')
        grande, alumnos_grande = self.grupo_con(50, 48, 'GR-EXA')

        for formato in ('pdf', 'xlsx'):
            with self.subTest(formato=formato):
                self.comparar(
                    self.descargar(reverse(
                        'reporte_alumno_exportar', args=[chico.pk, alumnos_chico[0].pk, formato])),
                    self.descargar(reverse(
                        'reporte_alumno_exportar', args=[grande.pk, alumnos_grande[0].pk, formato])), 12)
