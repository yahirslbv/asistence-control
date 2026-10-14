"""Pruebas de autenticación (RF-01 y RF-02)."""

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Usuario

PASSWORD = 'clave-de-prueba-123'


class AutenticacionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = Usuario.objects.create_user(
            username='docente', email='docente@asistencia.test',
            password=PASSWORD, rol=Usuario.Rol.DOCENTE,
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin', email='admin@asistencia.test',
            password=PASSWORD, rol=Usuario.Rol.ADMINISTRADOR, is_staff=True,
        )

    def iniciar_sesion(self, correo, password):
        return self.client.post(reverse('login'), {'username': correo, 'password': password})

    def test_login_correcto_con_correo(self):
        respuesta = self.iniciar_sesion('docente@asistencia.test', PASSWORD)

        self.assertRedirects(respuesta, reverse('inicio'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.docente.pk)

    def test_login_ignora_mayusculas_en_el_correo(self):
        respuesta = self.iniciar_sesion('Docente@Asistencia.TEST', PASSWORD)

        self.assertRedirects(respuesta, reverse('inicio'), fetch_redirect_response=False)

    def test_login_con_contrasena_incorrecta(self):
        respuesta = self.iniciar_sesion('docente@asistencia.test', 'otra-clave')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_con_correo_inexistente(self):
        respuesta = self.iniciar_sesion('nadie@asistencia.test', PASSWORD)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_dado_de_baja_no_puede_entrar(self):
        Usuario.objects.filter(pk=self.docente.pk).update(is_active=False)

        respuesta = self.iniciar_sesion('docente@asistencia.test', PASSWORD)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_docente_ve_su_pantalla_de_inicio(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('inicio'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'asistencia/inicio.html')
        self.assertContains(respuesta, 'Pase de lista')
        self.assertNotContains(respuesta, 'Usuarios')

    def test_administrador_es_redirigido_al_admin(self):
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('inicio'))

        self.assertRedirects(respuesta, reverse('admin:index'), fetch_redirect_response=False)

    def test_inicio_exige_sesion(self):
        respuesta = self.client.get(reverse('inicio'))

        self.assertRedirects(
            respuesta, f"{reverse('login')}?next={reverse('inicio')}",
            fetch_redirect_response=False,
        )

    def test_logout_cierra_la_sesion(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        respuesta = self.client.post(reverse('logout'))

        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
