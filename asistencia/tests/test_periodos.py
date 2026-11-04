"""Periodos escolares (RF-17): modelo, activar y desactivar, y la copia de los que ya existían."""

import importlib
from datetime import date

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from asistencia.models import Periodo
from asistencia.services.periodos import (
    ErrorDePeriodo, PeriodoCerrado, activar_periodo, asegurar_periodo_abierto,
    desactivar_periodo, grupos_del_periodo, periodo_activo, periodo_cerrado,
)

from .utils import crear_docente, crear_grupo, crear_periodo, crear_sesion

INICIO = date(2026, 8, 24)
FIN = date(2026, 12, 4)


class PeriodoModeloTests(TestCase):

    def test_la_clave_debe_tener_el_formato_aaaa_n(self):
        for clave in ('2026-1', '2026-2', '2027-3'):
            with self.subTest(clave):
                Periodo(clave=clave, fecha_inicio=INICIO, fecha_fin=FIN).full_clean()
        for clave in ('2026', '26-1', '2026-12', 'verano', '2026-a', ''):
            with self.subTest(clave):
                with self.assertRaises(ValidationError) as error:
                    Periodo(clave=clave, fecha_inicio=INICIO, fecha_fin=FIN).full_clean()
                self.assertIn('clave', error.exception.message_dict)

    def test_la_clave_no_se_repite(self):
        crear_periodo('2026-2')
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_periodo('2026-2')

    def test_el_fin_debe_ser_posterior_al_inicio_incluso_en_la_base_de_datos(self):
        for fin in (INICIO, date(2026, 8, 1)):
            with self.subTest(fin=fin):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    crear_periodo('2026-2', fin=fin)

    def test_la_base_de_datos_no_deja_dos_periodos_activos(self):
        crear_periodo('2026-1', activo=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_periodo('2026-2', activo=True)
        self.assertEqual(Periodo.objects.filter(activo=True).count(), 1)

    def test_pueden_convivir_muchos_periodos_inactivos(self):
        for clave in ('2025-1', '2025-2', '2026-1', '2026-2'):
            crear_periodo(clave)
        self.assertEqual(Periodo.objects.filter(activo=False).count(), 4)

    def test_se_ordenan_del_mas_reciente_al_mas_antiguo(self):
        for clave in ('2026-1', '2027-1', '2026-2'):
            crear_periodo(clave)
        self.assertEqual([p.clave for p in Periodo.objects.all()], ['2027-1', '2026-2', '2026-1'])


class ActivarYDesactivarTests(TestCase):

    def test_activar_un_periodo_lo_deja_activo(self):
        periodo = crear_periodo('2026-2')

        anterior = activar_periodo(periodo)

        self.assertIsNone(anterior)
        periodo.refresh_from_db()
        self.assertTrue(periodo.activo)
        self.assertEqual(periodo_activo(), periodo)

    def test_activar_otro_desactiva_el_que_estaba_activo(self):
        viejo = crear_periodo('2026-1', activo=True)
        nuevo = crear_periodo('2026-2')

        anterior = activar_periodo(nuevo)

        self.assertEqual(anterior, viejo)
        viejo.refresh_from_db(), nuevo.refresh_from_db()
        self.assertFalse(viejo.activo)
        self.assertTrue(nuevo.activo)
        self.assertEqual(Periodo.objects.filter(activo=True).count(), 1)

    def test_activar_el_que_ya_esta_activo_no_cambia_nada(self):
        periodo = crear_periodo('2026-2', activo=True)
        otro = crear_periodo('2026-1')

        self.assertIsNone(activar_periodo(periodo))

        self.assertEqual(list(Periodo.objects.filter(activo=True)), [periodo])
        otro.refresh_from_db()
        self.assertFalse(otro.activo)

    def test_desactivar_deja_el_periodo_inactivo_y_se_puede_repetir(self):
        periodo = crear_periodo('2026-2', activo=True)

        desactivar_periodo(periodo)
        desactivar_periodo(periodo)

        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)
        self.assertIsNone(periodo_activo())

    def test_una_secuencia_de_cambios_nunca_deja_dos_activos(self):
        periodos = [crear_periodo(clave) for clave in ('2026-1', '2026-2', '2027-1')]
        for indice in (0, 1, 2, 0, 2, 1, 1):
            activar_periodo(periodos[indice])
            self.assertEqual(Periodo.objects.filter(activo=True).count(), 1)
            self.assertEqual(periodo_activo(), periodos[indice])

    def test_un_periodo_borrado_no_se_puede_activar_ni_desactivar(self):
        periodo = crear_periodo('2026-2')
        periodo.delete()
        with self.assertRaises(ErrorDePeriodo):
            activar_periodo(periodo)
        with self.assertRaises(ErrorDePeriodo):
            desactivar_periodo(periodo)


class PeriodoCerradoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()

    def test_un_periodo_inactivo_esta_cerrado(self):
        crear_periodo('2026-1')
        self.assertTrue(periodo_cerrado('2026-1'))

    def test_un_periodo_activo_esta_abierto(self):
        crear_periodo('2026-2', activo=True)
        self.assertFalse(periodo_cerrado('2026-2'))

    def test_una_clave_sin_fila_no_se_congela(self):
        # Un grupo con un periodo que no existe en la tabla sigue funcionando.
        self.assertFalse(periodo_cerrado('2020-1'))

    def test_el_grupo_de_un_periodo_inactivo_no_pasa_la_comprobacion(self):
        crear_periodo('2026-1')
        grupo = crear_grupo(self.docente, periodo='2026-1')
        with self.assertRaises(PeriodoCerrado) as error:
            asegurar_periodo_abierto(grupo)
        self.assertIn('2026-1', str(error.exception))
        self.assertIn('solo lectura', str(error.exception))

    def test_el_grupo_de_un_periodo_activo_pasa_la_comprobacion(self):
        crear_periodo('2026-2', activo=True)
        asegurar_periodo_abierto(crear_grupo(self.docente, periodo='2026-2'))

    def test_desactivar_congela_y_activar_descongela_a_los_grupos(self):
        periodo = crear_periodo('2026-2', activo=True)
        grupo = crear_grupo(self.docente, periodo='2026-2')

        desactivar_periodo(periodo)
        with self.assertRaises(PeriodoCerrado):
            asegurar_periodo_abierto(grupo)

        activar_periodo(periodo)
        asegurar_periodo_abierto(grupo)

    def test_cuenta_los_grupos_que_usan_la_clave(self):
        crear_grupo(self.docente, clave='A', periodo='2026-2')
        crear_grupo(self.docente, clave='B', periodo='2026-2')
        crear_grupo(self.docente, clave='C', periodo='2026-1')
        self.assertEqual(grupos_del_periodo('2026-2'), 2)
        self.assertEqual(grupos_del_periodo('2030-1'), 0)


class CopiaDeLosPeriodosExistentesTests(TestCase):
    """La migración 0003 crea una fila por cada periodo que ya usaban los grupos."""

    @classmethod
    def setUpTestData(cls):
        cls.copiar = importlib.import_module(
            'asistencia.migrations.0003_periodo').copiar_periodos_de_los_grupos
        cls.docente = crear_docente()

    def test_toma_las_fechas_de_las_sesiones_y_activa_solo_el_mas_reciente(self):
        anterior = crear_grupo(self.docente, clave='A', periodo='2026-1')
        crear_sesion(anterior, fecha=date(2026, 2, 3))
        crear_sesion(anterior, fecha=date(2026, 5, 28))
        actual = crear_grupo(self.docente, clave='B', periodo='2026-2')
        crear_sesion(actual, fecha=date(2026, 8, 25))
        crear_sesion(actual, fecha=date(2026, 12, 3))

        self.copiar(apps, None)

        antes, ahora = Periodo.objects.get(clave='2026-1'), Periodo.objects.get(clave='2026-2')
        self.assertEqual((antes.fecha_inicio, antes.fecha_fin), (date(2026, 2, 3), date(2026, 5, 28)))
        self.assertEqual((ahora.fecha_inicio, ahora.fecha_fin), (date(2026, 8, 25), date(2026, 12, 3)))
        self.assertEqual(list(Periodo.objects.filter(activo=True)), [ahora])
        self.assertFalse(antes.activo)

    def test_sin_sesiones_usa_las_fechas_tipicas_del_semestre(self):
        crear_grupo(self.docente, clave='A', periodo='2027-1')
        crear_grupo(self.docente, clave='B', periodo='2027-2')

        self.copiar(apps, None)

        primavera, otono = Periodo.objects.get(clave='2027-1'), Periodo.objects.get(clave='2027-2')
        self.assertEqual((primavera.fecha_inicio, primavera.fecha_fin), (date(2027, 1, 26), date(2027, 6, 12)))
        self.assertEqual((otono.fecha_inicio, otono.fecha_fin), (date(2027, 8, 17), date(2027, 12, 11)))

    def test_una_clave_con_otro_formato_tambien_se_copia(self):
        crear_grupo(self.docente, clave='A', periodo='Verano 26')

        self.copiar(apps, None)

        periodo = Periodo.objects.get(clave='Verano 26')
        self.assertLess(periodo.fecha_inicio, periodo.fecha_fin)
        self.assertTrue(periodo.activo)

    def test_varios_grupos_del_mismo_periodo_dan_una_sola_fila(self):
        crear_grupo(self.docente, clave='A', periodo='2026-2')
        crear_grupo(self.docente, clave='B', periodo='2026-2')

        self.copiar(apps, None)

        self.assertEqual(Periodo.objects.count(), 1)

    def test_sin_grupos_no_crea_periodos(self):
        self.copiar(apps, None)
        self.assertEqual(Periodo.objects.count(), 0)
