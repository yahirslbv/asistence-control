"""Archivos estáticos en producción (fase J, bloque B3 de docs/DESPLIEGUE.md).

En producción los sirve WhiteNoise, con huella en el nombre (manifiesto). El
manifiesto solo se activa con DJANGO_STATIC_MANIFEST=1, que fija la imagen de
Docker: en desarrollo y en las pruebas no existe, porque sin `collectstatic`
previo toda pantalla fallaría.
"""

import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .test_configuracion import CLAVE_LARGA, ajustes

MANIFIESTO = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
SIN_MANIFIESTO = 'django.contrib.staticfiles.storage.StaticFilesStorage'
WHITENOISE = 'whitenoise.middleware.WhiteNoiseMiddleware'
SEGURIDAD = 'django.middleware.security.SecurityMiddleware'


class AjustesDeEstaticosTests(SimpleTestCase):

    def test_whitenoise_va_justo_despues_del_middleware_de_seguridad(self):
        posicion = settings.MIDDLEWARE.index(SEGURIDAD)
        self.assertEqual(settings.MIDDLEWARE[posicion + 1], WHITENOISE)

    def test_hay_carpeta_para_collectstatic(self):
        self.assertEqual(Path(settings.STATIC_ROOT), settings.BASE_DIR / 'staticfiles')

    def test_las_pruebas_corren_sin_manifiesto(self):
        # Con manifiesto y sin `collectstatic`, ninguna pantalla se podría mostrar.
        self.assertEqual(settings.STORAGES['staticfiles']['BACKEND'], SIN_MANIFIESTO)

    def test_sin_la_variable_no_hay_manifiesto(self):
        for variables in ({}, {'DJANGO_STATIC_MANIFEST': '0'}, {'DJANGO_STATIC_MANIFEST': ''}):
            valores = ajustes(DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA, **variables)
            self.assertEqual(valores['STORAGES']['staticfiles']['BACKEND'], SIN_MANIFIESTO)

    def test_con_la_variable_se_activa_el_manifiesto(self):
        valores = ajustes(
            DJANGO_DEBUG='0', DJANGO_SECRET_KEY=CLAVE_LARGA, DJANGO_STATIC_MANIFEST='1')
        self.assertEqual(valores['STORAGES']['staticfiles']['BACKEND'], MANIFIESTO)
        # Los archivos subidos (justificantes) siguen en el almacenamiento de siempre.
        self.assertEqual(
            valores['STORAGES']['default']['BACKEND'],
            'django.core.files.storage.FileSystemStorage')


class EstaticosConManifiestoTests(TestCase):
    """Lo que hace la imagen: `collectstatic` con manifiesto y WhiteNoise sirviendo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = Path(tempfile.mkdtemp(prefix='estaticos_'))
        cls.addClassCleanup(shutil.rmtree, cls.carpeta, ignore_errors=True)
        cls.enterClassContext(override_settings(
            STATIC_ROOT=cls.carpeta / 'static',
            MEDIA_ROOT=cls.carpeta / 'media',
            STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': MANIFIESTO},
            },
        ))
        call_command('collectstatic', interactive=False, verbosity=0)

    def url_con_huella(self, nombre):
        url = staticfiles_storage.url(nombre)
        base, _, extension = nombre.rpartition('.')
        self.assertRegex(url, rf'^/static/{re.escape(base)}\.[0-9a-f]{{12}}\.{extension}$')
        return url

    def test_collectstatic_deja_el_manifiesto_con_los_archivos_propios(self):
        self.assertTrue((self.carpeta / 'static' / 'staticfiles.json').is_file())
        for nombre in ('asistencia/estilo.css', 'asistencia/admin.css',
                       'asistencia/pase_de_lista.js', 'admin/css/base.css'):
            self.url_con_huella(nombre)

    def test_la_pantalla_de_acceso_enlaza_la_hoja_con_huella(self):
        respuesta = self.client.get(reverse('login'))
        self.assertContains(respuesta, self.url_con_huella('asistencia/estilo.css'))

    def test_whitenoise_sirve_la_hoja_de_la_aplicacion(self):
        respuesta = self.client.get(self.url_con_huella('asistencia/estilo.css'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta['Content-Type'].startswith('text/css'))
        # Con huella en el nombre, el navegador puede guardarla para siempre.
        self.assertIn('immutable', respuesta['Cache-Control'])
        contenido = b''.join(respuesta.streaming_content)
        self.assertIn(b'--pino', contenido)

    def test_whitenoise_sirve_las_hojas_del_admin(self):
        for nombre in ('asistencia/admin.css', 'admin/css/base.css'):
            respuesta = self.client.get(self.url_con_huella(nombre))
            self.assertEqual(respuesta.status_code, 200, nombre)
            self.assertTrue(respuesta['Content-Type'].startswith('text/css'), nombre)

    def test_whitenoise_no_sirve_media(self):
        # Un justificante existe en disco, pero no hay URL pública que lo entregue.
        carpeta = self.carpeta / 'media' / 'justificantes'
        carpeta.mkdir(parents=True)
        (carpeta / 'secreto.pdf').write_bytes(b'%PDF-1.4 secreto')
        for ruta in ('/media/justificantes/secreto.pdf',
                     '/static/../media/justificantes/secreto.pdf',
                     '/static/%2e%2e/media/justificantes/secreto.pdf'):
            respuesta = self.client.get(ruta)
            self.assertEqual(respuesta.status_code, 404, ruta)
