"""Páginas 403 y 404 propias. Con DEBUG=False, que es como corre en producción."""

from django.test import TestCase, override_settings
from django.urls import reverse

from .utils import PASSWORD, crear_administrador, crear_docente, crear_grupo


@override_settings(DEBUG=False)
class PaginasDeErrorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.otro = crear_docente('otro@asistencia.test', 'otro')
        crear_administrador()
        cls.grupo_ajeno = crear_grupo(cls.otro, clave='SECRETO-9')

    def test_una_url_inexistente_muestra_la_pagina_404_propia(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        respuesta = self.client.get('/esta/pagina/no/existe/')

        self.assertEqual(respuesta.status_code, 404)
        self.assertTemplateUsed(respuesta, '404.html')
        self.assertContains(respuesta, 'No encontramos esa página', status_code=404)
        self.assertContains(respuesta, reverse('inicio'), status_code=404)
        # Extiende la base: conserva el menú del usuario.
        self.assertContains(respuesta, 'Cerrar sesión', status_code=404)

    def test_la_pagina_404_funciona_sin_sesion(self):
        respuesta = self.client.get('/esta/pagina/no/existe/')

        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, 'No encontramos esa página', status_code=404)
        self.assertNotContains(respuesta, 'Cerrar sesión', status_code=404)

    def test_un_grupo_ajeno_se_ve_igual_que_uno_que_no_existe(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

        ajeno = self.client.get(reverse('grupo_detalle', args=[self.grupo_ajeno.pk]))
        inexistente = self.client.get(reverse('grupo_detalle', args=[999999]))

        for respuesta in (ajeno, inexistente):
            self.assertEqual(respuesta.status_code, 404)
            self.assertTemplateUsed(respuesta, '404.html')
            self.assertContains(respuesta, 'No encontramos esa página', status_code=404)
            self.assertNotContains(respuesta, 'SECRETO-9', status_code=404)

    def test_el_administrador_ve_la_pagina_403_propia(self):
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

        respuesta = self.client.get(reverse('grupos'))

        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, '403.html')
        self.assertContains(
            respuesta, 'No tienes permiso para ver esta página', status_code=403)
        self.assertContains(respuesta, reverse('inicio'), status_code=403)
