"""Pruebas de la alerta de sesiones sin registrar o incompletas (RF-10)."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from asistencia.models import Asistencia, Inscripcion, Sesion
from asistencia.services.pendientes import sesiones_pendientes

from .utils import (
    AHORA, HOY, PASSWORD, crear_docente, crear_grupo, crear_sesion,
    datos_del_pase, hora_fija, inscribir_alumnos,
)

REALIZADA = Sesion.Estado.REALIZADA
CANCELADA = Sesion.Estado.CANCELADA


def registrar(sesion, alumnos, usuario, estado=Asistencia.Estado.PRESENTE):
    Asistencia.objects.bulk_create([
        Asistencia(sesion=sesion, alumno=a, estado=estado, registrado_por=usuario)
        for a in alumnos])


class SesionesPendientesTests(TestCase):

    def setUp(self):
        self.docente = crear_docente()
        self.grupo = crear_grupo(self.docente)
        self.alumnos = inscribir_alumnos(self.grupo, 3)

    def pendientes(self, **extra):
        return sesiones_pendientes(self.docente, ahora=AHORA, **extra)

    # --- Programadas ---

    def test_una_sesion_programada_pasada_sin_registros_es_pendiente(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        self.assertEqual(self.pendientes(), [sesion])

    def test_una_sesion_programada_futura_no_es_pendiente(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 21))

        self.assertEqual(self.pendientes(), [])

    def test_una_sesion_de_hoy_cuya_hora_de_fin_ya_paso_es_pendiente(self):
        sesion = crear_sesion(self.grupo, fecha=HOY, inicio=time(15, 0), fin=time(17, 0))

        self.assertEqual(self.pendientes(), [sesion])

    def test_una_sesion_de_hoy_que_todavia_no_termina_no_es_pendiente(self):
        crear_sesion(self.grupo, fecha=HOY, inicio=time(17, 0), fin=time(19, 0))

        self.assertEqual(self.pendientes(), [])

    def test_justo_a_la_hora_de_fin_la_sesion_ya_cuenta_como_pasada(self):
        sesion = crear_sesion(self.grupo, fecha=HOY, inicio=time(16, 0), fin=time(18, 0))

        self.assertEqual(self.pendientes(), [sesion])

    def test_un_minuto_antes_de_la_hora_de_fin_todavia_no(self):
        crear_sesion(self.grupo, fecha=HOY, inicio=time(16, 0), fin=time(18, 1))

        self.assertEqual(self.pendientes(), [])

    # --- Realizadas ---

    def test_una_sesion_realizada_con_todos_registrados_no_es_pendiente(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos, self.docente)

        self.assertEqual(self.pendientes(), [])

    def test_una_sesion_realizada_con_inscritos_sin_registro_es_pendiente(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:2], self.docente)   # falta uno

        self.assertEqual(self.pendientes(), [sesion])

    def test_un_inscrito_dado_de_alta_despues_de_la_sesion_no_la_deja_incompleta(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:2], self.docente)
        Inscripcion.objects.filter(
            grupo=self.grupo, alumno=self.alumnos[2]).update(fecha_alta=date(2026, 10, 20))

        self.assertEqual(self.pendientes(), [])

    def test_un_inscrito_dado_de_alta_el_mismo_dia_de_la_sesion_si_cuenta(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:2], self.docente)
        Inscripcion.objects.filter(
            grupo=self.grupo, alumno=self.alumnos[2]).update(fecha_alta=date(2026, 10, 19))

        self.assertEqual(self.pendientes(), [sesion])

    def test_un_alumno_dado_de_baja_no_deja_incompleta_la_sesion(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:2], self.docente)
        # El tercero se dio de baja sin haber tenido registro en la sesión.
        Inscripcion.objects.filter(grupo=self.grupo, alumno=self.alumnos[2]).delete()

        self.assertEqual(self.pendientes(), [])

    def test_un_registro_de_un_alumno_dado_de_baja_no_cuenta_como_faltante(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos, self.docente)
        Inscripcion.objects.filter(grupo=self.grupo, alumno=self.alumnos[0]).delete()

        self.assertEqual(self.pendientes(), [])

    # --- Otros casos ---

    def test_una_sesion_cancelada_nunca_es_pendiente(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=CANCELADA)

        self.assertEqual(self.pendientes(), [])

    def test_solo_cuentan_las_sesiones_del_docente(self):
        otro = crear_docente('otro@asistencia.test', 'otro')
        ajena = crear_sesion(crear_grupo(otro, clave='AJENO-1'), fecha=date(2026, 10, 19))
        propia = crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        self.assertEqual(self.pendientes(), [propia])
        self.assertEqual(sesiones_pendientes(otro, ahora=AHORA), [ajena])

    def test_se_puede_limitar_a_un_grupo(self):
        otro_grupo = crear_grupo(self.docente, clave='BD-201')
        crear_sesion(otro_grupo, fecha=date(2026, 10, 19))
        propia = crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        self.assertEqual(self.pendientes(grupo=self.grupo), [propia])

    def test_van_de_la_mas_antigua_a_la_mas_reciente(self):
        recientes = [crear_sesion(self.grupo, fecha=date(2026, 10, d)) for d in (19, 7, 13)]

        self.assertEqual(
            [s.fecha.day for s in self.pendientes()], [7, 13, 19])
        self.assertEqual(len(recientes), 3)

    def test_la_hora_se_mide_en_la_zona_de_tijuana_no_en_utc(self):
        # Sesión del 19/10 que termina a las 20:00 hora de Tijuana.
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), inicio=time(18, 0), fin=time(20, 0))

        # 02:00 UTC del 20/10 son las 19:00 del 19/10 en Tijuana: aún no termina.
        antes = datetime(2026, 10, 20, 2, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(sesiones_pendientes(self.docente, ahora=antes), [])
        # 05:00 UTC son las 22:00 en Tijuana: ya terminó.
        despues = datetime(2026, 10, 20, 5, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(sesiones_pendientes(self.docente, ahora=despues), [sesion])

    def test_es_una_sola_consulta_sin_importar_cuantas_sesiones_haya(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                sesiones_pendientes(self.docente, ahora=AHORA)
            return len(capturadas)

        crear_sesion(self.grupo, fecha=date(2026, 10, 1))
        una = consultas()
        for dia in range(2, 20):
            crear_sesion(self.grupo, fecha=date(2026, 10, dia))
        muchas = consultas()

        self.assertEqual(len(sesiones_pendientes(self.docente, ahora=AHORA)), 19)
        self.assertEqual((una, muchas), (1, 1))


class AlertaDePendientesTests(TestCase):

    def setUp(self):
        self.docente = crear_docente()
        self.grupo = crear_grupo(self.docente)
        self.alumnos = inscribir_alumnos(self.grupo, 4)
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def get(self, nombre, *args):
        with hora_fija():
            return self.client.get(reverse(nombre, args=args))

    def test_sin_pendientes_no_hay_alerta(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 21))   # futura

        for respuesta in (self.get('grupos'), self.get('grupo_detalle', self.grupo.pk)):
            self.assertNotContains(respuesta, 'id="pendientes"')

    def test_la_pagina_de_grupos_avisa_de_una_sesion_sin_pase_de_lista(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        respuesta = self.get('grupos')

        self.assertContains(respuesta, 'id="pendientes"')
        self.assertContains(respuesta, '1 sesión necesita atención')
        self.assertContains(respuesta, reverse('pase_de_lista', args=[sesion.pk]))
        self.assertContains(respuesta, 'ADM-101 · Lunes 19/10/2026')
        self.assertContains(respuesta, 'sin pase de lista')

    def test_avisa_de_una_sesion_realizada_con_el_pase_incompleto(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:3], self.docente)

        respuesta = self.get('grupos')

        self.assertContains(respuesta, 'pase de lista incompleto')
        self.assertContains(respuesta, reverse('pase_de_lista', args=[sesion.pk]))

    def test_la_pagina_del_grupo_solo_avisa_de_ese_grupo(self):
        otro = crear_grupo(self.docente, clave='BD-201')
        crear_sesion(otro, fecha=date(2026, 10, 18))
        propia = crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        respuesta = self.get('grupo_detalle', self.grupo.pk)

        self.assertContains(respuesta, '1 sesión necesita atención')
        self.assertContains(respuesta, reverse('pase_de_lista', args=[propia.pk]))
        self.assertNotContains(respuesta, 'BD-201 ·')
        # La de todos los grupos sí aparece en la página de grupos.
        self.assertContains(self.get('grupos'), '2 sesiones necesitan atención')

    def test_una_sesion_cancelada_no_genera_alerta(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=CANCELADA)

        self.assertNotContains(self.get('grupos'), 'id="pendientes"')

    def test_al_guardar_el_pase_de_lista_la_alerta_desaparece(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19))
        self.assertContains(self.get('grupos'), 'id="pendientes"')

        with hora_fija():
            self.client.post(
                reverse('pase_de_lista', args=[sesion.pk]),
                datos_del_pase('captura', {a.pk: 'presente' for a in self.alumnos}))

        self.assertNotContains(self.get('grupos'), 'id="pendientes"')

    def test_completar_un_pase_incompleto_quita_la_alerta(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 19), estado=REALIZADA)
        registrar(sesion, self.alumnos[:3], self.docente)
        self.assertContains(self.get('grupos'), 'pase de lista incompleto')

        with hora_fija():
            self.client.post(
                reverse('pase_de_lista', args=[sesion.pk]),
                datos_del_pase('correccion', {a.pk: 'presente' for a in self.alumnos}))

        self.assertNotContains(self.get('grupos'), 'id="pendientes"')

    def test_con_muchas_pendientes_muestra_diez_y_cuenta_el_resto(self):
        for dia in range(1, 16):   # 15 sesiones pendientes
            crear_sesion(self.grupo, fecha=date(2026, 10, dia))

        respuesta = self.get('grupos')

        self.assertContains(respuesta, '15 sesiones necesitan atención')
        self.assertContains(respuesta, 'Y 5 más')
        # Diez enlaces a sesiones; el de «Ver todas» apunta a la página de pase de lista.
        self.assertContains(respuesta, 'class="alert-link" href="/sesiones/', count=10)
        self.assertContains(respuesta, reverse('pase_de_lista_inicio'))
        # Las más antiguas primero: el 1 sí, el 15 queda en «Ver todas».
        self.assertContains(respuesta, '01/10/2026')
        self.assertNotContains(respuesta, '15/10/2026')

    def test_la_alerta_no_hace_una_consulta_por_sesion(self):
        def consultas(nombre, *args):
            with CaptureQueriesContext(connection) as capturadas:
                self.get(nombre, *args)
            return len(capturadas)

        crear_sesion(self.grupo, fecha=date(2026, 10, 1))
        crear_sesion(self.grupo, fecha=date(2026, 10, 2))
        pocas = (consultas('grupos'), consultas('grupo_detalle', self.grupo.pk))
        for dia in range(3, 20):
            crear_sesion(self.grupo, fecha=date(2026, 10, dia))
        muchas = (consultas('grupos'), consultas('grupo_detalle', self.grupo.pk))

        self.assertEqual(pocas, muchas)


class PaginaDelPaseDeListaTests(TestCase):
    """«Pase de lista» del menú: sesiones de hoy y pendientes de días anteriores."""

    def setUp(self):
        self.docente = crear_docente()
        self.grupo = crear_grupo(self.docente)
        self.alumnos = inscribir_alumnos(self.grupo, 3)
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def get(self):
        with hora_fija():
            return self.client.get(reverse('pase_de_lista_inicio'))

    def test_lista_las_sesiones_de_hoy_cada_una_con_su_boton(self):
        sesion = crear_sesion(self.grupo, fecha=HOY, inicio=time(19, 0), fin=time(21, 0))
        manana = crear_sesion(self.grupo, fecha=date(2026, 10, 21))

        respuesta = self.get()

        self.assertContains(respuesta, reverse('pase_de_lista', args=[sesion.pk]))
        self.assertNotContains(respuesta, reverse('pase_de_lista', args=[manana.pk]))
        self.assertContains(respuesta, 'Martes 20/10/2026')

    def test_sin_sesiones_lo_dice(self):
        respuesta = self.get()

        self.assertContains(respuesta, 'No tienes sesiones programadas para hoy.')
        self.assertContains(respuesta, 'No tienes sesiones pendientes de días anteriores.')

    def test_las_pendientes_de_dias_anteriores_traen_su_boton(self):
        vieja = crear_sesion(self.grupo, fecha=date(2026, 10, 15))
        incompleta = crear_sesion(self.grupo, fecha=date(2026, 10, 16), estado=REALIZADA)
        registrar(incompleta, self.alumnos[:2], self.docente)

        respuesta = self.get()

        self.assertEqual(
            [s.pk for s in respuesta.context['pendientes']], [vieja.pk, incompleta.pk])
        self.assertContains(respuesta, reverse('pase_de_lista', args=[vieja.pk]))
        self.assertContains(respuesta, 'pase de lista incompleto')
        self.assertContains(respuesta, 'Completar')

    def test_una_sesion_de_hoy_que_ya_termino_se_marca_y_no_se_repite_en_pendientes(self):
        de_hoy = crear_sesion(self.grupo, fecha=HOY, inicio=time(8, 0), fin=time(10, 0))

        respuesta = self.get()

        self.assertContains(respuesta, 'Sin pase de lista')
        self.assertEqual(respuesta.context['pendientes'], [])
        self.assertContains(respuesta, reverse('pase_de_lista', args=[de_hoy.pk]), count=1)

    def test_una_sesion_de_hoy_ya_realizada_y_completa_no_se_marca(self):
        de_hoy = crear_sesion(
            self.grupo, fecha=HOY, inicio=time(8, 0), fin=time(10, 0), estado=REALIZADA)
        registrar(de_hoy, self.alumnos, self.docente)

        respuesta = self.get()

        self.assertContains(respuesta, 'Realizada')
        self.assertNotContains(respuesta, 'Incompleta')
        self.assertNotContains(respuesta, 'Sin pase de lista')

    def test_no_muestra_las_sesiones_de_otro_docente(self):
        otro = crear_docente('otro@asistencia.test', 'otro')
        ajena = crear_sesion(crear_grupo(otro, clave='AJENO-1'), fecha=date(2026, 10, 15))

        respuesta = self.get()

        self.assertNotContains(respuesta, reverse('pase_de_lista', args=[ajena.pk]))
