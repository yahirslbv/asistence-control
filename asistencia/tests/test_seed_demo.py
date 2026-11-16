"""La contraseña de demostración no llega a producción (fase J, bloque B7).

`PASSWORD_DEMO` está en un repositorio público. Con DEBUG apagado, `seed_demo`
se niega a crear cuentas con ella: exige una propia en SEED_PASSWORD.

El ejecutor de pruebas fuerza DEBUG=False, así que aquí «producción» es el
estado por defecto y «desarrollo» se declara con override_settings.
"""

import os
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from asistencia.management.commands.seed_demo import PASSWORD_DEMO
from asistencia.models import Alumno, Grupo, Periodo, Usuario

CLAVE_PROPIA = 'Otra-Clave-De-Demo-2026#z'
CORREOS = ('admin@asistencia.test', 'docente1@asistencia.test', 'docente2@asistencia.test')


def entorno(**variables):
    """El entorno del proceso sin SEED_PASSWORD, más las variables dadas."""
    limpio = {k: v for k, v in os.environ.items() if k != 'SEED_PASSWORD'}
    limpio.update(variables)
    return mock.patch.dict(os.environ, limpio, clear=True)


class SeedDemoConDebugApagadoTests(TestCase):

    def assert_no_sembro_nada(self):
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Periodo.objects.count(), 0)
        self.assertEqual(Grupo.objects.count(), 0)
        self.assertEqual(Alumno.objects.count(), 0)

    def test_sin_seed_password_se_niega_y_no_crea_nada(self):
        with entorno(), self.assertRaisesRegex(CommandError, 'SEED_PASSWORD'):
            call_command('seed_demo', verbosity=0)
        self.assert_no_sembro_nada()

    def test_con_seed_password_vacia_se_niega(self):
        with entorno(SEED_PASSWORD=''), self.assertRaisesRegex(CommandError, 'SEED_PASSWORD'):
            call_command('seed_demo', verbosity=0)
        self.assert_no_sembro_nada()

    def test_con_la_misma_clave_del_codigo_tambien_se_niega(self):
        # Ponerla en la variable no la vuelve secreta.
        with entorno(SEED_PASSWORD=PASSWORD_DEMO), self.assertRaises(CommandError):
            call_command('seed_demo', verbosity=0)
        self.assert_no_sembro_nada()

    def test_el_mensaje_explica_por_que_y_que_hacer(self):
        with entorno(), self.assertRaises(CommandError) as contexto:
            call_command('seed_demo', verbosity=0)
        mensaje = str(contexto.exception)
        self.assertIn('pública', mensaje)
        self.assertIn('createsuperuser', mensaje)
        self.assertNotIn(PASSWORD_DEMO, mensaje)

    def test_con_una_clave_propia_crea_las_cuentas_con_ella(self):
        with entorno(SEED_PASSWORD=CLAVE_PROPIA):
            call_command('seed_demo', verbosity=0)
        for correo in CORREOS:
            usuario = Usuario.objects.get(email=correo)
            self.assertTrue(usuario.check_password(CLAVE_PROPIA), correo)
            self.assertFalse(usuario.check_password(PASSWORD_DEMO), correo)

    def test_nadie_entra_con_la_clave_del_codigo(self):
        with entorno(SEED_PASSWORD=CLAVE_PROPIA):
            call_command('seed_demo', verbosity=0)
        for correo in CORREOS:
            self.assertFalse(self.client.login(username=correo, password=PASSWORD_DEMO), correo)
        self.assertTrue(self.client.login(username=CORREOS[1], password=CLAVE_PROPIA))


@override_settings(DEBUG=True)
class SeedDemoEnDesarrolloTests(TestCase):

    def test_sin_seed_password_usa_la_clave_de_demostracion(self):
        with entorno():
            call_command('seed_demo', verbosity=0)
        for correo in CORREOS:
            self.assertTrue(Usuario.objects.get(email=correo).check_password(PASSWORD_DEMO), correo)

    def test_seed_password_sigue_cambiando_la_clave(self):
        with entorno(SEED_PASSWORD=CLAVE_PROPIA):
            call_command('seed_demo', verbosity=0)
        self.assertTrue(Usuario.objects.get(email=CORREOS[0]).check_password(CLAVE_PROPIA))
