"""Registro de docentes (RF-19): dominio permitido, aprobación del administrador y rol docente.

Condiciones acordadas:
- solo se registra quien tenga correo de un dominio permitido (`REGISTRO_DOMINIOS`, por
  defecto `uabc.edu.mx`);
- la cuenta queda pendiente y no puede iniciar sesión hasta que un administrador la apruebe;
- el rol es siempre docente: el formulario no lo pregunta y no se puede forzar.
"""

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import authenticate
from django.contrib.messages import get_messages
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from asistencia.models import Usuario
from asistencia.services.registro import (
    CorreoNoPermitido, CorreoYaRegistrado, CuentaNoPendiente, aprobar_cuenta,
    cuenta_pendiente, cuentas_pendientes, dominio_permitido, registrar_docente,
    registro_abierto, rechazar_cuenta,
)

from .utils import PASSWORD, crear_administrador, crear_docente

CLAVE = 'Cuaderno-Verde-2026'
CORREO = 'marta.quintero@uabc.edu.mx'


def datos(**cambios):
    base = {'nombre': 'Marta', 'apellido': 'Quintero', 'correo': CORREO,
            'contrasena': CLAVE, 'confirmacion': CLAVE}
    base.update(cambios)
    return base


def mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


def registrar(**cambios):
    d = datos(**cambios)
    return registrar_docente(nombre=d['nombre'], apellido=d['apellido'],
                             correo=d['correo'], contrasena=d['contrasena'])


# ---------------------------------------------------------------------------
# Dominio permitido
# ---------------------------------------------------------------------------

class DominioPermitidoTests(SimpleTestCase):

    @override_settings(REGISTRO_DOMINIOS=['uabc.edu.mx'])
    def test_acepta_el_dominio_sin_importar_mayusculas_ni_espacios(self):
        for correo in ('a@uabc.edu.mx', 'Maria.Lopez@UABC.EDU.MX', '  ana@uabc.edu.mx  '):
            with self.subTest(correo):
                self.assertTrue(dominio_permitido(correo))

    @override_settings(REGISTRO_DOMINIOS=['uabc.edu.mx'])
    def test_rechaza_otros_dominios_y_los_que_solo_se_le_parecen(self):
        for correo in ('a@gmail.com', 'a@uabc.edu.mx.evil.com', 'a@evil-uabc.edu.mx',
                       'a@sub.uabc.edu.mx', 'a@uabc.edu', 'a@xuabc.edu.mx'):
            with self.subTest(correo):
                self.assertFalse(dominio_permitido(correo))

    @override_settings(REGISTRO_DOMINIOS=['uabc.edu.mx'])
    def test_rechaza_lo_que_no_tiene_forma_de_correo(self):
        for correo in ('', None, '@uabc.edu.mx', 'uabc.edu.mx', 'a@b@uabc.edu.mx', 'a@'):
            with self.subTest(correo):
                self.assertFalse(dominio_permitido(correo))

    @override_settings(REGISTRO_DOMINIOS=['uabc.edu.mx', 'ejemplo.mx'])
    def test_se_pueden_permitir_varios_dominios(self):
        self.assertTrue(dominio_permitido('a@ejemplo.mx'))
        self.assertTrue(dominio_permitido('a@uabc.edu.mx'))
        self.assertFalse(dominio_permitido('a@otro.mx'))

    @override_settings(REGISTRO_DOMINIOS=[])
    def test_sin_dominios_el_registro_esta_cerrado_y_no_deja_pasar_a_nadie(self):
        self.assertFalse(registro_abierto())
        self.assertFalse(dominio_permitido('a@uabc.edu.mx'))


# ---------------------------------------------------------------------------
# La cuenta que se crea
# ---------------------------------------------------------------------------

class RegistrarDocenteTests(TestCase):

    def test_la_cuenta_nace_de_docente_pendiente_y_sin_privilegios(self):
        usuario = registrar()

        usuario.refresh_from_db()
        self.assertEqual(usuario.rol, Usuario.Rol.DOCENTE)
        self.assertFalse(usuario.aprobado)
        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual((usuario.first_name, usuario.last_name), ('Marta', 'Quintero'))
        self.assertEqual(usuario.email, CORREO)
        self.assertEqual(usuario.username, CORREO)
        self.assertFalse(usuario.user_permissions.exists())

    def test_la_contrasena_se_guarda_cifrada(self):
        usuario = registrar()

        self.assertNotEqual(usuario.password, CLAVE)
        self.assertTrue(usuario.has_usable_password())
        self.assertTrue(usuario.check_password(CLAVE))

    def test_el_correo_se_guarda_en_minusculas_y_sin_espacios(self):
        usuario = registrar(correo='  Marta.Quintero@UABC.edu.mx ')

        self.assertEqual(usuario.email, CORREO)

    def test_un_dominio_no_permitido_no_crea_nada(self):
        with self.assertRaises(CorreoNoPermitido):
            registrar(correo='marta@gmail.com')

        self.assertFalse(Usuario.objects.filter(email='marta@gmail.com').exists())

    def test_un_correo_ya_registrado_se_rechaza_sin_importar_mayusculas(self):
        registrar()

        with self.assertRaises(CorreoYaRegistrado):
            registrar(correo=CORREO.upper())

        self.assertEqual(Usuario.objects.filter(email__iexact=CORREO).count(), 1)

    def test_el_correo_de_una_cuenta_creada_por_el_administrador_tambien_esta_en_uso(self):
        Usuario.objects.create_user(
            username='mq', email=CORREO, password=PASSWORD, rol=Usuario.Rol.DOCENTE)

        with self.assertRaises(CorreoYaRegistrado):
            registrar()

    def test_un_nombre_de_usuario_igual_al_correo_tambien_lo_ocupa(self):
        Usuario.objects.create_user(
            username=CORREO, email='otro@uabc.edu.mx', password=PASSWORD)

        with self.assertRaises(CorreoYaRegistrado):
            registrar()

    def test_las_cuentas_normales_nacen_aprobadas(self):
        # Las que ya existían y las que da de alta el administrador no esperan aprobación.
        self.assertTrue(crear_docente().aprobado)
        self.assertTrue(crear_administrador().aprobado)


# ---------------------------------------------------------------------------
# La pantalla de registro
# ---------------------------------------------------------------------------

class PantallaDeRegistroTests(TestCase):

    url = reverse('registro')

    def test_el_formulario_pide_nombre_apellido_correo_y_contrasena_pero_no_el_rol(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        for campo in ('nombre', 'apellido', 'correo', 'contrasena', 'confirmacion'):
            self.assertContains(respuesta, f'name="{campo}"')
        for ausente in ('rol', 'aprobado', 'is_staff', 'is_superuser', 'username'):
            self.assertNotContains(respuesta, f'name="{ausente}"')
        self.assertContains(respuesta, '@uabc.edu.mx')

    def test_el_formulario_muestra_las_reglas_de_contrasena(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'al menos 8 caracteres')

    def test_un_registro_valido_deja_la_cuenta_pendiente_y_manda_al_inicio_de_sesion(self):
        respuesta = self.client.post(self.url, datos())

        self.assertRedirects(respuesta, reverse('login'))
        usuario = Usuario.objects.get(email=CORREO)
        self.assertFalse(usuario.aprobado)
        self.assertEqual(usuario.rol, Usuario.Rol.DOCENTE)
        self.assertIn('pendiente de aprobación', ' '.join(mensajes(respuesta)))

    def test_el_registro_no_inicia_sesion(self):
        self.client.post(self.url, datos())

        self.assertNotIn('_auth_user_id', self.client.session)

    def test_el_envio_no_puede_forzar_el_rol_ni_la_aprobacion_ni_los_privilegios(self):
        self.client.post(self.url, datos(
            rol='administrador', aprobado='on', is_staff='on', is_superuser='on',
            is_active='on', username='otro-nombre'))

        usuario = Usuario.objects.get(email=CORREO)
        self.assertEqual(usuario.rol, Usuario.Rol.DOCENTE)
        self.assertFalse(usuario.aprobado)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.username, CORREO)

    def test_un_dominio_no_permitido_muestra_el_error_y_no_crea_la_cuenta(self):
        respuesta = self.client.post(self.url, datos(correo='marta@gmail.com'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Solo se admiten correos de @uabc.edu.mx.')
        self.assertFalse(Usuario.objects.filter(email='marta@gmail.com').exists())

    def test_un_correo_ya_registrado_muestra_el_error(self):
        registrar()

        respuesta = self.client.post(self.url, datos(correo=CORREO.upper()))

        self.assertContains(respuesta, 'Ya existe una cuenta con ese correo.')
        self.assertEqual(Usuario.objects.filter(email__iexact=CORREO).count(), 1)

    def test_las_contrasenas_deben_coincidir(self):
        respuesta = self.client.post(self.url, datos(confirmacion='Otra-Clave-2026'))

        self.assertContains(respuesta, 'Las contraseñas no coinciden.')
        self.assertFalse(Usuario.objects.filter(email=CORREO).exists())

    def test_se_aplican_las_reglas_de_contrasena_del_proyecto(self):
        casos = {
            'muy corta': 'Ab1-xyz',
            'demasiado común': 'password123',
            'solo números': '98765432101234',
            'parecida al correo': 'marta.quintero',
        }
        for nombre, clave in casos.items():
            with self.subTest(nombre):
                respuesta = self.client.post(
                    self.url, datos(contrasena=clave, confirmacion=clave))

                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(Usuario.objects.filter(email=CORREO).exists())
                self.assertTrue(respuesta.context['form'].errors.get('contrasena'))

    def test_todos_los_campos_son_obligatorios(self):
        for campo in ('nombre', 'apellido', 'correo', 'contrasena', 'confirmacion'):
            with self.subTest(campo):
                respuesta = self.client.post(self.url, datos(**{campo: ''}))

                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
                self.assertFalse(Usuario.objects.filter(email=CORREO).exists())

    def test_quien_ya_tiene_sesion_no_ve_el_registro(self):
        for usuario in (crear_docente(), crear_administrador()):
            with self.subTest(usuario.rol):
                self.client.force_login(usuario)

                self.assertRedirects(
                    self.client.get(self.url), reverse('inicio'), fetch_redirect_response=False)

    def test_el_envio_exige_el_token_de_seguridad(self):
        cliente = Client(enforce_csrf_checks=True)

        respuesta = cliente.post(self.url, datos())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Usuario.objects.filter(email=CORREO).exists())

    @override_settings(REGISTRO_DOMINIOS=[])
    def test_sin_dominios_configurados_el_registro_no_existe(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, datos()).status_code, 404)
        self.assertFalse(Usuario.objects.filter(email=CORREO).exists())

    @override_settings(REGISTRO_DOMINIOS=['uabc.edu.mx', 'ejemplo.mx'])
    def test_la_pantalla_nombra_todos_los_dominios_permitidos(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '@uabc.edu.mx')
        self.assertContains(respuesta, '@ejemplo.mx')


# ---------------------------------------------------------------------------
# Inicio de sesión con una cuenta pendiente
# ---------------------------------------------------------------------------

class InicioDeSesionConCuentaPendienteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pendiente = registrar()
        cls.url = reverse('login')

    def entrar(self, correo=CORREO, clave=CLAVE):
        return self.client.post(self.url, {'username': correo, 'password': clave})

    def test_la_pantalla_de_acceso_ofrece_registrarse(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Si no tienes cuenta,')
        self.assertContains(respuesta, f'href="{reverse("registro")}">regístrate aquí</a>')

    @override_settings(REGISTRO_DOMINIOS=[])
    def test_con_el_registro_cerrado_la_pantalla_de_acceso_no_lo_ofrece(self):
        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, 'regístrate aquí')
        self.assertNotContains(respuesta, reverse('registro'))

    def test_una_cuenta_pendiente_no_puede_entrar_y_se_le_dice_por_que(self):
        respuesta = self.entrar()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'pendiente de aprobación')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_con_la_contrasena_equivocada_el_mensaje_no_revela_que_esta_pendiente(self):
        respuesta = self.entrar(clave='Otra-Clave-2026')

        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertNotContains(respuesta, 'pendiente')

    def test_un_correo_que_no_existe_recibe_el_mismo_mensaje_que_uno_pendiente_con_mala_clave(self):
        inexistente = self.entrar(correo='nadie@uabc.edu.mx', clave='Otra-Clave-2026')
        pendiente = self.entrar(clave='Otra-Clave-2026')

        self.assertContains(inexistente, 'Correo o contraseña incorrectos.')
        self.assertEqual(
            [str(e) for e in inexistente.context['form'].non_field_errors()],
            [str(e) for e in pendiente.context['form'].non_field_errors()])

    def test_ningun_camino_autentica_a_una_cuenta_pendiente(self):
        self.assertIsNone(authenticate(username=CORREO, password=CLAVE))
        self.assertFalse(self.client.login(username=CORREO, password=CLAVE))

    def test_el_admin_de_django_tampoco_deja_entrar_a_una_cuenta_pendiente(self):
        respuesta = self.client.post('/admin/login/', {
            'username': CORREO, 'password': CLAVE, 'next': '/admin/'})

        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotEqual(respuesta.status_code, 302)

    def test_una_cuenta_rechazada_recibe_el_mensaje_generico(self):
        rechazar_cuenta(self.pendiente.pk, crear_administrador())

        respuesta = self.entrar()

        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertNotContains(respuesta, 'pendiente')

    def test_una_cuenta_aprobada_entra_y_va_a_su_pantalla(self):
        aprobar_cuenta(self.pendiente.pk, crear_administrador())

        respuesta = self.entrar()

        self.assertRedirects(respuesta, '/', fetch_redirect_response=False)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.pendiente.pk))

    def test_si_se_quita_la_aprobacion_deja_de_valer_la_sesion_abierta(self):
        docente = crear_docente()
        self.client.force_login(docente)
        self.assertEqual(self.client.get(reverse('grupos')).status_code, 200)

        Usuario.objects.filter(pk=docente.pk).update(aprobado=False)

        respuesta = self.client.get(reverse('grupos'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])


# ---------------------------------------------------------------------------
# Aprobar y rechazar (servicio)
# ---------------------------------------------------------------------------

class AprobacionDeCuentasTests(TestCase):

    def setUp(self):
        self.administrador = crear_administrador()
        self.cuenta = registrar()

    def test_cuenta_pendiente_solo_acierta_con_la_contrasena_correcta(self):
        self.assertTrue(cuenta_pendiente(CORREO, CLAVE))
        self.assertTrue(cuenta_pendiente(CORREO.upper(), CLAVE))
        self.assertFalse(cuenta_pendiente(CORREO, 'Otra-Clave-2026'))
        self.assertFalse(cuenta_pendiente('nadie@uabc.edu.mx', CLAVE))
        self.assertFalse(cuenta_pendiente('', ''))

    def test_las_pendientes_van_de_la_mas_antigua_a_la_mas_nueva_y_solo_las_activas(self):
        segunda = registrar(correo='beto@uabc.edu.mx', nombre='Beto')
        tercera = registrar(correo='carla@uabc.edu.mx', nombre='Carla')
        Usuario.objects.filter(pk=self.cuenta.pk).update(date_joined='2026-10-01T10:00:00Z')
        Usuario.objects.filter(pk=segunda.pk).update(date_joined='2026-10-02T10:00:00Z')
        Usuario.objects.filter(pk=tercera.pk).update(date_joined='2026-10-03T10:00:00Z')
        rechazar_cuenta(segunda.pk, self.administrador)

        self.assertEqual(
            [u.pk for u in cuentas_pendientes()], [self.cuenta.pk, tercera.pk])

    def test_las_cuentas_normales_no_aparecen_como_pendientes(self):
        crear_docente()

        self.assertEqual([u.pk for u in cuentas_pendientes()], [self.cuenta.pk])

    def test_aprobar_deja_la_cuenta_lista_para_entrar_y_anota_quien_lo_hizo(self):
        usuario = aprobar_cuenta(self.cuenta.pk, self.administrador)

        self.assertTrue(usuario.aprobado)
        self.cuenta.refresh_from_db()
        self.assertTrue(self.cuenta.aprobado)
        self.assertTrue(self.cuenta.is_active)
        self.assertEqual(self.cuenta.rol, Usuario.Rol.DOCENTE)
        self.assertTrue(self.client.login(username=CORREO, password=CLAVE))
        entrada = LogEntry.objects.get(object_id=str(self.cuenta.pk))
        self.assertEqual(entrada.user, self.administrador)
        self.assertEqual(entrada.action_flag, CHANGE)
        self.assertIn('aprobada', entrada.change_message)

    def test_aprobar_dos_veces_o_una_cuenta_que_no_esta_pendiente_falla(self):
        aprobar_cuenta(self.cuenta.pk, self.administrador)

        with self.assertRaises(CuentaNoPendiente):
            aprobar_cuenta(self.cuenta.pk, self.administrador)
        with self.assertRaises(CuentaNoPendiente):
            aprobar_cuenta(crear_docente().pk, self.administrador)
        with self.assertRaises(CuentaNoPendiente):
            aprobar_cuenta(999999, self.administrador)

    def test_rechazar_desactiva_la_cuenta_sin_borrarla(self):
        rechazar_cuenta(self.cuenta.pk, self.administrador)

        self.cuenta.refresh_from_db()
        self.assertFalse(self.cuenta.is_active)
        self.assertFalse(self.cuenta.aprobado)
        self.assertFalse(self.client.login(username=CORREO, password=CLAVE))
        self.assertIn('rechazada', LogEntry.objects.get(object_id=str(self.cuenta.pk)).change_message)

    def test_no_se_puede_aprobar_ni_rechazar_una_cuenta_ya_rechazada(self):
        rechazar_cuenta(self.cuenta.pk, self.administrador)

        with self.assertRaises(CuentaNoPendiente):
            aprobar_cuenta(self.cuenta.pk, self.administrador)
        with self.assertRaises(CuentaNoPendiente):
            rechazar_cuenta(self.cuenta.pk, self.administrador)

    def test_el_correo_de_una_cuenta_rechazada_sigue_ocupado(self):
        rechazar_cuenta(self.cuenta.pk, self.administrador)

        with self.assertRaises(CorreoYaRegistrado):
            registrar()

    def test_una_cuenta_rechazada_que_se_reactiva_vuelve_a_estar_pendiente(self):
        rechazar_cuenta(self.cuenta.pk, self.administrador)
        Usuario.objects.filter(pk=self.cuenta.pk).update(is_active=True)

        self.assertEqual([u.pk for u in cuentas_pendientes()], [self.cuenta.pk])
        aprobar_cuenta(self.cuenta.pk, self.administrador)
        self.assertTrue(self.client.login(username=CORREO, password=CLAVE))


# ---------------------------------------------------------------------------
# La aprobación en el admin de Django
# ---------------------------------------------------------------------------

class AprobacionEnElAdminTests(TestCase):
    """El admin muestra si una cuenta está aprobada, pero no la aprueba: eso es del panel."""

    @classmethod
    def setUpTestData(cls):
        cls.administrador = crear_administrador()
        cls.pendiente = registrar()

    def setUp(self):
        self.assertTrue(self.client.login(username='admin@asistencia.test', password=PASSWORD))

    def test_la_lista_muestra_la_columna_y_el_filtro_de_aprobacion(self):
        respuesta = self.client.get('/admin/asistencia/usuario/')

        self.assertContains(respuesta, 'Aprobada')
        self.assertContains(respuesta, 'Por cuenta aprobada')

    def test_el_filtro_deja_ver_solo_las_pendientes(self):
        crear_docente()

        respuesta = self.client.get('/admin/asistencia/usuario/?aprobado__exact=0')

        self.assertContains(respuesta, CORREO)
        self.assertNotContains(respuesta, 'docente@asistencia.test')

    def test_el_formulario_de_edicion_muestra_la_aprobacion_pero_no_deja_cambiarla(self):
        ruta = f'/admin/asistencia/usuario/{self.pendiente.pk}/change/'
        respuesta = self.client.get(ruta)
        self.assertNotIn('aprobado', respuesta.context['adminform'].form.fields)
        self.assertIn('aprobado', respuesta.context['adminform'].model_admin.readonly_fields)

        self.client.post(ruta, {
            'username': self.pendiente.username, 'first_name': 'Marta', 'last_name': 'Quintero',
            'email': CORREO, 'rol': 'docente', 'is_active': 'on', 'aprobado': 'on', '_save': 'Guardar'})

        self.pendiente.refresh_from_db()
        self.assertFalse(self.pendiente.aprobado)

    def test_un_usuario_dado_de_alta_por_el_administrador_nace_aprobado_y_puede_entrar(self):
        self.client.post('/admin/asistencia/usuario/add/', {
            'username': 'nora', 'usable_password': 'true',
            'password1': 'Clave-Nueva-2026#x', 'password2': 'Clave-Nueva-2026#x',
            'first_name': 'Nora', 'last_name': 'Núñez', 'email': 'nora@asistencia.test',
            'rol': 'docente', '_save': 'Guardar'})

        nuevo = Usuario.objects.get(email='nora@asistencia.test')
        self.assertTrue(nuevo.aprobado)
        self.client.logout()
        self.assertTrue(self.client.login(username='nora@asistencia.test', password='Clave-Nueva-2026#x'))
