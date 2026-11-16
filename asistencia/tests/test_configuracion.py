"""Configuración de producción (fase J, bloque B2 de docs/DESPLIEGUE.md).

`settings.py` se evalúa una sola vez, al arrancar. Para probarlo con otras
variables de entorno se importa en un proceso aparte: recargarlo dentro del
proceso de pruebas dejaría a medias la configuración que ya está en uso.

El proceso hijo no lee el archivo `.env` del equipo (se anula `load_dotenv`),
así que cada prueba decide exactamente qué variables existen.
"""

import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

CLAVE_LARGA = 'clave-de-prueba-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEFGH'

AJUSTES = [
    'DEBUG', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'SESSION_COOKIE_SECURE',
    'CSRF_COOKIE_SECURE', 'SECURE_PROXY_SSL_HEADER', 'SECURE_HSTS_SECONDS',
    'SECURE_SSL_REDIRECT',
]

CODIGO = """
import json
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
from django.conf import global_settings
from config import settings
valores = {
    nombre: getattr(settings, nombre, getattr(global_settings, nombre))
    for nombre in %r
}
valores['INIT_COMMAND'] = settings.DATABASES['default']['OPTIONS']['init_command']
print(json.dumps(valores))
""" % AJUSTES


def importar_settings(**variables):
    """Importa `config.settings` en otro proceso, solo con las variables dadas."""
    entorno = {
        nombre: valor for nombre, valor in os.environ.items()
        if not nombre.startswith(('DJANGO_', 'DB_'))
    }
    entorno.update(variables)
    return subprocess.run(
        [sys.executable, '-c', CODIGO],
        cwd=settings.BASE_DIR, env=entorno, capture_output=True, text=True,
        timeout=60,
    )


def ajustes(**variables):
    resultado = importar_settings(**variables)
    if resultado.returncode != 0:
        raise AssertionError(f'settings no se pudo importar:\n{resultado.stderr}')
    return json.loads(resultado.stdout)


class ClaveSecretaTests(SimpleTestCase):
    """Con DEBUG apagado la aplicación no arranca con una clave débil."""

    def assert_se_niega(self, **variables):
        resultado = importar_settings(DJANGO_DEBUG='0', **variables)
        self.assertNotEqual(resultado.returncode, 0, resultado.stdout)
        self.assertIn('ImproperlyConfigured', resultado.stderr)
        self.assertIn('DJANGO_SECRET_KEY', resultado.stderr)

    def test_sin_clave_no_arranca(self):
        self.assert_se_niega()

    def test_con_clave_vacia_no_arranca(self):
        self.assert_se_niega(DJANGO_SECRET_KEY='')
        self.assert_se_niega(DJANGO_SECRET_KEY='   ')

    def test_con_la_clave_del_ejemplo_no_arranca(self):
        self.assert_se_niega(DJANGO_SECRET_KEY='cambia-esto')

    def test_con_el_marcador_del_ejemplo_de_produccion_no_arranca(self):
        # `.env.prod.example` trae el marcador en mayúsculas.
        self.assert_se_niega(DJANGO_SECRET_KEY='CAMBIA-ESTO')
        self.assert_se_niega(DJANGO_SECRET_KEY='CAMBIA-ESTO-por-una-clave-larga')

    def test_sin_debug_declarado_tambien_se_niega(self):
        # DEBUG está apagado por defecto: no declararlo es producción.
        resultado = importar_settings()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', resultado.stderr)

    def test_con_una_clave_propia_arranca(self):
        valores = ajustes(DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA)
        self.assertFalse(valores['DEBUG'])

    def test_el_mensaje_no_muestra_la_clave_rechazada(self):
        resultado = importar_settings(
            DJANGO_DEBUG='0', DJANGO_SECRET_KEY='CAMBIA-ESTO-valor-rechazado')
        self.assertNotIn('valor-rechazado', resultado.stderr)

    def test_en_desarrollo_sigue_arrancando_sin_clave(self):
        valores = ajustes(DJANGO_DEBUG='1')
        self.assertTrue(valores['DEBUG'])


class OrigenesCsrfTests(SimpleTestCase):

    def test_por_defecto_no_hay_origenes_de_confianza(self):
        valores = ajustes(DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA)
        self.assertEqual(valores['CSRF_TRUSTED_ORIGINS'], [])

    def test_lista_separada_por_comas(self):
        valores = ajustes(
            DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA,
            DJANGO_CSRF_TRUSTED_ORIGINS='https://midominio.com , https://otro.mx,',
            DJANGO_ALLOWED_HOSTS='midominio.com, otro.mx',
        )
        self.assertEqual(
            valores['CSRF_TRUSTED_ORIGINS'], ['https://midominio.com', 'https://otro.mx'])
        self.assertEqual(valores['ALLOWED_HOSTS'], ['midominio.com', 'otro.mx'])


class HttpsTests(SimpleTestCase):

    def test_sin_https_las_cookies_no_son_solo_seguras(self):
        # Demostración local por HTTP: con cookies «secure» nadie podría entrar.
        for variables in ({}, {'DJANGO_HTTPS': '0'}):
            valores = ajustes(
                DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA, **variables)
            self.assertFalse(valores['SESSION_COOKIE_SECURE'])
            self.assertFalse(valores['CSRF_COOKIE_SECURE'])
            self.assertIsNone(valores['SECURE_PROXY_SSL_HEADER'])
            self.assertEqual(valores['SECURE_HSTS_SECONDS'], 0)

    def test_con_https_se_activan_cookies_seguras_proxy_y_hsts(self):
        valores = ajustes(
            DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA, DJANGO_HTTPS='1')
        self.assertTrue(valores['SESSION_COOKIE_SECURE'])
        self.assertTrue(valores['CSRF_COOKIE_SECURE'])
        self.assertEqual(
            valores['SECURE_PROXY_SSL_HEADER'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        # HSTS empieza bajo: uno largo en un dominio de prueba es difícil de revertir.
        self.assertEqual(valores['SECURE_HSTS_SECONDS'], 3600)

    def test_la_redireccion_a_https_la_hace_el_proxy(self):
        valores = ajustes(
            DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA, DJANGO_HTTPS='1')
        self.assertFalse(valores['SECURE_SSL_REDIRECT'])


class ConexionTests(SimpleTestCase):

    def test_la_conexion_conserva_el_modo_estricto_y_utc(self):
        valores = ajustes(DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA)
        self.assertIn("sql_mode='STRICT_TRANS_TABLES'", valores['INIT_COMMAND'])
        self.assertIn("time_zone='+00:00'", valores['INIT_COMMAND'])
