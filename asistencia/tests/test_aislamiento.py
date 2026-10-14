"""Aislamiento por docente (RNF-04, regla 9.6 del CLAUDE.md).

Cada docente ve y modifica solo sus grupos. Un grupo ajeno responde 404, no
403, en toda vista que reciba un `grupo_id` o un `sesion_id`.
"""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Alumno, Inscripcion

from .utils import PASSWORD, crear_administrador, crear_docente, crear_grupo

# Vistas que reciben un grupo_id: (nombre de la URL, métodos a probar).
VISTAS_DE_GRUPO = [
    ('grupo_detalle', ['get']),
    ('grupo_editar', ['get', 'post']),
    ('grupo_eliminar', ['get', 'post']),
    ('alumnos_importar', ['get', 'post']),
    ('alumno_agregar', ['get', 'post']),
]

# Vistas que no reciben un recurso y son solo para docentes.
VISTAS_SIN_RECURSO = ['grupos', 'grupo_crear']


class AislamientoPorDocenteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.intruso = crear_docente('intruso@asistencia.test', 'intruso')
        cls.administrador = crear_administrador()
        cls.grupo = crear_grupo(cls.docente)

    def entrar_como(self, correo):
        self.client.login(username=correo, password=PASSWORD)

    def test_un_grupo_ajeno_responde_404_en_todas_las_vistas(self):
        self.entrar_como('intruso@asistencia.test')

        for nombre, metodos in VISTAS_DE_GRUPO:
            for metodo in metodos:
                with self.subTest(vista=nombre, metodo=metodo):
                    url = reverse(nombre, args=[self.grupo.pk])
                    respuesta = getattr(self.client, metodo)(url)
                    self.assertEqual(respuesta.status_code, 404)

    def test_un_grupo_ajeno_no_se_modifica_ni_se_borra(self):
        self.entrar_como('intruso@asistencia.test')

        self.client.post(reverse('grupo_editar', args=[self.grupo.pk]), {
            'clave': 'HACKEADO', 'materia': 'x', 'periodo': '2026-2'})
        self.client.post(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.grupo.refresh_from_db()
        self.assertEqual(self.grupo.clave, 'ADM-101')

    def test_no_se_da_de_baja_a_un_alumno_de_un_grupo_ajeno(self):
        alumno = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        Inscripcion.objects.create(grupo=self.grupo, alumno=alumno, fecha_alta=date(2026, 10, 12))
        propio = crear_grupo(self.intruso, clave='PROPIO-1')
        self.entrar_como('intruso@asistencia.test')

        # Por el grupo ajeno, y también usando un grupo propio con el alumno ajeno.
        for grupo in (self.grupo, propio):
            for metodo in ('get', 'post'):
                with self.subTest(grupo=grupo.clave, metodo=metodo):
                    url = reverse('alumno_baja', args=[grupo.pk, alumno.pk])
                    self.assertEqual(getattr(self.client, metodo)(url).status_code, 404)
        self.assertEqual(self.grupo.inscripciones.count(), 1)

    def test_el_dueno_si_entra_a_sus_vistas(self):
        self.entrar_como('docente@asistencia.test')

        for nombre, _ in VISTAS_DE_GRUPO:
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(nombre, args=[self.grupo.pk]))
                self.assertEqual(respuesta.status_code, 200)

    def test_el_administrador_no_entra_a_las_pantallas_del_docente(self):
        self.entrar_como('admin@asistencia.test')

        urls = [reverse(nombre) for nombre in VISTAS_SIN_RECURSO]
        urls += [reverse(nombre, args=[self.grupo.pk]) for nombre, _ in VISTAS_DE_GRUPO]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_sin_sesion_se_redirige_al_login(self):
        urls = [reverse(nombre) for nombre in VISTAS_SIN_RECURSO]
        urls += [reverse(nombre, args=[self.grupo.pk]) for nombre, _ in VISTAS_DE_GRUPO]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(
                    respuesta, f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )
