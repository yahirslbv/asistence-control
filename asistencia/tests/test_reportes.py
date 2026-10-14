"""Pruebas de los reportes de asistencia (RF-13 y RF-14)."""

import re
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, Inscripcion, Sesion
from asistencia.services.asistencia import registrar_pase_de_lista
from asistencia.services.reportes import (
    esta_bajo_el_minimo, periodos_del_docente, porcentaje_truncado,
    reporte_del_alumno, reporte_del_grupo, reporte_del_periodo,
    tabla_del_alumno, tabla_del_grupo, texto_de_porcentaje,
)

from .escenarios import EscenarioFijo
from .utils import (
    PASSWORD, RelojFijoMixin, celdas_de_la_tabla, crear_administrador,
    crear_docente, crear_grupo, crear_sesion, inscribir_alumnos,
)

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO
REALIZADA = Sesion.Estado.REALIZADA


class PorcentajeTruncadoTests(SimpleTestCase):
    """Las funciones puras del cálculo, sin base de datos."""

    def test_tres_de_cuatro_es_75(self):
        self.assertEqual(porcentaje_truncado(3, 4), Decimal('75.0'))
        self.assertEqual(texto_de_porcentaje(porcentaje_truncado(3, 4)), '75.0 %')

    def test_el_porcentaje_se_trunca_no_se_redondea(self):
        casos = [
            (1999, 2500, '79.9'),   # 79.96: no debe verse como 80.0
            (2, 3, '66.6'),         # 66.666...: redondeado sería 66.7
            (1, 3, '33.3'),
            (7, 9, '77.7'),
            (79, 100, '79.0'),
            (4, 4, '100.0'),
            (0, 5, '0.0'),
        ]
        for asistencias, registros, esperado in casos:
            with self.subTest(f'{asistencias}/{registros}'):
                self.assertEqual(porcentaje_truncado(asistencias, registros), Decimal(esperado))

    def test_el_resultado_es_decimal_con_un_decimal_nunca_float(self):
        for asistencias, registros in [(3, 4), (1, 3), (4, 4), (0, 7)]:
            resultado = porcentaje_truncado(asistencias, registros)
            self.assertIsInstance(resultado, Decimal)
            self.assertEqual(resultado.as_tuple().exponent, -1)

    def test_sin_registros_no_hay_porcentaje_ni_marca(self):
        self.assertIsNone(porcentaje_truncado(0, 0))
        self.assertEqual(texto_de_porcentaje(None), 'Sin registros')
        self.assertFalse(esta_bajo_el_minimo(0, 0, 80))

    @override_settings(ASISTENCIA_MINIMA=80)
    def test_1999_de_2500_se_muestra_79_9_y_queda_marcado(self):
        self.assertEqual(porcentaje_truncado(1999, 2500), Decimal('79.9'))
        self.assertTrue(esta_bajo_el_minimo(1999, 2500))

    def test_marca_solo_si_es_estrictamente_menor_al_minimo(self):
        self.assertTrue(esta_bajo_el_minimo(79, 100, 80))
        self.assertFalse(esta_bajo_el_minimo(80, 100, 80))     # justo en el mínimo
        self.assertFalse(esta_bajo_el_minimo(81, 100, 80))
        self.assertTrue(esta_bajo_el_minimo(3, 4, 80))         # 75 < 80
        self.assertFalse(esta_bajo_el_minimo(3, 4, 75))        # 75 no es menor que 75
        self.assertTrue(esta_bajo_el_minimo(3, 4, 76))

    def test_la_marca_no_depende_del_redondeo_ni_del_truncado(self):
        # 79.96 % se ve como 79.9 y está bajo el mínimo; 2/3 se ve como 66.6.
        self.assertTrue(esta_bajo_el_minimo(1999, 2500, 80))
        self.assertTrue(esta_bajo_el_minimo(2, 3, 67))
        self.assertFalse(esta_bajo_el_minimo(2, 3, 66))

    def test_el_minimo_se_lee_de_la_configuracion_al_usarlo(self):
        with override_settings(ASISTENCIA_MINIMA=70):
            self.assertFalse(esta_bajo_el_minimo(3, 4))
        with override_settings(ASISTENCIA_MINIMA=90):
            self.assertTrue(esta_bajo_el_minimo(3, 4))


class ReporteDelGrupoTests(EscenarioFijo):

    def test_el_escenario_fijo_da_75_100_y_sin_registros(self):
        reporte = reporte_del_grupo(self.grupo)

        self.assertEqual([f.alumno for f in reporte.filas], [self.a, self.b, self.c])
        a, b, c = (self.fila(reporte, x) for x in (self.a, self.b, self.c))

        self.assertEqual((a.registros, a.presentes, a.retardos, a.ausentes, a.justificados),
                         (4, 1, 1, 1, 1))
        self.assertEqual(a.asistencias, 3)
        self.assertEqual(a.porcentaje, Decimal('75.0'))
        self.assertTrue(a.bajo_el_minimo)

        self.assertEqual((b.registros, b.presentes, b.asistencias), (4, 4, 4))
        self.assertEqual(b.porcentaje, Decimal('100.0'))
        self.assertFalse(b.bajo_el_minimo)

        self.assertEqual(c.registros, 0)
        self.assertIsNone(c.porcentaje)
        self.assertEqual(c.porcentaje_texto, 'Sin registros')
        self.assertFalse(c.bajo_el_minimo)          # sin registros no se marca
        self.assertEqual(c.situacion, '—')

    def test_los_textos_de_cada_situacion(self):
        reporte = reporte_del_grupo(self.grupo)

        self.assertEqual(self.fila(reporte, self.a).porcentaje_texto, '75.0 %')
        self.assertEqual(self.fila(reporte, self.a).situacion, 'Bajo el mínimo')
        self.assertEqual(self.fila(reporte, self.b).situacion, 'Cumple')

    def test_el_porcentaje_del_grupo_es_el_ponderado(self):
        reporte = reporte_del_grupo(self.grupo)

        # (3 + 4) asistencias de (4 + 4) registros; no el promedio de 75 y 100.
        self.assertEqual((reporte.asistencias, reporte.registros), (7, 8))
        self.assertEqual(reporte.porcentaje, Decimal('87.5'))
        self.assertEqual(reporte.alumnos_bajo_el_minimo, 1)
        self.assertEqual(reporte.sesiones_realizadas, 4)

    def test_solo_cuentan_las_sesiones_realizadas(self):
        reporte = reporte_del_grupo(self.grupo)

        # B tiene dos «ausente» más, en una sesión programada y en una cancelada.
        self.assertEqual(Asistencia.objects.filter(alumno=self.b).count(), 6)
        self.assertEqual(self.fila(reporte, self.b).registros, 4)
        self.assertEqual(self.fila(reporte, self.b).ausentes, 0)

    def test_los_registros_de_un_alumno_dado_de_baja_no_entran_al_grupo(self):
        reporte = reporte_del_grupo(self.grupo)

        self.assertNotIn(self.d, [f.alumno for f in reporte.filas])
        self.assertEqual(reporte.registros, 8)            # no 10: sin los 2 de D
        self.assertEqual(Asistencia.objects.filter(alumno=self.d).count(), 2)
        nombres = [fila[1] for fila in tabla_del_grupo(reporte).filas]
        self.assertNotIn('Dani Díaz', nombres)

    def test_si_el_alumno_vuelve_a_inscribirse_vuelve_al_reporte(self):
        Inscripcion.objects.create(grupo=self.grupo, alumno=self.d, fecha_alta=date(2026, 10, 1))

        reporte = reporte_del_grupo(self.grupo)

        d = self.fila(reporte, self.d)
        self.assertEqual((d.registros, d.asistencias, d.porcentaje), (2, 0, Decimal('0.0')))
        self.assertTrue(d.bajo_el_minimo)
        self.assertEqual(reporte.registros, 10)

    def test_los_justificados_y_los_retardos_cuentan_como_asistencia(self):
        a = self.fila(reporte_del_grupo(self.grupo), self.a)

        self.assertEqual(a.asistencias, a.presentes + a.retardos + a.justificados)
        self.assertEqual(a.registros, a.asistencias + a.ausentes)

    def test_un_alumno_con_registros_solo_ausentes_tiene_0_y_se_marca(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 11), estado=REALIZADA)
        self.registrar(sesion, self.a, AUSENTE)
        Asistencia.objects.filter(alumno=self.a).exclude(sesion=sesion).delete()

        a = self.fila(reporte_del_grupo(self.grupo), self.a)

        self.assertEqual((a.registros, a.asistencias, a.porcentaje), (1, 0, Decimal('0.0')))
        self.assertTrue(a.bajo_el_minimo)

    def test_ordena_por_nombre(self):
        reporte = reporte_del_grupo(self.grupo)

        nombres = [f.alumno.nombre for f in reporte.filas]
        self.assertEqual(nombres, sorted(nombres))


class MinimoDeAsistenciaTests(EscenarioFijo):

    def test_cambiar_el_minimo_cambia_quien_queda_marcado(self):
        casos = [(70, False), (74, False), (75, False), (76, True), (80, True), (100, True)]
        for minimo, a_marcado in casos:
            with self.subTest(minimo=minimo), override_settings(ASISTENCIA_MINIMA=minimo):
                reporte = reporte_del_grupo(self.grupo)
                self.assertEqual(self.fila(reporte, self.a).bajo_el_minimo, a_marcado)
                self.assertEqual(reporte.minimo, minimo)

    def test_con_el_minimo_al_100_b_cumple_y_c_sigue_sin_marca(self):
        with override_settings(ASISTENCIA_MINIMA=100):
            reporte = reporte_del_grupo(self.grupo)

        self.assertFalse(self.fila(reporte, self.b).bajo_el_minimo)   # 100 no es < 100
        self.assertFalse(self.fila(reporte, self.c).bajo_el_minimo)   # sin registros

    def test_el_porcentaje_truncado_no_oculta_la_marca(self):
        # 2 de 3 se ve 66.6 %; con mínimo 67 está bajo, con 66 no.
        alumno = Alumno.objects.create(matricula='1000009', nombre='Zeta Zamora')
        Inscripcion.objects.create(grupo=self.grupo, alumno=alumno, fecha_alta=date(2026, 10, 1))
        for sesion, estado in zip(self.sesiones[:3], (PRESENTE, PRESENTE, AUSENTE)):
            self.registrar(sesion, alumno, estado)

        with override_settings(ASISTENCIA_MINIMA=67):
            fila = self.fila(reporte_del_grupo(self.grupo), alumno)
            self.assertEqual(fila.porcentaje_texto, '66.6 %')
            self.assertTrue(fila.bajo_el_minimo)
        with override_settings(ASISTENCIA_MINIMA=66):
            self.assertFalse(self.fila(reporte_del_grupo(self.grupo), alumno).bajo_el_minimo)

    def test_el_minimo_se_ve_en_la_pantalla_y_en_la_tabla(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        with override_settings(ASISTENCIA_MINIMA=70):
            respuesta = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))
            tabla = tabla_del_grupo(reporte_del_grupo(self.grupo))

        self.assertContains(respuesta, 'Mínimo de asistencia: 70 %')
        self.assertIn('Mínimo de asistencia: 70 %', tabla.subtitulo)
        # Con 70 ya nadie está bajo el mínimo: ninguna fila se resalta.
        self.assertNotContains(respuesta, 'table-danger')
        self.assertEqual(tabla.marcadas, frozenset())


class AvisoDePendientesTests(EscenarioFijo):

    def aviso(self):
        return reporte_del_grupo(self.grupo).aviso

    def test_sin_sesiones_pendientes_no_hay_aviso(self):
        self.assertIsNone(self.aviso())
        self.assertFalse(
            any('sin pase de lista' in n for n in tabla_del_grupo(reporte_del_grupo(self.grupo)).notas))

    def test_una_sesion_pasada_sin_pase_de_lista_activa_el_aviso(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 18))

        self.assertIn('Hay 1 sesión sin pase de lista o con el pase incompleto', self.aviso())

    def test_el_aviso_cuenta_varias_en_plural(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 18))
        crear_sesion(self.grupo, fecha=date(2026, 10, 19))

        self.assertIn('Hay 2 sesiones sin pase de lista', self.aviso())

    def test_el_aviso_desaparece_al_cancelar_la_sesion(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 18))
        self.assertIsNotNone(self.aviso())

        Sesion.objects.filter(pk=sesion.pk).update(estado=Sesion.Estado.CANCELADA)

        self.assertIsNone(self.aviso())

    def test_el_aviso_desaparece_al_tomar_lista(self):
        sesion = crear_sesion(self.grupo, fecha=date(2026, 10, 18))
        self.assertIsNotNone(self.aviso())

        registrar_pase_de_lista(
            sesion.pk, {self.a.pk: PRESENTE, self.b.pk: PRESENTE, self.c.pk: PRESENTE}, self.docente)

        self.assertIsNone(self.aviso())

    def test_una_sesion_realizada_incompleta_tambien_activa_el_aviso(self):
        nuevo = Alumno.objects.create(matricula='1000010', nombre='Nora Núñez')
        Inscripcion.objects.create(grupo=self.grupo, alumno=nuevo, fecha_alta=date(2026, 10, 1))

        self.assertIn('Hay 4 sesiones', self.aviso())   # falta registrar a Nora en las 4

    def test_una_sesion_futura_no_activa_el_aviso(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 25))

        self.assertIsNone(self.aviso())

    def test_las_sesiones_pendientes_de_otro_grupo_no_cuentan(self):
        otro = crear_grupo(self.docente, clave='OTRO-1')
        crear_sesion(otro, fecha=date(2026, 10, 18))

        self.assertIsNone(self.aviso())

    def test_el_aviso_sale_en_la_pantalla_del_grupo_y_del_alumno_y_en_las_notas(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 18))
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        grupo = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))
        alumno = self.client.get(reverse('reporte_alumno', args=[self.grupo.pk, self.a.pk]))

        for respuesta in (grupo, alumno):
            self.assertContains(respuesta, 'id="aviso-pendientes"')
            self.assertContains(respuesta, 'el porcentaje no la incluye por completo')
        notas = tabla_del_grupo(reporte_del_grupo(self.grupo)).notas
        self.assertTrue(any('no la incluye por completo' in n for n in notas))

    def test_sin_pendientes_la_pantalla_no_muestra_el_aviso(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))

        self.assertNotContains(respuesta, 'aviso-pendientes')


class DosGruposDelMismoDocenteTests(RelojFijoMixin, TestCase):
    """Un alumno inscrito en dos grupos del mismo docente: los conteos no se mezclan."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.g1 = crear_grupo(cls.docente, clave='G-1')
        cls.g2 = crear_grupo(cls.docente, clave='G-2')
        cls.x = Alumno.objects.create(matricula='2000001', nombre='Xavier Ximenez')
        for grupo in (cls.g1, cls.g2):
            Inscripcion.objects.create(grupo=grupo, alumno=cls.x, fecha_alta=date(2026, 10, 1))
        for grupo, estado, cantidad in ((cls.g1, PRESENTE, 3), (cls.g2, AUSENTE, 2)):
            for dia in range(cantidad):
                sesion = crear_sesion(grupo, fecha=date(2026, 10, 10 + dia), estado=REALIZADA)
                Asistencia.objects.create(
                    sesion=sesion, alumno=cls.x, estado=estado, registrado_por=cls.docente)

    def test_cada_grupo_cuenta_solo_lo_suyo(self):
        r1, r2 = reporte_del_grupo(self.g1), reporte_del_grupo(self.g2)

        f1, f2 = r1.filas[0], r2.filas[0]
        self.assertEqual((f1.registros, f1.presentes, f1.ausentes, f1.porcentaje),
                         (3, 3, 0, Decimal('100.0')))
        self.assertEqual((f2.registros, f2.presentes, f2.ausentes, f2.porcentaje),
                         (2, 0, 2, Decimal('0.0')))
        self.assertEqual((r1.registros, r2.registros), (3, 2))
        self.assertEqual((r1.alumnos_bajo_el_minimo, r2.alumnos_bajo_el_minimo), (0, 1))

    def test_el_reporte_del_alumno_es_por_grupo(self):
        ra1 = reporte_del_alumno(self.g1, self.x)
        ra2 = reporte_del_alumno(self.g2, self.x)

        self.assertEqual((len(ra1.sesiones), ra1.fila.registros), (3, 3))
        self.assertEqual((len(ra2.sesiones), ra2.fila.registros), (2, 2))
        self.assertTrue(all(s.estado == PRESENTE for s in ra1.sesiones))
        self.assertTrue(all(s.estado == AUSENTE for s in ra2.sesiones))

    def test_el_resumen_del_periodo_tampoco_los_mezcla(self):
        resumen = {r.grupo.clave: r for r in reporte_del_periodo(self.docente, '2026-2').resumenes}

        self.assertEqual((resumen['G-1'].registros, resumen['G-1'].porcentaje_texto), (3, '100.0 %'))
        self.assertEqual((resumen['G-2'].registros, resumen['G-2'].porcentaje_texto), (2, '0.0 %'))
        self.assertEqual((resumen['G-1'].alumnos_bajo_el_minimo, resumen['G-2'].alumnos_bajo_el_minimo), (0, 1))


class ConsultasDelReporteTests(RelojFijoMixin, TestCase):
    """Número fijo de consultas, sin importar cuántos alumnos ni sesiones haya."""

    def setUp(self):
        self.docente = crear_docente()

    def grupo_con(self, alumnos, sesiones, clave, primera_matricula):
        grupo = crear_grupo(self.docente, clave=clave)
        lista = inscribir_alumnos(grupo, alumnos, primera_matricula=primera_matricula)
        registros = []
        for dia in range(sesiones):
            sesion = crear_sesion(grupo, fecha=date(2026, 10, 1 + dia), estado=REALIZADA)
            registros += [
                Asistencia(sesion=sesion, alumno=a,
                           estado=AUSENTE if (i + dia) % 7 == 0 else PRESENTE,
                           registrado_por=self.docente)
                for i, a in enumerate(lista)
            ]
        Asistencia.objects.bulk_create(registros)
        return grupo

    def test_el_reporte_de_un_grupo_de_50_alumnos_hace_cuatro_consultas(self):
        chico = self.grupo_con(5, 3, 'CH-1', 4000000)
        grande = self.grupo_con(50, 10, 'GR-1', 4100000)

        with self.assertNumQueries(4):   # alumnos, conteos, sesiones realizadas, pendientes
            reporte_del_grupo(chico)
        with self.assertNumQueries(4):
            reporte = reporte_del_grupo(grande)

        self.assertEqual(len(reporte.filas), 50)
        self.assertEqual(reporte.registros, 500)

    def test_la_pantalla_del_grupo_no_depende_del_numero_de_alumnos(self):
        chico = self.grupo_con(5, 3, 'CH-2', 4200000)
        grande = self.grupo_con(50, 10, 'GR-2', 4300000)
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        def consultas(grupo):
            with CaptureQueriesContext(connection) as capturadas:
                self.client.get(reverse('reporte_grupo', args=[grupo.pk]))
            return len(capturadas)

        self.assertEqual(consultas(chico), consultas(grande))
        self.assertLessEqual(consultas(grande), 10)

    def test_el_reporte_del_alumno_hace_un_numero_fijo_de_consultas(self):
        poca = self.grupo_con(5, 3, 'CH-3', 4400000)
        mucha = self.grupo_con(50, 30, 'GR-3', 4500000)
        alumno_poca = Alumno.objects.get(matricula='4400000')
        alumno_mucha = Alumno.objects.get(matricula='4500000')

        with self.assertNumQueries(3):   # sesiones realizadas, registros del alumno, pendientes
            reporte_del_alumno(poca, alumno_poca)
        with self.assertNumQueries(3):
            reporte = reporte_del_alumno(mucha, alumno_mucha)

        self.assertEqual(len(reporte.sesiones), 30)

    def test_el_resumen_del_periodo_hace_tres_consultas_con_uno_o_con_muchos_grupos(self):
        self.grupo_con(5, 3, 'P-1', 4600000)
        with self.assertNumQueries(3):   # grupos, inscripciones, conteos
            reporte_del_periodo(self.docente, '2026-2')
        for i in range(2, 9):
            self.grupo_con(5, 3, f'P-{i}', 4600000 + i * 100)
        with self.assertNumQueries(3):
            reporte = reporte_del_periodo(self.docente, '2026-2')

        self.assertEqual(len(reporte.resumenes), 8)


class ReporteDelPeriodoTests(RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.otro = crear_docente('otro@asistencia.test', 'otro')
        cls.g1 = crear_grupo(cls.docente, clave='A-101', periodo='2026-2')
        cls.g2 = crear_grupo(cls.docente, clave='B-202', periodo='2026-2')
        cls.viejo = crear_grupo(cls.docente, clave='C-303', periodo='2026-1')
        cls.ajeno = crear_grupo(cls.otro, clave='X-999', periodo='2026-2')
        # g1: 2 alumnos, uno al 75 % (bajo) y otro al 100 %.
        cls.alumnos = inscribir_alumnos(cls.g1, 2, primera_matricula=5000000)
        for dia, (e0, e1) in enumerate([(PRESENTE, PRESENTE), (RETARDO, PRESENTE),
                                        (AUSENTE, PRESENTE), (JUSTIFICADO, PRESENTE)]):
            sesion = crear_sesion(cls.g1, fecha=date(2026, 10, 12 + dia), estado=REALIZADA)
            for alumno, estado in zip(cls.alumnos, (e0, e1)):
                Asistencia.objects.create(
                    sesion=sesion, alumno=alumno, estado=estado, registrado_por=cls.docente)
        inscribir_alumnos(cls.g2, 3, primera_matricula=5100000)   # sin registros

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_los_periodos_van_del_mas_reciente_al_mas_antiguo(self):
        self.assertEqual(periodos_del_docente(self.docente), ['2026-2', '2026-1'])
        self.assertEqual(periodos_del_docente(self.otro), ['2026-2'])

    def test_por_defecto_muestra_el_periodo_mas_reciente_con_sus_grupos(self):
        respuesta = self.client.get(reverse('reportes'))

        self.assertEqual(respuesta.context['periodo'], '2026-2')
        self.assertEqual([r.grupo.clave for r in respuesta.context['reporte'].resumenes],
                         ['A-101', 'B-202'])
        self.assertNotContains(respuesta, 'C-303')      # otro periodo
        self.assertNotContains(respuesta, 'X-999')      # grupo de otro docente

    def test_la_tabla_trae_porcentaje_ponderado_alumnos_bajo_el_minimo_y_enlace(self):
        respuesta = self.client.get(reverse('reportes'))

        celdas = celdas_de_la_tabla(respuesta.content, 'tabla-periodo')
        self.assertEqual(celdas['filas'][0][:5], ['A-101', 'Administración de Proyectos', '2', '87.5 %', '1'])
        self.assertEqual(celdas['filas'][1][:5], ['B-202', 'Administración de Proyectos', '3', 'Sin registros', '0'])
        self.assertContains(respuesta, reverse('reporte_grupo', args=[self.g1.pk]))
        self.assertContains(respuesta, reverse('reporte_grupo', args=[self.g2.pk]))

    def test_el_selector_lista_los_periodos_y_cambia_el_resultado(self):
        respuesta = self.client.get(reverse('reportes'), {'periodo': '2026-1'})

        self.assertContains(respuesta, '<option value="2026-1" selected>')
        self.assertContains(respuesta, '<option value="2026-2" >')
        self.assertEqual([r.grupo.clave for r in respuesta.context['reporte'].resumenes], ['C-303'])

    def test_un_periodo_ajeno_o_mal_escrito_cae_en_el_mas_reciente(self):
        for valor in ('2099-9', '<script>', ''):
            with self.subTest(valor=valor):
                respuesta = self.client.get(reverse('reportes'), {'periodo': valor})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context['periodo'], '2026-2')

    def test_el_minimo_se_ve_en_la_pantalla_y_cambia_la_cuenta(self):
        with override_settings(ASISTENCIA_MINIMA=70):
            respuesta = self.client.get(reverse('reportes'))

        self.assertContains(respuesta, 'Mínimo de asistencia: <strong>70 %</strong>')
        self.assertEqual(respuesta.context['reporte'].resumenes[0].alumnos_bajo_el_minimo, 0)

    def test_un_alumno_dado_de_baja_no_cuenta_en_el_resumen(self):
        Inscripcion.objects.filter(grupo=self.g1, alumno=self.alumnos[0]).delete()

        resumen = reporte_del_periodo(self.docente, '2026-2').resumenes[0]

        self.assertEqual((resumen.alumnos, resumen.registros, resumen.asistencias), (1, 4, 4))
        self.assertEqual((resumen.porcentaje_texto, resumen.alumnos_bajo_el_minimo), ('100.0 %', 0))

    def test_sin_grupos_invita_a_crear_uno(self):
        sin_grupos = crear_docente('vacio@asistencia.test', 'vacio')
        self.client.logout()
        self.client.login(username='vacio@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('reportes'))

        self.assertContains(respuesta, 'Todavía no tienes grupos')
        self.assertIsNone(respuesta.context['periodo'])
        self.assertEqual(sin_grupos.grupos.count(), 0)


class PantallaDelReporteDelGrupoTests(EscenarioFijo):

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)
        self.respuesta = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))

    def test_muestra_las_columnas_y_los_numeros_del_escenario(self):
        celdas = celdas_de_la_tabla(self.respuesta.content)

        self.assertEqual(celdas['encabezado'], [
            'Matrícula', 'Nombre', 'Registros', 'Presentes', 'Retardos', 'Ausentes',
            'Justificados', 'Asistencias', 'Porcentaje', 'Situación'])
        self.assertEqual(celdas['filas'], [
            ['1000001', 'Ana Alonso', '4', '1', '1', '1', '1', '3', '75.0 %', 'Bajo el mínimo'],
            ['1000002', 'Beto Bravo', '4', '4', '0', '0', '0', '4', '100.0 %', 'Cumple'],
            ['1000003', 'Carla Cruz', '0', '0', '0', '0', '0', '0', 'Sin registros', '—'],
        ])
        self.assertEqual(celdas['pie'], [
            ['', 'Grupo (ponderado)', '8', '5', '1', '1', '1', '7', '87.5 %', '']])

    def test_la_marca_de_bajo_el_minimo_no_depende_solo_del_color(self):
        # Solo la fila de Ana se resalta, y además lleva el texto «Bajo el mínimo».
        self.assertContains(self.respuesta, 'class="table-danger"', count=1)
        self.assertContains(self.respuesta, 'Bajo el mínimo</span>', count=1)
        self.assertContains(self.respuesta, 'text-bg-danger')

    def test_un_alumno_sin_registros_dice_sin_registros_y_no_se_marca(self):
        filas = celdas_de_la_tabla(self.respuesta.content)['filas']
        carla = next(f for f in filas if f[1] == 'Carla Cruz')

        self.assertEqual(carla[8], 'Sin registros')
        self.assertNotIn('0.0 %', carla[8])
        self.assertNotEqual(carla[9], 'Bajo el mínimo')

    def test_cada_alumno_enlaza_a_su_reporte_y_el_dado_de_baja_no_sale(self):
        for alumno in (self.a, self.b, self.c):
            self.assertContains(
                self.respuesta, reverse('reporte_alumno', args=[self.grupo.pk, alumno.pk]))
        self.assertNotContains(self.respuesta, 'Dani Díaz')

    def test_resumen_del_grupo(self):
        self.assertContains(self.respuesta, '87.5 %')
        self.assertContains(self.respuesta, 'Sesiones realizadas')
        self.assertContains(self.respuesta, 'Mínimo de asistencia: 80 %')
        self.assertContains(self.respuesta, 'Alumnos bajo el mínimo: 1.')

    def test_la_tabla_se_adapta_al_telefono_ocultando_columnas_de_detalle(self):
        # En pantallas chicas (sin clase d-none) solo quedan Nombre, Porcentaje y Situación.
        html = self.respuesta.content.decode()
        encabezado = html.split('<thead>')[1].split('</thead>')[0]
        columnas = re.findall(r'<th([^>]*)>(.*?)</th>', encabezado, flags=re.S)
        visibles = [texto.strip() for atributos, texto in columnas if 'd-none' not in atributos]

        self.assertEqual(visibles, ['Nombre', 'Porcentaje', 'Situación'])

    def test_la_pagina_del_grupo_y_el_menu_enlazan_al_reporte(self):
        grupo = self.client.get(reverse('grupo_detalle', args=[self.grupo.pk]))
        inicio = self.client.get(reverse('inicio'))

        self.assertContains(grupo, reverse('reporte_grupo', args=[self.grupo.pk]))
        self.assertContains(inicio, f'href="{reverse("reportes")}"')
        self.assertNotContains(inicio, 'nav-link disabled')

    def test_un_grupo_sin_alumnos_lo_dice(self):
        vacio = crear_grupo(self.docente, clave='VACIO-1')

        respuesta = self.client.get(reverse('reporte_grupo', args=[vacio.pk]))

        self.assertContains(respuesta, 'no tiene alumnos inscritos')
        self.assertIsNone(respuesta.context['reporte'].porcentaje)


class ReporteDelAlumnoTests(EscenarioFijo):

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def get(self, alumno):
        return self.client.get(reverse('reporte_alumno', args=[self.grupo.pk, alumno.pk]))

    def test_porcentaje_y_detalle_sesion_por_sesion(self):
        respuesta = self.get(self.a)

        self.assertContains(respuesta, '75.0 %')
        self.assertContains(respuesta, 'Bajo el mínimo')
        celdas = celdas_de_la_tabla(respuesta.content)
        self.assertEqual(celdas['encabezado'], ['Fecha', 'Horario', 'Estado'])
        self.assertEqual(celdas['filas'], [
            ['12/10/2026', '08:00 – 10:00', 'Presente'],
            ['13/10/2026', '08:00 – 10:00', 'Retardo'],
            ['14/10/2026', '08:00 – 10:00', 'Ausente'],
            ['15/10/2026', '08:00 – 10:00', 'Justificado'],
        ])

    def test_el_detalle_solo_incluye_sesiones_realizadas(self):
        filas = celdas_de_la_tabla(self.get(self.b).content)['filas']

        fechas = [f[0] for f in filas]
        self.assertNotIn('16/10/2026', fechas)   # cancelada
        self.assertNotIn('17/10/2026', fechas)   # programada
        self.assertEqual(len(filas), 4)

    def test_los_mismos_numeros_que_el_reporte_del_grupo(self):
        reporte = reporte_del_alumno(self.grupo, self.a)
        en_el_grupo = next(f for f in reporte_del_grupo(self.grupo).filas if f.alumno == self.a)

        self.assertEqual(reporte.fila, en_el_grupo)

    def test_una_sesion_realizada_sin_registro_del_alumno_dice_sin_registro(self):
        crear_sesion(self.grupo, fecha=date(2026, 10, 11), estado=REALIZADA)

        filas = celdas_de_la_tabla(self.get(self.a).content)['filas']

        self.assertEqual(filas[0], ['11/10/2026', '08:00 – 10:00', 'Sin registro'])
        # ...y no cuenta como registro: sigue siendo 3 de 4.
        self.assertEqual(reporte_del_alumno(self.grupo, self.a).fila.registros, 4)

    def test_un_alumno_sin_registros_muestra_sin_registros_y_no_se_marca(self):
        respuesta = self.get(self.c)

        self.assertContains(respuesta, 'Sin registros')
        self.assertNotContains(respuesta, 'Bajo el mínimo')
        self.assertNotContains(respuesta, '0.0 %')
        self.assertFalse(respuesta.context['reporte'].fila.bajo_el_minimo)

    def test_un_alumno_dado_de_baja_responde_404_pero_conserva_sus_registros(self):
        respuesta = self.get(self.d)

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(Asistencia.objects.filter(alumno=self.d).count(), 2)
        # Sigue visible en la sesión donde tiene registro.
        sesion = self.client.get(reverse('pase_de_lista', args=[self.sesiones[0].pk]))
        self.assertIn(self.d, [f.alumno for f in sesion.context['filas']])

    def test_un_alumno_de_otro_grupo_responde_404(self):
        otro_grupo = crear_grupo(self.docente, clave='OTRO-9')
        ajeno = inscribir_alumnos(otro_grupo, 1, primera_matricula=6000000)[0]

        self.assertEqual(self.get(ajeno).status_code, 404)

    def test_el_porcentaje_del_alumno_se_calcula_con_el_minimo_configurado(self):
        with override_settings(ASISTENCIA_MINIMA=70):
            respuesta = self.get(self.a)

        self.assertNotContains(respuesta, 'Bajo el mínimo')
        self.assertContains(respuesta, 'Mínimo de asistencia: 70 %')

    def test_la_tabla_del_alumno_coincide_con_lo_que_se_ve(self):
        tabla = tabla_del_alumno(reporte_del_alumno(self.grupo, self.a))

        self.assertEqual(tabla.columnas, ['Fecha', 'Horario', 'Estado'])
        self.assertEqual(tabla.filas, celdas_de_la_tabla(self.get(self.a).content)['filas'])
        self.assertIn('Porcentaje: 75.0 % (3 de 4 registros)', tabla.subtitulo)
        self.assertIn('Bajo el mínimo', tabla.subtitulo)


class PermisosDeLosReportesTests(RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.intruso = crear_docente('intruso@asistencia.test', 'intruso')
        crear_administrador()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumno = inscribir_alumnos(cls.grupo, 1, primera_matricula=7000000)[0]

    def urls(self):
        return {
            'reportes': reverse('reportes'),
            'reporte_grupo': reverse('reporte_grupo', args=[self.grupo.pk]),
            'reporte_alumno': reverse('reporte_alumno', args=[self.grupo.pk, self.alumno.pk]),
        }

    def test_un_grupo_ajeno_responde_404(self):
        self.client.login(username='intruso@asistencia.test', password=PASSWORD)

        for nombre in ('reporte_grupo', 'reporte_alumno'):
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(self.urls()[nombre]).status_code, 404)

    def test_el_menu_de_reportes_solo_muestra_los_grupos_propios(self):
        self.client.login(username='intruso@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('reportes'))

        self.assertContains(respuesta, 'Todavía no tienes grupos')
        self.assertNotContains(respuesta, self.grupo.clave)

    def test_el_administrador_recibe_403_en_todas(self):
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

        for nombre, url in self.urls().items():
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_sin_sesion_se_redirige_al_login(self):
        for nombre, url in self.urls().items():
            with self.subTest(vista=nombre):
                self.assertRedirects(
                    self.client.get(url), f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False)

    def test_el_dueno_si_entra(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        for nombre, url in self.urls().items():
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(url).status_code, 200)
