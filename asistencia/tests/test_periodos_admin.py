"""El administrador gestiona los periodos desde el admin de Django (RF-17)."""

from datetime import date

from django.contrib.admin.models import LogEntry
from django.contrib.messages import get_messages
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Periodo, Usuario

from .utils import (
    PASSWORD, crear_administrador, crear_docente, crear_grupo, crear_periodo,
)

LISTA = reverse('admin:asistencia_periodo_changelist')
ALTA = reverse('admin:asistencia_periodo_add')
CAMBIAR_ESTADO = reverse('admin:asistencia_periodo_cambiar_estado')


def cambio(pk):
    return reverse('admin:asistencia_periodo_change', args=[pk])


def datos(**cambios):
    return {'clave': '2027-1', 'fecha_inicio': '2027-01-25', 'fecha_fin': '2027-06-11', **cambios}


class PeriodosAdminBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.administrador = crear_administrador()
        cls.docente = crear_docente()

    def setUp(self):
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]


class AccesoTests(PeriodosAdminBase):

    def test_el_administrador_ve_periodos_en_el_admin(self):
        indice = self.client.get(reverse('admin:index'))
        self.assertContains(indice, reverse('admin:asistencia_periodo_changelist'))
        self.assertContains(indice, 'Periodos')
        self.assertEqual(self.client.get(LISTA).status_code, 200)
        self.assertEqual(self.client.get(ALTA).status_code, 200)

    def test_el_superusuario_tambien(self):
        Usuario.objects.create_superuser('root', 'root@asistencia.test', PASSWORD)
        cliente = Client()
        cliente.login(username='root@asistencia.test', password=PASSWORD)
        self.assertEqual(cliente.get(LISTA).status_code, 200)

    def test_un_docente_no_entra(self):
        periodo = crear_periodo('2026-2')
        cliente = Client()
        cliente.login(username='docente@asistencia.test', password=PASSWORD)

        for respuesta in (cliente.get(LISTA), cliente.get(ALTA), cliente.get(cambio(periodo.pk)),
                          cliente.post(CAMBIAR_ESTADO, {'accion': f'activar-{periodo.pk}'})):
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn('/login/', respuesta['Location'])
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_un_docente_con_is_staff_marcado_a_mano_tampoco_entra(self):
        # El rol manda: aunque alguien le marque is_staff, un docente no gestiona periodos.
        Usuario.objects.filter(pk=self.docente.pk).update(is_staff=True)
        periodo = crear_periodo('2026-2')
        cliente = Client()
        cliente.login(username='docente@asistencia.test', password=PASSWORD)

        self.assertEqual(cliente.get(LISTA).status_code, 403)
        self.assertEqual(cliente.get(ALTA).status_code, 403)
        self.assertEqual(cliente.post(CAMBIAR_ESTADO, {'accion': f'activar-{periodo.pk}'}).status_code, 403)
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_quien_no_inicio_sesion_va_al_login(self):
        periodo = crear_periodo('2026-2')
        cliente = Client()
        for respuesta in (cliente.get(LISTA), cliente.post(CAMBIAR_ESTADO, {'accion': f'activar-{periodo.pk}'})):
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn('/login/', respuesta['Location'])
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_un_administrador_inactivo_no_entra(self):
        Usuario.objects.filter(pk=self.administrador.pk).update(is_active=False)
        cliente = Client()
        self.assertFalse(cliente.login(username='admin@asistencia.test', password=PASSWORD))

    def test_los_periodos_no_se_borran(self):
        periodo = crear_periodo('2026-2')

        pantalla = self.client.get(reverse('admin:asistencia_periodo_delete', args=[periodo.pk]))
        masivo = self.client.post(LISTA, {
            'action': 'delete_selected', '_selected_action': [periodo.pk], 'post': 'yes'})

        self.assertEqual(pantalla.status_code, 403)
        self.assertNotContains(self.client.get(LISTA), 'delete_selected')
        self.assertTrue(Periodo.objects.filter(pk=periodo.pk).exists())
        self.assertEqual(masivo.status_code, 200)


class AltaYEdicionTests(PeriodosAdminBase):

    def test_se_crea_un_periodo_inactivo(self):
        respuesta = self.client.post(ALTA, datos(_save='Guardar'))

        self.assertRedirects(respuesta, LISTA, fetch_redirect_response=False)
        periodo = Periodo.objects.get()
        self.assertEqual(
            (periodo.clave, periodo.fecha_inicio, periodo.fecha_fin, periodo.activo),
            ('2027-1', date(2027, 1, 25), date(2027, 6, 11), False))

    def test_guardar_y_activar_lo_deja_activo_y_desactiva_el_anterior(self):
        anterior = crear_periodo('2026-2', activo=True)

        self.client.post(ALTA, datos(_activar='Guardar y activar'))

        anterior.refresh_from_db()
        self.assertFalse(anterior.activo)
        self.assertEqual(list(Periodo.objects.filter(activo=True).values_list('clave', flat=True)), ['2027-1'])

    def test_los_datos_invalidos_se_rechazan_con_un_mensaje_claro(self):
        crear_periodo('2026-2')
        casos = {
            'clave sin el formato AAAA-N': (datos(clave='verano'), 'Usa el formato AAAA-N'),
            'clave repetida': (datos(clave='2026-2'), 'Ya existe un periodo con esa clave.'),
            'fin igual al inicio': (datos(fecha_fin='2027-01-25'), 'El último día debe ser posterior al primer día.'),
            'fin antes del inicio': (datos(fecha_fin='2026-12-31'), 'El último día debe ser posterior al primer día.'),
            'sin clave': (datos(clave=''), 'Este campo es obligatorio'),
            'sin fechas': (datos(fecha_inicio='', fecha_fin=''), 'Este campo es obligatorio'),
        }
        for nombre, (envio, texto) in casos.items():
            with self.subTest(nombre):
                respuesta = self.client.post(ALTA, envio)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, texto)
        self.assertEqual(Periodo.objects.count(), 1)

    def test_se_pueden_cambiar_las_fechas(self):
        periodo = crear_periodo('2026-2')

        respuesta = self.client.post(cambio(periodo.pk), datos(clave='2026-2', fecha_inicio='2026-08-31', _save='Guardar'))

        self.assertRedirects(respuesta, LISTA, fetch_redirect_response=False)
        periodo.refresh_from_db()
        self.assertEqual(periodo.fecha_inicio, date(2026, 8, 31))

    def test_la_clave_se_corrige_mientras_no_tenga_grupos(self):
        periodo = crear_periodo('2026-2')

        self.client.post(cambio(periodo.pk), datos(clave='2026-3', _save='Guardar'))

        periodo.refresh_from_db()
        self.assertEqual(periodo.clave, '2026-3')

    def test_la_clave_queda_fija_cuando_ya_tiene_grupos(self):
        periodo = crear_periodo('2026-2')
        crear_grupo(self.docente, periodo='2026-2')

        pantalla = self.client.get(cambio(periodo.pk))
        self.client.post(cambio(periodo.pk), datos(clave='2026-3', _save='Guardar'))

        self.assertContains(pantalla, 'field-clave')
        self.assertNotContains(pantalla, 'name="clave"')
        periodo.refresh_from_db()
        self.assertEqual(periodo.clave, '2026-2')

    def test_el_estado_no_se_edita_desde_el_formulario(self):
        periodo = crear_periodo('2026-2')
        self.client.post(cambio(periodo.pk), datos(clave='2026-2', activo='on', _save='Guardar'))
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_guardar_y_activar_aparece_solo_si_el_periodo_no_esta_activo(self):
        inactivo, activo = crear_periodo('2026-1'), crear_periodo('2026-2', activo=True)

        self.assertContains(self.client.get(ALTA), 'name="_activar"')
        self.assertContains(self.client.get(cambio(inactivo.pk)), 'name="_activar"')
        self.assertNotContains(self.client.get(cambio(activo.pk)), 'name="_activar"')

    def test_guardar_y_activar_al_editar(self):
        viejo = crear_periodo('2026-2', activo=True)
        nuevo = crear_periodo('2027-1')

        self.client.post(cambio(nuevo.pk), datos(_activar='Guardar y activar'))

        viejo.refresh_from_db(), nuevo.refresh_from_db()
        self.assertFalse(viejo.activo)
        self.assertTrue(nuevo.activo)


class ListaYBotonesTests(PeriodosAdminBase):

    def test_la_lista_muestra_fechas_estado_y_numero_de_grupos(self):
        crear_periodo('2026-1')
        crear_periodo('2026-2', activo=True)
        crear_grupo(self.docente, clave='A', periodo='2026-2')
        crear_grupo(self.docente, clave='B', periodo='2026-2')

        respuesta = self.client.get(LISTA)

        contenido = respuesta.content.decode()
        self.assertContains(respuesta, '24/08/2026 – 04/12/2026')
        self.assertEqual(contenido.count('etiqueta-activa'), 1)     # una etiqueta «Activo»
        self.assertEqual(contenido.count('etiqueta-inactiva'), 1)   # y una «Inactivo»
        self.assertRegex(contenido, r'field-grupos">2<')
        self.assertRegex(contenido, r'field-grupos">0<')
        # Del más reciente al más antiguo.
        self.assertLess(contenido.index('2026-2'), contenido.index('2026-1'))

    def test_cada_fila_tiene_el_boton_que_le_toca(self):
        inactivo, activo = crear_periodo('2026-1'), crear_periodo('2026-2', activo=True)

        contenido = self.client.get(LISTA).content.decode()

        self.assertIn(f'value="activar-{inactivo.pk}"', contenido)
        self.assertNotIn(f'value="desactivar-{inactivo.pk}"', contenido)
        self.assertIn(f'value="desactivar-{activo.pk}"', contenido)
        self.assertNotIn(f'value="activar-{activo.pk}"', contenido)
        self.assertIn('id="form-periodos"', contenido)
        self.assertIn(reverse('admin:asistencia_periodo_cambiar_estado'), contenido)
        self.assertEqual(contenido.count('form="form-periodos"'), 2)
        self.assertIn('confirm(', contenido)

    def test_el_numero_de_consultas_no_crece_con_los_periodos(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.client.get(LISTA)
            return len(capturadas)

        crear_periodo('2026-1')
        con_uno = consultas()
        for anio in range(2027, 2033):
            crear_periodo(f'{anio}-1')
            crear_grupo(self.docente, clave=f'G{anio}', periodo=f'{anio}-1')

        self.assertEqual(consultas(), con_uno)

    def test_activar_desactiva_el_otro_y_lo_cuenta_en_el_mensaje(self):
        viejo = crear_periodo('2026-1', activo=True)
        nuevo = crear_periodo('2026-2')
        crear_grupo(self.docente, clave='A', periodo='2026-1')
        crear_grupo(self.docente, clave='B', periodo='2026-1')

        respuesta = self.client.post(CAMBIAR_ESTADO, {'accion': f'activar-{nuevo.pk}'})

        self.assertRedirects(respuesta, LISTA, fetch_redirect_response=False)
        viejo.refresh_from_db(), nuevo.refresh_from_db()
        self.assertFalse(viejo.activo)
        self.assertTrue(nuevo.activo)
        mensaje = self.mensajes(respuesta)[0]
        self.assertIn('Periodo 2026-2 activado.', mensaje)
        self.assertIn('2026-1', mensaje)
        self.assertIn('sus 2 grupos quedan en solo lectura', mensaje)

    def test_activar_sin_otro_activo_no_menciona_a_nadie_mas(self):
        periodo = crear_periodo('2026-2')

        respuesta = self.client.post(CAMBIAR_ESTADO, {'accion': f'activar-{periodo.pk}'})

        self.assertEqual(self.mensajes(respuesta), ['Periodo 2026-2 activado.'])

    def test_desactivar_deja_el_periodo_inactivo_y_avisa_que_no_hay_activo(self):
        periodo = crear_periodo('2026-2', activo=True)
        crear_grupo(self.docente, periodo='2026-2')

        respuesta = self.client.post(CAMBIAR_ESTADO, {'accion': f'desactivar-{periodo.pk}'})

        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)
        mensaje = self.mensajes(respuesta)[0]
        self.assertIn('desactivado', mensaje)
        self.assertIn('sus 1 grupos quedan en solo lectura', mensaje)
        self.assertIn('Ya no hay un periodo activo', mensaje)

    def test_desactivar_uno_inactivo_no_dice_que_no_hay_activo_si_hay_otro(self):
        activo = crear_periodo('2026-2', activo=True)
        inactivo = crear_periodo('2026-1')

        respuesta = self.client.post(CAMBIAR_ESTADO, {'accion': f'desactivar-{inactivo.pk}'})

        self.assertNotIn('Ya no hay un periodo activo', self.mensajes(respuesta)[0])
        activo.refresh_from_db()
        self.assertTrue(activo.activo)

    def test_los_cambios_quedan_en_el_registro_de_acciones_del_admin(self):
        viejo = crear_periodo('2026-1', activo=True)
        nuevo = crear_periodo('2026-2')

        self.client.post(CAMBIAR_ESTADO, {'accion': f'activar-{nuevo.pk}'})

        textos = {(e.object_repr, e.change_message) for e in LogEntry.objects.all()}
        self.assertIn(('2026-2', 'Activado.'), textos)
        self.assertIn(('2026-1', 'Desactivado al activar 2026-2.'), textos)
        self.assertTrue(viejo.pk)

    def test_una_accion_mal_formada_responde_404_y_no_cambia_nada(self):
        periodo = crear_periodo('2026-2')
        for accion in ('', 'borrar-1', f'activar-{periodo.pk}x', 'activar-', 'activar', 'activar--1'):
            with self.subTest(accion):
                self.assertEqual(self.client.post(CAMBIAR_ESTADO, {'accion': accion}).status_code, 404)
        self.assertEqual(self.client.post(CAMBIAR_ESTADO, {}).status_code, 404)
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_un_periodo_que_ya_no_existe_avisa_sin_romper(self):
        respuesta = self.client.post(CAMBIAR_ESTADO, {'accion': 'activar-99999'})

        self.assertRedirects(respuesta, LISTA, fetch_redirect_response=False)
        self.assertEqual(self.mensajes(respuesta), ['Ese periodo ya no existe.'])

    def test_cambiar_el_estado_exige_post(self):
        periodo = crear_periodo('2026-2')
        respuesta = self.client.get(CAMBIAR_ESTADO + f'?accion=activar-{periodo.pk}')
        self.assertEqual(respuesta.status_code, 405)
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)

    def test_cambiar_el_estado_exige_el_token_csrf(self):
        periodo = crear_periodo('2026-2')
        cliente = Client(enforce_csrf_checks=True)
        cliente.login(username='admin@asistencia.test', password=PASSWORD)

        respuesta = cliente.post(CAMBIAR_ESTADO, {'accion': f'activar-{periodo.pk}'})

        self.assertEqual(respuesta.status_code, 403)
        periodo.refresh_from_db()
        self.assertFalse(periodo.activo)
