"""Página 500 propia (H-02, CR-001). Con DEBUG=False, que es como corre en producción.

Django la muestra sin contexto, sin sesión y a veces sin base de datos, así que la
plantilla tiene que valerse por sí sola. Estas pruebas lo comprueban provocando
errores reales en vistas de prueba, sin tocar la base de datos.
"""

from django.db import OperationalError
from django.template.loader import get_template
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path


def vista_con_error(request):
    raise RuntimeError('fallo provocado por la prueba')


def vista_con_base_de_datos_caida(request):
    raise OperationalError(2003, "Can't connect to MySQL server on '127.0.0.1'")


# Rutas de prueba: solo existen mientras dure esta clase (ROOT_URLCONF = este módulo).
urlpatterns = [
    path('falla/', vista_con_error),
    path('sin-base-de-datos/', vista_con_base_de_datos_caida),
]


@override_settings(DEBUG=False, ROOT_URLCONF=__name__)
class PaginaDeErrorDelServidorTests(SimpleTestCase):

    def setUp(self):
        # Sin esto el cliente de pruebas vuelve a lanzar la excepción en lugar de
        # devolver la respuesta 500 que vería el usuario.
        self.client = Client(raise_request_exception=False)

    def pedir(self, ruta):
        with self.assertLogs('django.request', level='ERROR'):
            return self.client.get(ruta)

    def test_un_error_del_servidor_muestra_la_pagina_500_propia(self):
        respuesta = self.pedir('/falla/')

        self.assertEqual(respuesta.status_code, 500)
        self.assertTemplateUsed(respuesta, '500.html')
        self.assertContains(respuesta, 'Algo salió mal', status_code=500)
        self.assertContains(respuesta, 'href="/"', status_code=500)
        self.assertContains(respuesta, 'lang="es"', status_code=500)
        # Ya no sale el texto mínimo y en inglés de Django.
        self.assertNotContains(respuesta, 'Server Error', status_code=500)

    def test_se_muestra_aunque_la_base_de_datos_no_responda(self):
        # El caso que motivó que la página sea independiente: un error de MySQL.
        respuesta = self.pedir('/sin-base-de-datos/')

        self.assertEqual(respuesta.status_code, 500)
        self.assertTemplateUsed(respuesta, '500.html')
        self.assertContains(respuesta, 'Algo salió mal', status_code=500)

    def test_no_muestra_el_detalle_del_error(self):
        respuesta = self.pedir('/falla/')

        self.assertNotContains(respuesta, 'fallo provocado por la prueba', status_code=500)
        self.assertNotContains(respuesta, 'RuntimeError', status_code=500)
        self.assertNotContains(respuesta, 'Traceback', status_code=500)

    def test_no_depende_del_menu_ni_de_la_hoja_de_estilos_de_la_aplicacion(self):
        respuesta = self.pedir('/falla/')

        # No extiende la base: no hay menú de usuario ni enlace a estilo.css.
        self.assertNotContains(respuesta, 'Cerrar sesión', status_code=500)
        self.assertNotContains(respuesta, 'estilo.css', status_code=500)
        self.assertNotContains(respuesta, 'bootstrap', status_code=500)

    def test_la_plantilla_no_usa_herencia_ni_rutas_ni_estaticos_ni_usuario(self):
        # Si alguien la "mejora" para que extienda la base, esta prueba avisa antes
        # de que la página de error pueda fallar por culpa de la base de datos.
        fuente = get_template('500.html').template.source

        for prohibido in ('{% extends', '{% include', '{% url', '{% static',
                          '{% load', 'request.', 'user.'):
            with self.subTest(prohibido=prohibido):
                self.assertNotIn(prohibido, fuente)
