"""Pruebas de edición y cancelación de sesiones (RF-07)."""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Sesion
from asistencia.services.sesiones import (
    SesionNoModificable, asegurar_programada, cancelar_sesion,
)

from .utils import PASSWORD, crear_docente, crear_grupo


def crear_sesion(grupo, dia=19, inicio=time(8, 0), fin=time(10, 0),
                 estado=Sesion.Estado.PROGRAMADA):
    return Sesion.objects.create(
        grupo=grupo, fecha=date(2026, 10, dia), hora_inicio=inicio,
        hora_fin=fin, estado=estado)


class SesionesServicioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.grupo = crear_grupo(crear_docente())

    def test_cancelar_pasa_la_sesion_a_cancelada_sin_borrarla(self):
        sesion = crear_sesion(self.grupo)

        cancelar_sesion(sesion)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.CANCELADA)
        self.assertEqual(Sesion.objects.count(), 1)

    def test_solo_una_sesion_programada_se_puede_modificar(self):
        for dia, estado in [(20, Sesion.Estado.REALIZADA), (21, Sesion.Estado.CANCELADA)]:
            with self.subTest(estado=estado):
                sesion = crear_sesion(self.grupo, dia=dia, estado=estado)
                with self.assertRaises(SesionNoModificable):
                    asegurar_programada(sesion)
                with self.assertRaises(SesionNoModificable):
                    cancelar_sesion(sesion)
                sesion.refresh_from_db()
                self.assertEqual(sesion.estado, estado)


class EditarSesionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.lista = reverse('sesiones', args=[cls.grupo.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)
        self.sesion = crear_sesion(self.grupo)
        self.url = reverse('sesion_editar', args=[self.sesion.pk])

    def datos(self, **cambios):
        return {'fecha': '2026-10-20', 'hora_inicio': '09:00', 'hora_fin': '11:00', **cambios}

    def test_el_formulario_trae_los_datos_actuales(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'value="2026-10-19"')
        self.assertContains(respuesta, 'value="08:00"')
        self.assertContains(respuesta, 'value="10:00"')

    def test_editar_cambia_la_fecha_y_el_horario(self):
        respuesta = self.client.post(self.url, self.datos(), follow=True)

        self.assertRedirects(respuesta, self.lista)
        self.assertContains(respuesta, 'Sesión actualizada.')
        self.sesion.refresh_from_db()
        self.assertEqual(
            (self.sesion.fecha, self.sesion.hora_inicio, self.sesion.hora_fin),
            (date(2026, 10, 20), time(9, 0), time(11, 0)))
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)

    def test_guardar_sin_cambios_no_choca_consigo_misma(self):
        respuesta = self.client.post(self.url, self.datos(
            fecha='2026-10-19', hora_inicio='08:00', hora_fin='10:00'))

        self.assertRedirects(respuesta, self.lista)

    def test_no_se_puede_repetir_la_fecha_y_hora_de_inicio_de_otra_sesion(self):
        crear_sesion(self.grupo, dia=20, inicio=time(9, 0), fin=time(10, 0))

        respuesta = self.client.post(self.url, self.datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya tiene una sesión en esa fecha y hora de inicio')
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fecha, date(2026, 10, 19))

    def test_la_misma_fecha_y_hora_en_otro_grupo_si_se_permite(self):
        otro = crear_grupo(self.docente, clave='BD-201')
        crear_sesion(otro, dia=20, inicio=time(9, 0), fin=time(10, 0))

        respuesta = self.client.post(self.url, self.datos())

        self.assertRedirects(respuesta, self.lista)

    def test_la_hora_de_fin_debe_ser_posterior_a_la_de_inicio(self):
        for fin in ('09:00', '08:30'):
            with self.subTest(fin=fin):
                respuesta = self.client.post(self.url, self.datos(hora_fin=fin))
                self.assertContains(respuesta, 'La hora de fin debe ser posterior')
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.hora_fin, time(10, 0))

    def test_campos_vacios_muestran_errores(self):
        respuesta = self.client.post(self.url, {})

        self.assertEqual(respuesta.status_code, 200)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fecha, date(2026, 10, 19))

    def test_una_sesion_realizada_o_cancelada_no_se_edita(self):
        for estado, texto in [(Sesion.Estado.REALIZADA, 'realizada'),
                              (Sesion.Estado.CANCELADA, 'cancelada')]:
            sesion = crear_sesion(self.grupo, dia=25 if texto == 'realizada' else 26, estado=estado)
            url = reverse('sesion_editar', args=[sesion.pk])
            for metodo in ('get', 'post'):
                with self.subTest(estado=texto, metodo=metodo):
                    respuesta = getattr(self.client, metodo)(url, follow=True) if metodo == 'get' \
                        else self.client.post(url, self.datos(), follow=True)
                    self.assertRedirects(respuesta, self.lista)
                    self.assertContains(respuesta, f'esta ya está {texto}')
            sesion.refresh_from_db()
            self.assertEqual(sesion.fecha.day, 25 if texto == 'realizada' else 26)


class CancelarSesionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.lista = reverse('sesiones', args=[cls.grupo.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)
        self.sesion = crear_sesion(self.grupo)
        self.url = reverse('sesion_cancelar', args=[self.sesion.pk])

    def test_la_confirmacion_no_cancela(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)

    def test_confirmar_cancela_la_sesion(self):
        respuesta = self.client.post(self.url, follow=True)

        self.assertRedirects(respuesta, self.lista)
        self.assertContains(respuesta, 'Sesión cancelada.')
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.CANCELADA)

    def test_cancelar_dos_veces_avisa_y_no_falla(self):
        self.client.post(self.url)

        respuesta = self.client.post(self.url, follow=True)

        self.assertRedirects(respuesta, self.lista)
        self.assertContains(respuesta, 'esta ya está cancelada')

    def test_una_sesion_cancelada_sigue_ocupando_su_horario(self):
        self.client.post(self.url)

        respuesta = self.client.post(reverse('sesiones_generar', args=[self.grupo.pk]), {
            'dias': ['0'], 'hora_inicio': '08:00', 'hora_fin': '10:00',
            'fecha_inicio': '2026-10-19', 'fecha_fin': '2026-10-19'}, follow=True)

        self.assertContains(respuesta, '1 ya estaban programadas')
        self.assertEqual(Sesion.objects.count(), 1)

    def test_el_calendario_ofrece_acciones_solo_para_las_programadas(self):
        realizada = crear_sesion(self.grupo, dia=26, estado=Sesion.Estado.REALIZADA)

        respuesta = self.client.get(self.lista)

        self.assertContains(respuesta, reverse('sesion_editar', args=[self.sesion.pk]))
        self.assertContains(respuesta, reverse('sesion_cancelar', args=[self.sesion.pk]))
        self.assertNotContains(respuesta, reverse('sesion_editar', args=[realizada.pk]))
        self.assertNotContains(respuesta, reverse('sesion_cancelar', args=[realizada.pk]))
