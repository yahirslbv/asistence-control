"""La bitácora es solo de inserción y solo lectura en el admin (regla 9.3).

Se prueba con un superusuario, que pasa cualquier chequeo de permisos: si alguien
registra BitacoraCambio con un ModelAdmin normal, estas pruebas fallan.
"""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Asistencia, BitacoraCambio, Usuario

from .utils import PASSWORD, crear_docente, crear_grupo, crear_sesion, inscribir_alumnos

SIN_ACCESO = (403, 404)   # 404 si el modelo no está en el admin; 403 si está sin permisos


class BitacoraEnElAdminTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        docente = crear_docente()
        grupo = crear_grupo(docente)
        alumno = inscribir_alumnos(grupo, 1)[0]
        sesion = crear_sesion(grupo)
        registro = Asistencia.objects.create(
            sesion=sesion, alumno=alumno, estado=Asistencia.Estado.PRESENTE,
            registrado_por=docente)
        registro.estado = Asistencia.Estado.AUSENTE
        registro.registrado_por = docente
        registro.save()
        cls.cambio = BitacoraCambio.objects.get()
        cls.registro = registro
        Usuario.objects.create_superuser(
            username='root', email='root@asistencia.test', password=PASSWORD)

    def setUp(self):
        self.client.login(username='root@asistencia.test', password=PASSWORD)

    def test_la_bitacora_no_permite_agregar_editar_ni_borrar(self):
        base = 'admin:asistencia_bitacoracambio_'
        pruebas = {
            'agregar (GET)': lambda: self.client.get('/admin/asistencia/bitacoracambio/add/'),
            'agregar (POST)': lambda: self.client.post(
                '/admin/asistencia/bitacoracambio/add/',
                {'asistencia': self.registro.pk, 'valor_anterior': 'presente',
                 'valor_nuevo': 'retardo'}),
            'editar (POST)': lambda: self.client.post(
                f'/admin/asistencia/bitacoracambio/{self.cambio.pk}/change/',
                {'valor_nuevo': 'justificado'}),
            'borrar (POST)': lambda: self.client.post(
                f'/admin/asistencia/bitacoracambio/{self.cambio.pk}/delete/', {'post': 'yes'}),
        }
        for nombre, accion in pruebas.items():
            with self.subTest(nombre):
                self.assertIn(accion().status_code, SIN_ACCESO)

        self.cambio.refresh_from_db()
        self.assertEqual(self.cambio.valor_nuevo, Asistencia.Estado.AUSENTE)
        self.assertEqual(BitacoraCambio.objects.count(), 1)

    def test_la_asistencia_tampoco_se_edita_desde_el_admin(self):
        """Editarla ahí saltaría `registrado_por` y el autor quedaría mal en la bitácora."""
        for nombre, accion in {
            'editar': lambda: self.client.post(
                f'/admin/asistencia/asistencia/{self.registro.pk}/change/', {'estado': 'presente'}),
            'borrar': lambda: self.client.post(
                f'/admin/asistencia/asistencia/{self.registro.pk}/delete/', {'post': 'yes'}),
        }.items():
            with self.subTest(nombre):
                self.assertIn(accion().status_code, SIN_ACCESO)

        self.registro.refresh_from_db()
        self.assertEqual(self.registro.estado, Asistencia.Estado.AUSENTE)
