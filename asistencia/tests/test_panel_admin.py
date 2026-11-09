"""Panel del administrador (RF-20) y aprobación de cuentas desde él (RF-19).

El administrador entra a su panel; ahí aprueba o rechaza cuentas, ve el periodo activo y
algunas cifras, y llega al admin de Django para gestionar usuarios y periodos. No ve los
grupos de los docentes, y un docente no entra al panel (403).
"""

from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Usuario
from asistencia.services.registro import registrar_docente
from asistencia.services.resumen import resumen_del_administrador

from .utils import (
    AHORA, PASSWORD, RelojFijoMixin, crear_administrador, crear_docente, crear_grupo,
    crear_periodo, crear_sesion, inscribir_alumnos,
)

CLAVE = 'Cuaderno-Verde-2026'


def registrar(nombre='Marta', apellido='Quintero', correo='marta.quintero@uabc.edu.mx'):
    return registrar_docente(nombre=nombre, apellido=apellido, correo=correo, contrasena=CLAVE)


class PanelBase(RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.administrador = crear_administrador()
        cls.docente = crear_docente()

    def entrar_como(self, usuario):
        self.client.login(username=usuario.email, password=PASSWORD)


class AccesoAlPanelTests(PanelBase):

    def rutas(self):
        cuenta = registrar()
        return {
            'panel': ('get', reverse('panel_admin')),
            'aprobar': ('post', reverse('cuenta_aprobar', args=[cuenta.pk])),
            'rechazar (confirmación)': ('get', reverse('cuenta_rechazar', args=[cuenta.pk])),
            'rechazar': ('post', reverse('cuenta_rechazar', args=[cuenta.pk])),
        }, cuenta

    def test_un_anonimo_va_al_inicio_de_sesion_y_no_cambia_nada(self):
        rutas, cuenta = self.rutas()

        for nombre, (metodo, url) in rutas.items():
            with self.subTest(nombre):
                respuesta = getattr(self.client, metodo)(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.aprobado)
        self.assertTrue(cuenta.is_active)

    def test_un_docente_recibe_403_y_no_puede_aprobar_ni_rechazar(self):
        rutas, cuenta = self.rutas()
        self.entrar_como(self.docente)

        for nombre, (metodo, url) in rutas.items():
            with self.subTest(nombre):
                self.assertEqual(getattr(self.client, metodo)(url).status_code, 403)
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.aprobado)
        self.assertTrue(cuenta.is_active)

    def test_un_superusuario_con_rol_docente_tambien_recibe_403(self):
        # createsuperuser crea el rol docente (README): el panel es solo para el rol administrador.
        superusuario = Usuario.objects.create_superuser(
            username='root', email='root@asistencia.test', password=PASSWORD)
        self.entrar_como(superusuario)

        self.assertEqual(self.client.get(reverse('panel_admin')).status_code, 403)

    def test_el_administrador_entra(self):
        self.entrar_como(self.administrador)

        self.assertEqual(self.client.get(reverse('panel_admin')).status_code, 200)

    def test_el_inicio_lleva_al_administrador_a_su_panel_y_al_docente_a_su_inicio(self):
        self.entrar_como(self.administrador)
        self.assertRedirects(
            self.client.get(reverse('inicio')), reverse('panel_admin'), fetch_redirect_response=False)

        self.client.logout()
        self.entrar_como(self.docente)
        self.assertEqual(self.client.get(reverse('inicio')).status_code, 200)

    def test_aprobar_solo_acepta_post(self):
        cuenta = registrar()
        self.entrar_como(self.administrador)

        respuesta = self.client.get(reverse('cuenta_aprobar', args=[cuenta.pk]))

        self.assertEqual(respuesta.status_code, 405)
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.aprobado)


class ContenidoDelPanelTests(PanelBase):

    def setUp(self):
        self.entrar_como(self.administrador)
        self.url = reverse('panel_admin')

    def test_lista_las_cuentas_pendientes_con_sus_botones(self):
        marta = registrar()
        beto = registrar('Beto', 'Salas', 'beto.salas@uabc.edu.mx')

        respuesta = self.client.get(self.url)

        for cuenta in (marta, beto):
            self.assertContains(respuesta, cuenta.email)
            self.assertContains(respuesta, cuenta.get_full_name())
            self.assertContains(respuesta, f'action="{reverse("cuenta_aprobar", args=[cuenta.pk])}"')
            self.assertContains(respuesta, f'href="{reverse("cuenta_rechazar", args=[cuenta.pk])}"')
        self.assertEqual(len(respuesta.context['cuentas']), 2)
        self.assertContains(respuesta, '2 cuentas esperan tu aprobación.')

    def test_sin_pendientes_lo_dice_y_no_muestra_botones(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Todo al día')
        self.assertContains(respuesta, 'No hay cuentas esperando aprobación.')
        self.assertNotContains(respuesta, 'Aprobar</button>')

    def test_una_sola_cuenta_se_anuncia_en_singular(self):
        registrar()

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '1 cuenta espera tu aprobación.')

    def test_las_cuentas_normales_y_las_rechazadas_no_aparecen_en_la_lista(self):
        rechazada = registrar('Rita', 'Rojas', 'rita.rojas@uabc.edu.mx')
        Usuario.objects.filter(pk=rechazada.pk).update(is_active=False)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['cuentas'], [])
        self.assertNotContains(respuesta, 'rita.rojas@uabc.edu.mx')
        self.assertNotContains(respuesta, self.docente.email)

    def test_muestra_el_periodo_activo_con_su_numero_de_grupos(self):
        crear_periodo('2026-2', activo=True, inicio=date(2026, 8, 24), fin=date(2026, 12, 4))
        crear_grupo(self.docente, clave='ADM-101')
        crear_grupo(self.docente, clave='BD-201')

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'El periodo activo es 2026-2.')
        self.assertContains(respuesta, 'Del 24/08/2026 al 04/12/2026')
        self.assertContains(respuesta, '2 grupos')

    def test_sin_periodo_activo_avisa_y_enlaza_a_los_periodos(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'No hay un periodo activo.')
        self.assertContains(respuesta, 'Activa o crea un periodo.')

    def test_enlaza_al_admin_de_usuarios_y_periodos_sin_reconstruirlos(self):
        respuesta = self.client.get(self.url)

        for nombre in ('admin:asistencia_usuario_changelist', 'admin:asistencia_usuario_add',
                       'admin:asistencia_periodo_changelist'):
            with self.subTest(nombre):
                self.assertContains(respuesta, f'href="{reverse(nombre)}"')

    def test_no_muestra_los_grupos_ni_los_alumnos_de_los_docentes(self):
        crear_periodo('2026-2', activo=True)
        grupo = crear_grupo(self.docente, clave='SECRETO-99', materia='MateriaSecretaXYZ')
        alumnos = inscribir_alumnos(grupo, 2)
        crear_sesion(grupo)

        respuesta = self.client.get(self.url).content.decode()

        for texto in ('SECRETO-99', 'MateriaSecretaXYZ', alumnos[0].nombre, alumnos[0].matricula):
            self.assertNotIn(texto, respuesta)

    def test_el_administrador_sigue_sin_acceso_a_las_pantallas_de_los_docentes(self):
        grupo = crear_grupo(self.docente)

        for url in (reverse('grupos'), reverse('grupo_detalle', args=[grupo.pk])):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_la_navegacion_del_administrador_lleva_al_panel_usuarios_y_periodos(self):
        respuesta = self.client.get(self.url)

        for nombre, texto in (('panel_admin', 'Panel'),
                              ('admin:asistencia_usuario_changelist', 'Usuarios'),
                              ('admin:asistencia_periodo_changelist', 'Periodos')):
            with self.subTest(nombre):
                self.assertRegex(
                    respuesta.content.decode(),
                    rf'class="nav-link[^"]*"[^>]*href="{reverse(nombre)}"><svg[^>]*><use[^>]*/></svg>{texto}</a>')

    def test_la_seccion_activa_del_menu_es_el_panel(self):
        respuesta = self.client.get(self.url)

        self.assertRegex(
            respuesta.content.decode(),
            rf'class="nav-link active"\s+aria-current="page"\s+href="{reverse("panel_admin")}"')

    def test_cuesta_las_mismas_consultas_con_una_cuenta_que_con_diez(self):
        registrar('Ana', 'Uno', 'ana.uno@uabc.edu.mx')
        self.client.get(self.url)                       # calienta cachés (tipos de contenido, permisos)
        with CaptureQueriesContext(connection) as una:
            self.client.get(self.url)
        for i in range(9):
            registrar('Persona', f'Número{i}', f'persona{i}@uabc.edu.mx')
        with CaptureQueriesContext(connection) as diez:
            self.client.get(self.url)

        self.assertEqual(len(una), len(diez))


class AprobarYRechazarDesdeElPanelTests(PanelBase):

    def setUp(self):
        self.entrar_como(self.administrador)
        self.cuenta = registrar()

    def test_aprobar_deja_entrar_a_la_cuenta_y_avisa(self):
        respuesta = self.client.post(
            reverse('cuenta_aprobar', args=[self.cuenta.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('panel_admin'))
        self.assertContains(respuesta, 'Cuenta de Marta Quintero aprobada: ya puede iniciar sesión.')
        self.cuenta.refresh_from_db()
        self.assertTrue(self.cuenta.aprobado)
        self.assertEqual(respuesta.context['cuentas'], [])
        # Y la persona ya puede entrar, como docente.
        otro = self.client_class()
        self.assertTrue(otro.login(username=self.cuenta.email, password=CLAVE))
        self.assertEqual(otro.get(reverse('inicio')).status_code, 200)

    def test_rechazar_pide_confirmacion_antes_de_cambiar_algo(self):
        respuesta = self.client.get(reverse('cuenta_rechazar', args=[self.cuenta.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.cuenta.email)
        self.assertContains(respuesta, 'Sí, rechazar la cuenta')
        self.cuenta.refresh_from_db()
        self.assertTrue(self.cuenta.is_active)

    def test_rechazar_desactiva_la_cuenta_y_avisa(self):
        respuesta = self.client.post(
            reverse('cuenta_rechazar', args=[self.cuenta.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('panel_admin'))
        self.assertContains(respuesta, 'Cuenta de Marta Quintero rechazada: quedó desactivada.')
        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.is_active)
        self.assertFalse(self.cuenta.aprobado)
        self.assertEqual(Usuario.objects.filter(pk=self.cuenta.pk).count(), 1)   # no se borra
        self.assertFalse(self.client_class().login(username=self.cuenta.email, password=CLAVE))

    def test_una_cuenta_que_ya_no_esta_pendiente_avisa_en_vez_de_fallar(self):
        self.client.post(reverse('cuenta_aprobar', args=[self.cuenta.pk]))

        for nombre, metodo in (('cuenta_aprobar', 'post'), ('cuenta_rechazar', 'post'),
                               ('cuenta_rechazar', 'get')):
            with self.subTest(f'{nombre} {metodo}'):
                respuesta = getattr(self.client, metodo)(
                    reverse(nombre, args=[self.cuenta.pk]), follow=True)
                self.assertRedirects(respuesta, reverse('panel_admin'))
                self.assertContains(respuesta, 'Esa cuenta ya no está esperando aprobación.')
        self.cuenta.refresh_from_db()
        self.assertTrue(self.cuenta.aprobado)
        self.assertTrue(self.cuenta.is_active)

    def test_una_cuenta_que_no_existe_tambien_avisa(self):
        respuesta = self.client.post(reverse('cuenta_aprobar', args=[999999]), follow=True)

        self.assertContains(respuesta, 'Esa cuenta ya no está esperando aprobación.')

    def test_no_se_puede_aprobar_ni_rechazar_a_un_docente_que_ya_trabaja(self):
        for nombre in ('cuenta_aprobar', 'cuenta_rechazar'):
            with self.subTest(nombre):
                self.client.post(reverse(nombre, args=[self.docente.pk]))

                self.docente.refresh_from_db()
                self.assertTrue(self.docente.is_active)
                self.assertTrue(self.docente.aprobado)

    def test_el_envio_exige_el_token_de_seguridad(self):
        cliente = self.client_class(enforce_csrf_checks=True)
        cliente.login(username=self.administrador.email, password=PASSWORD)

        respuesta = cliente.post(reverse('cuenta_aprobar', args=[self.cuenta.pk]))

        self.assertEqual(respuesta.status_code, 403)
        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.aprobado)


class ResumenDelAdministradorTests(RelojFijoMixin, TestCase):

    def resumen(self):
        return resumen_del_administrador(ahora=AHORA)

    def test_sin_datos_todo_es_cero_y_no_hay_periodo(self):
        resumen = self.resumen()

        self.assertEqual(
            (resumen.pendientes, resumen.docentes, resumen.administradores,
             resumen.desactivados, resumen.grupos_del_periodo, resumen.periodos), (0,) * 6)
        self.assertIsNone(resumen.periodo)
        self.assertEqual(resumen.saludo, 'Buenas tardes')       # AHORA son las 18:00
        self.assertEqual(resumen.hoy, AHORA.date())

    def test_cuenta_cada_tipo_de_cuenta_por_separado(self):
        crear_administrador()
        crear_docente()
        crear_docente('otra@asistencia.test', 'otra')
        registrar()                                              # pendiente: no es docente activo todavía
        baja = crear_docente('baja@asistencia.test', 'baja')
        Usuario.objects.filter(pk=baja.pk).update(is_active=False)

        resumen = self.resumen()

        self.assertEqual(resumen.administradores, 1)
        self.assertEqual(resumen.docentes, 2)
        self.assertEqual(resumen.pendientes, 1)
        self.assertEqual(resumen.desactivados, 1)

    def test_el_periodo_activo_y_sus_grupos(self):
        docente = crear_docente()
        crear_periodo('2026-1', activo=False)
        activo = crear_periodo('2026-2', activo=True)
        crear_grupo(docente, clave='ADM-101', periodo='2026-2')
        crear_grupo(docente, clave='BD-201', periodo='2026-2')
        crear_grupo(docente, clave='ADM-090', periodo='2026-1')

        resumen = self.resumen()

        self.assertEqual(resumen.periodo, activo)
        self.assertEqual(resumen.grupos_del_periodo, 2)
        self.assertEqual(resumen.periodos, 2)


class FlujoDeAltaTests(PanelBase):
    """De «no tengo cuenta» a trabajar como docente, pasando por la aprobación."""

    def test_registro_aprobacion_y_primer_grupo(self):
        crear_periodo('2026-2', activo=True)
        cliente = self.client_class()

        # 1. Se registra desde la pantalla de acceso.
        self.assertContains(cliente.get(reverse('login')), 'regístrate aquí</a>')
        cliente.post(reverse('registro'), {
            'nombre': 'Marta', 'apellido': 'Quintero', 'correo': 'marta.quintero@uabc.edu.mx',
            'contrasena': CLAVE, 'confirmacion': CLAVE})

        # 2. Todavía no puede entrar.
        respuesta = cliente.post(reverse('login'), {
            'username': 'marta.quintero@uabc.edu.mx', 'password': CLAVE})
        self.assertContains(respuesta, 'pendiente de aprobación')

        # 3. El administrador la ve en su panel y la aprueba.
        self.entrar_como(self.administrador)
        cuenta = Usuario.objects.get(email='marta.quintero@uabc.edu.mx')
        self.assertContains(self.client.get(reverse('panel_admin')), 'marta.quintero@uabc.edu.mx')
        self.client.post(reverse('cuenta_aprobar', args=[cuenta.pk]))

        # 4. Ahora entra como docente y crea su primer grupo.
        respuesta = cliente.post(reverse('login'), {
            'username': 'marta.quintero@uabc.edu.mx', 'password': CLAVE}, follow=True)
        self.assertContains(respuesta, 'Buenas')              # el saludo del inicio del docente
        respuesta = cliente.post(reverse('grupo_crear'), {
            'clave': 'ADM-101', 'materia': 'Administración de Proyectos', 'periodo': '2026-2'},
            follow=True)
        self.assertContains(respuesta, 'ADM-101')
        self.assertEqual(cuenta.grupos.count(), 1)
        # Y no entra a las pantallas del administrador.
        self.assertEqual(cliente.get(reverse('panel_admin')).status_code, 403)


class RegistroDeAccionesTests(PanelBase):

    def test_aprobar_y_rechazar_quedan_en_el_registro_de_acciones_del_admin(self):
        from django.contrib.admin.models import LogEntry
        aprobada = registrar()
        rechazada = registrar('Rita', 'Rojas', 'rita.rojas@uabc.edu.mx')
        self.entrar_como(self.administrador)

        self.client.post(reverse('cuenta_aprobar', args=[aprobada.pk]))
        self.client.post(reverse('cuenta_rechazar', args=[rechazada.pk]))

        tipo = ContentType.objects.get_for_model(Usuario)
        entradas = {e.object_id: e for e in LogEntry.objects.filter(content_type=tipo)}
        self.assertEqual(entradas[str(aprobada.pk)].user, self.administrador)
        self.assertIn('aprobada', entradas[str(aprobada.pk)].change_message)
        self.assertEqual(entradas[str(rechazada.pk)].user, self.administrador)
        self.assertIn('rechazada', entradas[str(rechazada.pk)].change_message)
