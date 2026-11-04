"""Pruebas del resumen del inicio del docente y de las ayudas de presentación.

El resumen solo junta datos que ya existen (clases de hoy, grupos, alumnos y las
sesiones pendientes de RF-10); aquí se comprueba qué entra y qué no.
"""

from datetime import date, time

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from asistencia.models import Sesion
from asistencia.services.resumen import resumen_del_docente, saludo_de
from asistencia.templatetags.diseno import iniciales

from .utils import (
    AHORA, HOY, PASSWORD, crear_docente, crear_grupo, crear_periodo, crear_sesion,
    hora_fija, inscribir_alumnos,
)

REALIZADA = Sesion.Estado.REALIZADA
CANCELADA = Sesion.Estado.CANCELADA


class SaludoTests(SimpleTestCase):

    def test_el_saludo_cambia_a_las_12_y_a_las_19(self):
        self.assertEqual(saludo_de(6), 'Buenos días')
        self.assertEqual(saludo_de(11), 'Buenos días')
        self.assertEqual(saludo_de(12), 'Buenas tardes')
        self.assertEqual(saludo_de(18), 'Buenas tardes')
        self.assertEqual(saludo_de(19), 'Buenas noches')
        self.assertEqual(saludo_de(23), 'Buenas noches')


class InicialesTests(SimpleTestCase):

    def test_toma_la_inicial_de_las_dos_primeras_palabras(self):
        self.assertEqual(iniciales('María López Rivera'), 'ML')

    def test_una_sola_palabra_da_una_sola_letra(self):
        self.assertEqual(iniciales('Ana'), 'A')

    def test_pasa_a_mayusculas_y_respeta_la_enie(self):
        self.assertEqual(iniciales('ñandú pérez'), 'ÑP')

    def test_un_correo_se_trata_como_dos_palabras(self):
        self.assertEqual(iniciales('victor@asistencia.test'), 'VA')

    def test_vacio_o_nulo_da_un_signo_de_interrogacion(self):
        self.assertEqual(iniciales(''), '?')
        self.assertEqual(iniciales(None), '?')
        self.assertEqual(iniciales('   '), '?')

    def test_funciona_como_filtro_de_plantilla(self):
        html = Template('{% load diseno %}{{ nombre|iniciales }}').render(
            Context({'nombre': 'Luis Martínez'}))
        self.assertEqual(html, 'LM')


class ResumenDelDocenteTests(TestCase):

    def setUp(self):
        self.docente = crear_docente()
        self.grupo = crear_grupo(self.docente)

    def resumen(self):
        return resumen_del_docente(self.docente, ahora=AHORA)

    def test_trae_la_fecha_y_el_saludo_de_la_hora_indicada(self):
        resumen = self.resumen()

        self.assertEqual(resumen.hoy, HOY)
        self.assertEqual(resumen.saludo, 'Buenas tardes')       # AHORA son las 18:00

    def test_sin_datos_todo_es_cero(self):
        resumen = self.resumen()

        self.assertEqual(resumen.sesiones_de_hoy, [])
        self.assertEqual((resumen.grupos, resumen.alumnos, resumen.pendientes), (1, 0, 0))

    def test_las_clases_de_hoy_van_ordenadas_por_hora(self):
        tarde = crear_sesion(self.grupo, fecha=HOY, inicio=time(19, 0), fin=time(21, 0))
        manana = crear_sesion(self.grupo, fecha=HOY, inicio=time(8, 0), fin=time(10, 0))

        self.assertEqual(self.resumen().sesiones_de_hoy, [manana, tarde])

    def test_no_incluye_canceladas_ni_otros_dias_ni_otros_docentes(self):
        crear_sesion(self.grupo, fecha=HOY, estado=CANCELADA)
        crear_sesion(self.grupo, fecha=date(2026, 10, 21))
        otro = crear_docente(correo='otro@asistencia.test', username='otro')
        crear_sesion(crear_grupo(otro, clave='BD-201'), fecha=HOY)

        self.assertEqual(self.resumen().sesiones_de_hoy, [])

    def test_las_clases_de_un_periodo_inactivo_no_aparecen(self):
        crear_periodo('2026-2', activo=False)
        crear_sesion(self.grupo, fecha=HOY)

        resumen = self.resumen()

        self.assertEqual(resumen.sesiones_de_hoy, [])
        self.assertEqual(resumen.grupos, 0)

    def test_marca_cual_clase_de_hoy_ya_se_hizo_y_cual_esta_pendiente(self):
        inscribir_alumnos(self.grupo, 2)
        pasada = crear_sesion(self.grupo, fecha=HOY, inicio=time(8, 0), fin=time(10, 0))
        hecha = crear_sesion(self.grupo, fecha=HOY, inicio=time(10, 0), fin=time(12, 0),
                             estado=REALIZADA)
        futura = crear_sesion(self.grupo, fecha=HOY, inicio=time(19, 0), fin=time(21, 0))

        por_id = {s.pk: s for s in self.resumen().sesiones_de_hoy}

        self.assertTrue(por_id[hecha.pk].hecha)
        self.assertFalse(por_id[pasada.pk].hecha)
        self.assertTrue(por_id[pasada.pk].pendiente)       # ya terminó y no tiene lista
        self.assertFalse(por_id[futura.pk].pendiente)      # todavía no termina

    def test_cuenta_alumnos_distintos_aunque_esten_en_dos_grupos(self):
        otro_grupo = crear_grupo(self.docente, clave='BD-201')
        inscribir_alumnos(self.grupo, 3)
        inscribir_alumnos(otro_grupo, 2)          # las mismas dos primeras matrículas

        resumen = self.resumen()

        self.assertEqual(resumen.grupos, 2)
        self.assertEqual(resumen.alumnos, 3)

    def test_los_alumnos_de_un_grupo_congelado_no_cuentan(self):
        crear_periodo('2026-1', activo=False)
        viejo = crear_grupo(self.docente, clave='ADM-090', periodo='2026-1')
        inscribir_alumnos(viejo, 4, primera_matricula=1300000)
        inscribir_alumnos(self.grupo, 2)

        resumen = self.resumen()

        self.assertEqual((resumen.grupos, resumen.alumnos), (1, 2))

    def test_las_pendientes_de_un_grupo_congelado_no_se_cuentan(self):
        crear_periodo('2026-1', activo=False)
        viejo = crear_grupo(self.docente, clave='ADM-090', periodo='2026-1')
        inscribir_alumnos(viejo, 2, primera_matricula=1300000)
        crear_sesion(viejo, fecha=date(2026, 10, 5))        # sin lista, pero ya no se puede atender
        inscribir_alumnos(self.grupo, 2)
        crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        self.assertEqual(self.resumen().pendientes, 1)


class InicioDelDocenteTests(TestCase):

    def setUp(self):
        self.docente = crear_docente()
        self.docente.first_name = 'Elena'
        self.docente.save()
        self.client.login(username=self.docente.email, password=PASSWORD)

    def test_el_inicio_saluda_y_cuenta_las_clases_de_hoy(self):
        grupo = crear_grupo(self.docente)
        inscribir_alumnos(grupo, 3)
        crear_sesion(grupo, fecha=HOY, inicio=time(19, 0), fin=time(21, 0))

        with hora_fija():
            respuesta = self.client.get(reverse('inicio'))

        self.assertContains(respuesta, 'Buenas tardes, Elena')
        self.assertContains(respuesta, 'Hoy tienes 1 clase en tu calendario.')
        self.assertContains(respuesta, 'ADM-101')

    def test_sin_clases_el_inicio_lo_dice_y_ofrece_ir_a_los_grupos(self):
        with hora_fija():
            respuesta = self.client.get(reverse('inicio'))

        self.assertContains(respuesta, 'Hoy no tienes clases programadas.')
        self.assertContains(respuesta, 'Sin clases hoy')

    def test_las_pendientes_se_anuncian_en_singular_y_en_plural(self):
        grupo = crear_grupo(self.docente)
        inscribir_alumnos(grupo, 2)
        crear_sesion(grupo, fecha=date(2026, 10, 19))

        with hora_fija():
            una = self.client.get(reverse('inicio'))
        crear_sesion(grupo, fecha=date(2026, 10, 16))
        with hora_fija():
            dos = self.client.get(reverse('inicio'))

        self.assertContains(una, '1 sesión espera su pase de lista.')
        self.assertContains(dos, '2 sesiones esperan su pase de lista.')
