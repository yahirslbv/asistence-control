"""El periodo de un grupo sale de los periodos del administrador (RF-17), no de un texto libre."""

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from asistencia.forms import GrupoForm
from asistencia.models import Grupo, Periodo
from asistencia.services.periodos import activar_periodo, periodo_activo

from .utils import PASSWORD, crear_docente, crear_grupo, crear_periodo


def datos(**cambios):
    return {'clave': 'ADM-101', 'materia': 'Administración de Proyectos', 'periodo': '2026-2', **cambios}


class FormularioDeGrupoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_ofrece_solo_el_periodo_activo(self):
        crear_periodo('2026-1')
        crear_periodo('2026-2', activo=True)
        crear_periodo('2027-1')

        formulario = GrupoForm()

        self.assertEqual(formulario.fields['periodo'].choices, [('2026-2', '2026-2')])
        self.assertFalse(formulario.sin_periodo_activo)

    def test_la_pantalla_de_alta_muestra_una_lista_con_el_periodo_activo(self):
        crear_periodo('2026-2', activo=True)

        respuesta = self.client.get(reverse('grupo_crear'))

        self.assertContains(respuesta, '<select')
        self.assertContains(respuesta, '<option value="2026-2">2026-2</option>', html=True)
        self.assertContains(respuesta, 'Solo se pueden crear grupos en el periodo activo.')
        self.assertNotContains(respuesta, 'id="aviso-sin-periodo"')

    def test_un_grupo_nuevo_se_crea_en_el_periodo_activo(self):
        crear_periodo('2026-2', activo=True)

        respuesta = self.client.post(reverse('grupo_crear'), datos())

        grupo = Grupo.objects.get()
        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]))
        self.assertEqual(grupo.periodo, '2026-2')

    def test_no_se_crea_un_grupo_en_un_periodo_inactivo_aunque_se_mande_a_mano(self):
        crear_periodo('2026-1')
        crear_periodo('2026-2', activo=True)

        respuesta = self.client.post(reverse('grupo_crear'), datos(periodo='2026-1'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ese periodo no está activo')
        self.assertEqual(Grupo.objects.count(), 0)

    def test_no_se_crea_un_grupo_en_un_periodo_que_no_existe(self):
        crear_periodo('2026-2', activo=True)

        respuesta = self.client.post(reverse('grupo_crear'), datos(periodo='2099-9'))

        self.assertContains(respuesta, 'Ese periodo no está activo')
        self.assertEqual(Grupo.objects.count(), 0)

    def test_sin_periodo_activo_se_avisa_y_no_se_puede_crear(self):
        crear_periodo('2026-1')

        pantalla = self.client.get(reverse('grupo_crear'))
        envio = self.client.post(reverse('grupo_crear'), datos(periodo='2026-1'))

        self.assertContains(pantalla, 'id="aviso-sin-periodo"')
        self.assertContains(pantalla, 'No hay un periodo activo')
        self.assertRegex(pantalla.content.decode(), r'<button type="submit" class="btn btn-primary"\s+disabled')
        self.assertEqual(envio.status_code, 200)
        self.assertEqual(Grupo.objects.count(), 0)

    def test_al_cambiar_el_periodo_activo_cambia_lo_que_se_ofrece(self):
        viejo = crear_periodo('2026-2', activo=True)
        nuevo = crear_periodo('2027-1')

        activar_periodo(nuevo)

        self.assertEqual(GrupoForm().fields['periodo'].choices, [('2027-1', '2027-1')])
        viejo.refresh_from_db()
        self.assertFalse(viejo.activo)
        self.assertEqual(periodo_activo(), nuevo)

    def test_al_editar_se_conserva_el_periodo_que_el_grupo_ya_tiene(self):
        crear_periodo('2027-1', activo=True)
        grupo = crear_grupo(self.docente, periodo='2026-2')   # un periodo que ya no es el activo

        formulario = GrupoForm(instance=grupo)

        self.assertEqual(
            formulario.fields['periodo'].choices, [('2027-1', '2027-1'), ('2026-2', '2026-2')])

    def test_editar_un_grupo_del_periodo_activo_deja_el_periodo_y_guarda(self):
        crear_periodo('2026-2', activo=True)
        grupo = crear_grupo(self.docente)

        respuesta = self.client.post(
            reverse('grupo_editar', args=[grupo.pk]), datos(materia='Otra materia'))

        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]))
        grupo.refresh_from_db()
        self.assertEqual((grupo.materia, grupo.periodo), ('Otra materia', '2026-2'))

    def test_la_clave_sigue_siendo_unica_por_periodo(self):
        crear_periodo('2026-2', activo=True)
        crear_grupo(self.docente)

        respuesta = self.client.post(reverse('grupo_crear'), datos())

        self.assertContains(respuesta, 'Ya existe un grupo con esa clave en ese periodo.')


class SeedDemoYPeriodosTests(TestCase):

    def test_deja_el_periodo_de_la_demo_creado_y_activo(self):
        call_command('seed_demo', verbosity=0)

        periodo = Periodo.objects.get()
        self.assertEqual(periodo.clave, '2026-2')
        self.assertTrue(periodo.activo)
        self.assertLess(periodo.fecha_inicio, periodo.fecha_fin)

    def test_es_repetible(self):
        call_command('seed_demo', verbosity=0)
        call_command('seed_demo', verbosity=0)

        self.assertEqual(Periodo.objects.count(), 1)
        self.assertEqual(Periodo.objects.filter(activo=True).count(), 1)

    def test_no_le_quita_el_lugar_a_un_periodo_que_el_administrador_ya_activo(self):
        otro = crear_periodo('2027-1', activo=True)

        call_command('seed_demo', verbosity=0)

        self.assertEqual(periodo_activo(), otro)
        demo = Periodo.objects.get(clave='2026-2')
        self.assertFalse(demo.activo)
