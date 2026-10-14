"""Pruebas de la generación de sesiones (RF-06) y del calendario."""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Sesion
from asistencia.services.generar_sesiones import (
    MAX_DIAS_PERIODO, fechas_de_clase, generar_sesiones,
)
from asistencia.services.sesiones import calendario_de_sesiones

from .utils import PASSWORD, crear_docente, crear_grupo

LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, SABADO, DOMINGO = range(7)


class FechasDeClaseTests(TestCase):

    def test_lunes_y_miercoles_de_dos_semanas(self):
        # 2026-10-19 es lunes.
        fechas = list(fechas_de_clase(
            [LUNES, MIERCOLES], date(2026, 10, 19), date(2026, 11, 1)))

        self.assertEqual(fechas, [
            date(2026, 10, 19), date(2026, 10, 21),
            date(2026, 10, 26), date(2026, 10, 28),
        ])

    def test_las_dos_fechas_de_los_extremos_se_incluyen(self):
        fechas = list(fechas_de_clase([LUNES], date(2026, 10, 19), date(2026, 10, 26)))

        self.assertEqual(fechas, [date(2026, 10, 19), date(2026, 10, 26)])

    def test_un_periodo_sin_el_dia_elegido_no_da_fechas(self):
        self.assertEqual(
            list(fechas_de_clase([DOMINGO], date(2026, 10, 19), date(2026, 10, 24))), [])


class GenerarSesionesServicioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)

    def generar(self, grupo=None, **cambios):
        parametros = dict(
            dias=[LUNES, MIERCOLES], hora_inicio=time(8, 0), hora_fin=time(10, 0),
            fecha_inicio=date(2026, 10, 19), fecha_fin=date(2026, 11, 1),
        )
        parametros.update(cambios)
        return generar_sesiones(grupo or self.grupo, **parametros)

    def test_crea_una_sesion_por_cada_dia_de_clase(self):
        resultado = self.generar()

        self.assertEqual((resultado.creadas, resultado.existentes), (4, 0))
        sesiones = list(Sesion.objects.filter(grupo=self.grupo))
        self.assertEqual(
            [s.fecha for s in sesiones],
            [date(2026, 10, 19), date(2026, 10, 21), date(2026, 10, 26), date(2026, 10, 28)])
        self.assertTrue(all(s.hora_inicio == time(8, 0) for s in sesiones))
        self.assertTrue(all(s.hora_fin == time(10, 0) for s in sesiones))
        self.assertTrue(all(s.estado == Sesion.Estado.PROGRAMADA for s in sesiones))

    def test_repetirla_no_duplica_las_sesiones(self):
        self.generar()

        resultado = self.generar()

        self.assertEqual((resultado.creadas, resultado.existentes), (0, 4))
        self.assertEqual(Sesion.objects.count(), 4)

    def test_ampliar_el_periodo_solo_crea_las_que_faltan(self):
        self.generar()

        resultado = self.generar(fecha_fin=date(2026, 11, 8))

        self.assertEqual((resultado.creadas, resultado.existentes), (2, 4))
        self.assertEqual(Sesion.objects.count(), 6)

    def test_una_sesion_existente_no_se_pisa_aunque_cambie_la_hora_de_fin(self):
        existente = Sesion.objects.create(
            grupo=self.grupo, fecha=date(2026, 10, 19),
            hora_inicio=time(8, 0), hora_fin=time(9, 0))

        resultado = self.generar(dias=[LUNES], fecha_fin=date(2026, 10, 19))

        self.assertEqual((resultado.creadas, resultado.existentes), (0, 1))
        existente.refresh_from_db()
        self.assertEqual(existente.hora_fin, time(9, 0))

    def test_otro_horario_el_mismo_dia_si_se_crea(self):
        self.generar(dias=[LUNES], fecha_fin=date(2026, 10, 19))

        resultado = self.generar(
            dias=[LUNES], fecha_fin=date(2026, 10, 19),
            hora_inicio=time(12, 0), hora_fin=time(14, 0))

        self.assertEqual(resultado.creadas, 1)
        self.assertEqual(Sesion.objects.count(), 2)

    def test_los_grupos_no_se_mezclan(self):
        otro = crear_grupo(self.docente, clave='BD-201')
        self.generar()

        resultado = self.generar(grupo=otro)

        self.assertEqual(resultado.creadas, 4)
        self.assertEqual(Sesion.objects.count(), 8)

    def test_un_horario_invertido_se_rechaza_sin_crear_nada(self):
        # Con INSERT IGNORE la base descartaría en silencio estas filas.
        for inicio, fin in [(time(10, 0), time(8, 0)), (time(8, 0), time(8, 0))]:
            with self.subTest(inicio=inicio, fin=fin):
                with self.assertRaisesRegex(ValueError, 'hora de fin'):
                    self.generar(hora_inicio=inicio, hora_fin=fin)
        self.assertFalse(Sesion.objects.exists())

    def test_fechas_invertidas_o_periodo_demasiado_largo_se_rechazan(self):
        with self.assertRaises(ValueError):
            self.generar(fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 10, 19))
        with self.assertRaises(ValueError):
            self.generar(fecha_inicio=date(2026, 1, 1), fecha_fin=date(2027, 12, 31))
        self.assertFalse(Sesion.objects.exists())


class CalendarioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.otro = crear_grupo(cls.docente, clave='BD-201')
        for dia in (26, 19, 21):  # desordenadas a propósito
            Sesion.objects.create(grupo=cls.grupo, fecha=date(2026, 10, dia),
                                  hora_inicio=time(8, 0), hora_fin=time(10, 0))
        Sesion.objects.create(grupo=cls.grupo, fecha=date(2026, 10, 19),
                              hora_inicio=time(7, 0), hora_fin=time(8, 0))
        Sesion.objects.create(grupo=cls.otro, fecha=date(2026, 10, 20),
                              hora_inicio=time(8, 0), hora_fin=time(10, 0))

    def test_orden_cronologico_y_solo_las_del_grupo(self):
        sesiones = list(calendario_de_sesiones(self.grupo))

        self.assertEqual(
            [(s.fecha.day, s.hora_inicio.hour) for s in sesiones],
            [(19, 7), (19, 8), (21, 8), (26, 8)])

    def test_filtra_por_rango_con_extremos_incluidos(self):
        dias = [s.fecha.day for s in calendario_de_sesiones(
            self.grupo, desde=date(2026, 10, 19), hasta=date(2026, 10, 21))]

        self.assertEqual(dias, [19, 19, 21])

    def test_un_limite_abierto_no_filtra_ese_lado(self):
        self.assertEqual(
            [s.fecha.day for s in calendario_de_sesiones(self.grupo, desde=date(2026, 10, 21))],
            [21, 26])
        self.assertEqual(
            [s.fecha.day for s in calendario_de_sesiones(self.grupo, hasta=date(2026, 10, 19))],
            [19, 19])


class GenerarSesionesVistaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.url = reverse('sesiones_generar', args=[cls.grupo.pk])
        cls.lista = reverse('sesiones', args=[cls.grupo.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def datos(self, **cambios):
        return {'dias': ['0', '2'], 'hora_inicio': '08:00', 'hora_fin': '10:00',
                'fecha_inicio': '2026-10-19', 'fecha_fin': '2026-11-01', **cambios}

    def test_generar_crea_las_sesiones_y_avisa(self):
        respuesta = self.client.post(self.url, self.datos(), follow=True)

        self.assertRedirects(respuesta, self.lista)
        self.assertContains(respuesta, 'Se programaron 4 sesiones.')
        self.assertEqual(self.grupo.sesiones.count(), 4)

    def test_repetir_avisa_de_las_que_ya_existian(self):
        self.client.post(self.url, self.datos())

        respuesta = self.client.post(self.url, self.datos(), follow=True)

        self.assertContains(respuesta, '4 ya estaban programadas')
        self.assertEqual(self.grupo.sesiones.count(), 4)

    def test_acepta_la_fecha_en_formato_dia_mes_anio(self):
        self.client.post(self.url, self.datos(fecha_inicio='19/10/2026', fecha_fin='25/10/2026'))

        self.assertEqual(self.grupo.sesiones.count(), 2)

    def test_datos_invalidos_no_crean_sesiones(self):
        casos = {
            'sin días': self.datos(dias=[]),
            'hora fin antes del inicio': self.datos(hora_fin='07:00'),
            'último día antes del primero': self.datos(fecha_fin='2026-10-01'),
            f'periodo de más de {MAX_DIAS_PERIODO} días': self.datos(fecha_fin='2028-01-01'),
            'ninguna fecha cae en los días': self.datos(
                dias=['6'], fecha_inicio='2026-10-19', fecha_fin='2026-10-24'),
            'campos vacíos': {},
        }
        for nombre, datos in casos.items():
            with self.subTest(nombre):
                respuesta = self.client.post(self.url, datos)
                self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.grupo.sesiones.exists())

    def test_el_formulario_muestra_los_siete_dias(self):
        respuesta = self.client.get(self.url)

        for dia in ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'):
            self.assertContains(respuesta, dia)


class CalendarioVistaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.url = reverse('sesiones', args=[cls.grupo.pk])
        for fecha in (date(2026, 10, 19), date(2026, 10, 26), date(2026, 11, 2)):
            Sesion.objects.create(grupo=cls.grupo, fecha=fecha,
                                  hora_inicio=time(8, 0), hora_fin=time(10, 0))

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_agrupa_las_sesiones_por_mes(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Octubre 2026')
        self.assertContains(respuesta, 'Noviembre 2026')
        self.assertContains(respuesta, '08:00 – 10:00')
        self.assertEqual(len(respuesta.context['sesiones']), 3)

    def test_filtra_por_fechas(self):
        respuesta = self.client.get(self.url, {'desde': '2026-10-20', 'hasta': '2026-10-31'})

        self.assertEqual([s.fecha for s in respuesta.context['sesiones']], [date(2026, 10, 26)])

    def test_una_fecha_mal_escrita_se_ignora(self):
        for valor in ('no-es-fecha', '2026-02-31', ''):
            with self.subTest(valor=valor):
                respuesta = self.client.get(self.url, {'desde': valor})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(len(respuesta.context['sesiones']), 3)

    def test_sin_sesiones_invita_a_generarlas(self):
        otro = crear_grupo(self.docente, clave='VACIO-1')

        respuesta = self.client.get(reverse('sesiones', args=[otro.pk]))

        self.assertContains(respuesta, 'todavía no tiene sesiones')

    def test_el_detalle_del_grupo_enlaza_las_sesiones(self):
        respuesta = self.client.get(reverse('grupo_detalle', args=[self.grupo.pk]))

        self.assertContains(respuesta, self.url)
