"""Diseño visual (RNF-02): la hoja de estilos se carga, la paleta es legible y el menú marca la sección activa."""

import re

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .utils import PASSWORD, crear_administrador, crear_docente, crear_grupo, crear_sesion

HOJA = 'asistencia/estilo.css'
MINIMO_TEXTO_NORMAL = 4.5  # WCAG 2.1 AA


def _luminancia(color):
    canales = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(texto, fondo):
    claro, oscuro = sorted((_luminancia(texto), _luminancia(fondo)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


class HojaDeEstilosTests(SimpleTestCase):
    """La paleta vive en variables de `estilo.css`: si alguien la cambia, el contraste se vuelve a comprobar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ruta = finders.find(HOJA)
        cls.css = open(ruta, encoding='utf-8').read() if ruta else ''
        cls.t = dict(re.findall(r'--([a-z-]+):\s*(#[0-9a-fA-F]{6})', cls.css))

    def test_la_hoja_esta_en_los_estaticos_de_la_aplicacion(self):
        self.assertTrue(self.css, f'No se encontró {HOJA} en los estáticos')

    def test_los_pares_de_texto_y_fondo_cumplen_el_contraste_minimo(self):
        t = self.t
        pares = {
            'texto principal / lienzo': (t['tinta'], t['lienzo']),
            'texto principal / tarjeta': (t['tinta'], t['superficie']),
            'texto secundario / lienzo': (t['tinta-suave'], t['lienzo']),
            'texto secundario / tarjeta': (t['tinta-suave'], t['superficie']),
            'texto secundario / realce': (t['tinta-suave'], t['realce']),
            'enlace / tarjeta': (t['enlace'], t['superficie']),
            'enlace / lienzo': (t['enlace'], t['lienzo']),
            'fila bajo el mínimo (RF-14)': (t['tinta'], t['rojo-fondo']),
        }
        for color in ('verde', 'ambar', 'rojo', 'azul', 'turquesa', 'gris'):
            pares[f'etiqueta {color}'] = (t[f'{color}-texto'], t[f'{color}-fondo'])
        for nombre, (texto, fondo) in pares.items():
            with self.subTest(nombre):
                self.assertGreaterEqual(_contraste(texto, fondo), MINIMO_TEXTO_NORMAL)

    def test_los_estados_elegidos_del_pase_de_lista_se_leen_en_blanco(self):
        # Los cuatro colores sólidos están escritos en la regla de cada estado.
        solidos = re.findall(r'--estado-solido:\s*(#[0-9a-fA-F]{6})', self.css)
        self.assertEqual(len(solidos), 4, 'Debe haber un color por estado: presente, retardo, ausente y justificado')
        for solido in solidos:
            with self.subTest(solido):
                self.assertGreaterEqual(_contraste('#ffffff', solido), MINIMO_TEXTO_NORMAL)


@override_settings(DEBUG=False)
class MenuYHojaEnLasPantallasTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.sesion = crear_sesion(cls.grupo)

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def _activos(self, url):
        """Textos de los enlaces del menú marcados como página actual."""
        html = self.client.get(url).content.decode()
        menu = html.split('<ul class="navbar-nav')[1].split('</ul>')[0]
        enlaces = re.findall(r'<a class="nav-link([^"]*)"\s*(aria-current="page")?\s*href="[^"]*">([^<]+)</a>', menu)
        return [texto for clase, actual, texto in enlaces if actual and 'active' in clase]

    def _carga_la_hoja(self, respuesta):
        # Con el almacenamiento de producción el nombre lleva una huella: estilo.3153bc6eb70d.css.
        self.assertEqual(respuesta.status_code, 200)
        self.assertRegex(respuesta.content.decode(), r'href="[^"]*asistencia/estilo(\.[0-9a-f]{12})?\.css"')

    def test_las_pantallas_con_sesion_cargan_la_hoja_de_estilos(self):
        for url in (reverse('inicio'), reverse('grupos'), reverse('pase_de_lista', args=[self.sesion.pk])):
            with self.subTest(url):
                self._carga_la_hoja(self.client.get(url))

    def test_la_pantalla_de_acceso_carga_la_hoja_de_estilos(self):
        # Con sesión iniciada /login/ redirige: se prueba con un cliente anónimo.
        self._carga_la_hoja(Client().get(reverse('login')))

    def test_el_menu_marca_grupos_en_el_grupo_y_en_sus_sesiones(self):
        for url in (reverse('grupos'), reverse('grupo_detalle', args=[self.grupo.pk]),
                    reverse('sesiones', args=[self.grupo.pk]), reverse('sesion_editar', args=[self.sesion.pk])):
            with self.subTest(url):
                self.assertEqual(self._activos(url), ['Grupos'])

    def test_el_menu_marca_pase_de_lista_en_la_lista_y_en_la_sesion(self):
        for url in (reverse('pase_de_lista_inicio'), reverse('pase_de_lista', args=[self.sesion.pk])):
            with self.subTest(url):
                self.assertEqual(self._activos(url), ['Pase de lista'])

    def test_el_menu_marca_reportes_tambien_en_el_reporte_de_un_grupo(self):
        # El reporte cuelga de /grupos/<id>/reporte/: no debe contar como «Grupos».
        for url in (reverse('reportes'), reverse('reporte_grupo', args=[self.grupo.pk])):
            with self.subTest(url):
                self.assertEqual(self._activos(url), ['Reportes'])

    def test_el_inicio_no_marca_ninguna_seccion(self):
        self.assertEqual(self._activos(reverse('inicio')), [])

    def test_el_inicio_ofrece_los_tres_accesos_del_docente(self):
        respuesta = self.client.get(reverse('inicio'))

        for destino in ('grupos', 'pase_de_lista_inicio', 'reportes'):
            self.assertContains(respuesta, f'class="acceso" href="{reverse(destino)}"')


class TemaDelAdminHojaTests(SimpleTestCase):
    """`admin.css` tiene dos paletas (clara y oscura): las dos deben leerse bien y estar en sincronía."""

    HOJA_ADMIN = 'asistencia/admin.css'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ruta = finders.find(cls.HOJA_ADMIN)
        cls.css = open(ruta, encoding='utf-8').read() if ruta else ''

    def _tokens(self, patron):
        bloque = re.search(patron, self.css, re.DOTALL)
        self.assertIsNotNone(bloque, f'No se encontró el bloque {patron!r}')
        return dict(re.findall(r'--([a-z-]+):\s*(#[0-9a-fA-F]{6})', bloque.group(1)))

    def claro(self):
        return self._tokens(r':root,\s*html\[data-theme="light"\]\s*\{(.*?)\n\}')

    def oscuro(self):
        return self._tokens(r'html\[data-theme="dark"\]\s*\{(.*?)\n\}')

    def oscuro_automatico(self):
        return self._tokens(r'@media \(prefers-color-scheme: dark\) \{\s*:root \{(.*?)\n  \}\n\}')

    def test_la_hoja_esta_en_los_estaticos(self):
        self.assertTrue(self.css, f'No se encontró {self.HOJA_ADMIN} en los estáticos')

    def test_el_tema_oscuro_automatico_y_el_forzado_son_el_mismo(self):
        self.assertEqual(self.oscuro_automatico(), self.oscuro())

    def test_las_dos_paletas_cumplen_el_contraste_minimo(self):
        for nombre, t in (('claro', self.claro()), ('oscuro', self.oscuro())):
            pares = {
                'texto principal / lienzo': (t['tinta'], t['lienzo']),
                'texto principal / tarjeta': (t['tinta'], t['superficie']),
                'texto secundario / lienzo': (t['tinta-suave'], t['lienzo']),
                'texto secundario / tarjeta': (t['tinta-suave'], t['superficie']),
                'texto secundario / realce': (t['tinta-suave'], t['realce']),
                'enlace / tarjeta': (t['enlace'], t['superficie']),
                'enlace / lienzo': (t['enlace'], t['lienzo']),
                'botón': (t['button-fg'], t['button-bg']),
                'botón principal': (t['button-fg'], t['default-button-bg']),
                'botón de acciones': (t['object-tools-fg'], t['object-tools-bg']),
                'borrar': ('#ffffff', t.get('delete-button-bg') or t['rojo-texto']),
            }
            for color in ('verde', 'ambar', 'rojo', 'azul', 'gris'):
                pares[f'aviso {color}'] = (t[f'{color}-texto'], t[f'{color}-fondo'])
            for par, (texto, fondo) in pares.items():
                with self.subTest(f'{nombre}: {par}'):
                    self.assertGreaterEqual(_contraste(texto, fondo), MINIMO_TEXTO_NORMAL)


@override_settings(DEBUG=False)
class AdminConTemaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_administrador()

    def setUp(self):
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

    def test_la_plantilla_base_del_admin_es_la_del_proyecto(self):
        # Solo gana la del proyecto si `asistencia` va antes que el admin en INSTALLED_APPS.
        origen = get_template('admin/base_site.html').origin.name.replace(chr(92), '/')
        self.assertTrue(origen.endswith('asistencia/templates/admin/base_site.html'), origen)

    def test_el_admin_carga_su_hoja_la_marca_y_los_textos_del_proyecto(self):
        respuesta = self.client.get(reverse('admin:index'))

        self.assertContains(respuesta, 'asistencia/admin.css')
        self.assertContains(respuesta, 'class="marca"')
        self.assertContains(respuesta, 'Control de asistencia')
        self.assertContains(respuesta, 'Administración')
        self.assertNotContains(respuesta, 'Django administration')
        self.assertNotContains(respuesta, 'Administración de Django')

    def test_no_se_ofrece_ver_sitio_ni_la_barra_lateral(self):
        for url in (reverse('admin:index'), reverse('admin:asistencia_periodo_changelist')):
            with self.subTest(url):
                respuesta = self.client.get(url)
                self.assertNotContains(respuesta, 'view-site')
                self.assertNotContains(respuesta, 'nav-sidebar')

    def test_las_pantallas_de_periodos_y_usuarios_usan_el_tema(self):
        for nombre in ('admin:asistencia_periodo_changelist', 'admin:asistencia_periodo_add',
                       'admin:asistencia_usuario_changelist', 'admin:asistencia_usuario_add'):
            with self.subTest(nombre):
                self.assertContains(self.client.get(reverse(nombre)), 'asistencia/admin.css')
