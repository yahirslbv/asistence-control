"""Matriz de acceso (fase H): cada ruta de la aplicación contra cada visitante.

Las rutas salen de `asistencia/urls.py`, no de una lista escrita a mano: si
alguien agrega una ruta y no la clasifica aquí, la primera prueba falla y obliga
a decidir quién puede entrar (RNF-04, regla 9.6 del CLAUDE.md).

| Visitante                | Rutas con recurso      | Rutas del docente sin recurso |
|--------------------------|------------------------|-------------------------------|
| Anónimo                  | al inicio de sesión    | al inicio de sesión           |
| Administrador            | 403                    | 403                           |
| Docente ajeno al recurso | 404 (nunca 403)        | 200                           |
| Docente dueño            | 200                    | 200                           |
"""

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, BitacoraCambio, Grupo, Inscripcion, Sesion
from asistencia.services.justificantes import adjuntar_justificante
from asistencia.urls import urlpatterns

from .test_justificantes import PDF
from .utils import (
    PASSWORD, MediaTemporalMixin, RelojFijoMixin, crear_administrador, crear_docente,
    crear_grupo, crear_sesion, inscribir_alumnos,
)

# Rutas abiertas a cualquiera (el cierre de sesión es solo por POST).
PUBLICAS = {'login', 'logout'}
# Cualquier usuario con sesión; cada rol va a su pantalla.
SOLO_CON_SESION = {'inicio'}
# Pantallas del docente que no reciben ningún recurso.
DEL_DOCENTE_SIN_RECURSO = {'grupos', 'grupo_crear', 'pase_de_lista_inicio', 'reportes'}
# Los parámetros que sabemos poblar: grupo, sesión, alumno y formato de exportación.
PARAMETROS_CONOCIDOS = {'grupo_id', 'sesion_id', 'alumno_id', 'formato'}
# Estas editan o cancelan una sesión programada; el resto de las de sesión
# necesitan una realizada con su justificante.
DE_SESION_PROGRAMADA = {'sesion_editar', 'sesion_cancelar'}

RUTAS = [patron for patron in urlpatterns if hasattr(patron, 'name')]


def parametros(patron):
    return set(patron.pattern.converters)


def con_recurso():
    return [p for p in RUTAS if parametros(p)]


def sin_recurso_del_docente():
    return [p for p in RUTAS if p.name in DEL_DOCENTE_SIN_RECURSO]


class MatrizDeAcceso(MediaTemporalMixin, RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.dueno = crear_docente()
        cls.intruso = crear_docente('intruso@asistencia.test', 'intruso')
        cls.administrador = crear_administrador()

        cls.grupo = crear_grupo(cls.dueno)
        cls.alumno, otro = inscribir_alumnos(cls.grupo, 2)
        cls.realizada = crear_sesion(cls.grupo, fecha=date(2026, 10, 19), estado=Sesion.Estado.REALIZADA)
        cls.programada = crear_sesion(cls.grupo, fecha=date(2026, 10, 21))
        Asistencia.objects.bulk_create([
            Asistencia(sesion=cls.realizada, alumno=cls.alumno,
                       estado=Asistencia.Estado.JUSTIFICADO, registrado_por=cls.dueno),
            Asistencia(sesion=cls.realizada, alumno=otro,
                       estado=Asistencia.Estado.PRESENTE, registrado_por=cls.dueno),
        ])
        adjuntar_justificante(
            cls.realizada.pk, cls.alumno.pk,
            SimpleUploadedFile('constancia.pdf', PDF, content_type='application/pdf'))

        # Un grupo del intruso, con su propio alumno y sesión.
        cls.grupo_propio = crear_grupo(cls.intruso, clave='PROPIO-1')
        cls.alumno_propio = inscribir_alumnos(cls.grupo_propio, 1, primera_matricula=1900000)[0]
        cls.sesion_propia = crear_sesion(cls.grupo_propio, estado=Sesion.Estado.REALIZADA)
        Asistencia.objects.create(
            sesion=cls.sesion_propia, alumno=cls.alumno_propio,
            estado=Asistencia.Estado.JUSTIFICADO, registrado_por=cls.intruso)

    # --- Ayudas -----------------------------------------------------------

    def url(self, patron, grupo=None, sesion=None, alumno=None):
        valores = {
            'grupo_id': (grupo or self.grupo).pk,
            'sesion_id': (sesion or (
                self.programada if patron.name in DE_SESION_PROGRAMADA else self.realizada)).pk,
            'alumno_id': (alumno or self.alumno).pk,
            'formato': 'pdf',
        }
        return reverse(patron.name, kwargs={n: valores[n] for n in parametros(patron)})

    def entrar_como(self, correo):
        self.client.logout()
        if correo:
            self.assertTrue(self.client.login(username=correo, password=PASSWORD))

    def pedir(self, metodo, url):
        return getattr(self.client, metodo)(url)

    def foto_de_la_base(self):
        """Lo que no debe cambiar si un visitante sin derecho insiste."""
        return {
            'grupos': list(Grupo.objects.order_by('pk').values_list('pk', 'clave', 'materia', 'periodo')),
            'sesiones': list(Sesion.objects.order_by('pk').values_list('pk', 'fecha', 'estado')),
            'inscripciones': Inscripcion.objects.count(),
            'asistencias': list(Asistencia.objects.order_by('pk').values_list('pk', 'estado', 'justificante')),
            'bitacora': BitacoraCambio.objects.count(),
            'alumnos': Alumno.objects.count(),
            'archivos': self.archivos_de_justificantes(),
        }

    # --- La matriz -------------------------------------------------------

    def test_toda_ruta_esta_clasificada(self):
        """Una ruta nueva sin clasificar rompe esta prueba a propósito."""
        sin_clasificar = []
        for patron in RUTAS:
            if patron.name in PUBLICAS | SOLO_CON_SESION | DEL_DOCENTE_SIN_RECURSO:
                continue
            desconocidos = parametros(patron) - PARAMETROS_CONOCIDOS
            if not parametros(patron) or desconocidos:
                sin_clasificar.append(patron.name)
        self.assertEqual(sin_clasificar, [], 'Rutas sin clasificar en la matriz de acceso')
        self.assertGreaterEqual(len(con_recurso()), 18)   # la matriz no puede quedar vacía

    def test_el_anonimo_va_al_inicio_de_sesion_en_toda_ruta_protegida(self):
        self.entrar_como(None)
        protegidas = con_recurso() + sin_recurso_del_docente() + [
            p for p in RUTAS if p.name in SOLO_CON_SESION]
        for patron in protegidas:
            url = self.url(patron) if parametros(patron) else reverse(patron.name)
            for metodo in ('get', 'post'):
                with self.subTest(ruta=patron.name, metodo=metodo):
                    respuesta = self.pedir(metodo, url)
                    self.assertRedirects(
                        respuesta, f"{reverse('login')}?next={url}", fetch_redirect_response=False)

    def test_el_administrador_recibe_403_en_toda_pantalla_del_docente(self):
        self.entrar_como('admin@asistencia.test')
        antes = self.foto_de_la_base()
        rutas = con_recurso() + sin_recurso_del_docente()
        for patron in rutas:
            url = self.url(patron) if parametros(patron) else reverse(patron.name)
            for metodo in ('get', 'post'):
                with self.subTest(ruta=patron.name, metodo=metodo):
                    self.assertEqual(self.pedir(metodo, url).status_code, 403)
        self.assertEqual(self.foto_de_la_base(), antes)

    def test_un_docente_ajeno_recibe_404_nunca_403_y_no_cambia_nada(self):
        self.entrar_como('intruso@asistencia.test')
        antes = self.foto_de_la_base()
        for patron in con_recurso():
            for metodo in ('get', 'post'):
                with self.subTest(ruta=patron.name, metodo=metodo):
                    self.assertEqual(self.pedir(metodo, self.url(patron)).status_code, 404)
        self.assertEqual(self.foto_de_la_base(), antes)

    def test_un_docente_no_mezcla_sus_recursos_con_los_ajenos(self):
        """Su propio grupo o sesión con un alumno que no es suyo: también 404."""
        self.entrar_como('intruso@asistencia.test')
        antes = self.foto_de_la_base()
        for patron in con_recurso():
            nombres = parametros(patron)
            if 'alumno_id' not in nombres:
                continue
            url = self.url(
                patron, grupo=self.grupo_propio, sesion=self.sesion_propia, alumno=self.alumno)
            for metodo in ('get', 'post'):
                with self.subTest(ruta=patron.name, metodo=metodo):
                    self.assertEqual(self.pedir(metodo, url).status_code, 404)
        self.assertEqual(self.foto_de_la_base(), antes)

    def test_el_dueno_entra_a_toda_su_ruta(self):
        self.entrar_como('docente@asistencia.test')
        for patron in con_recurso() + sin_recurso_del_docente():
            url = self.url(patron) if parametros(patron) else reverse(patron.name)
            with self.subTest(ruta=patron.name):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)

    def test_cada_rol_aterriza_en_su_pantalla(self):
        for correo, esperado in (
                ('docente@asistencia.test', 200), ('intruso@asistencia.test', 200),
                ('admin@asistencia.test', 302)):
            self.entrar_como(correo)
            with self.subTest(correo=correo):
                self.assertEqual(self.client.get(reverse('inicio')).status_code, esperado)
        self.assertRedirects(self.client.get(reverse('inicio')), reverse('admin:index'),
                             fetch_redirect_response=False)
