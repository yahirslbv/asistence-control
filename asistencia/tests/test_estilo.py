"""Diseño visual (RNF-02): la hoja de estilos se carga, la paleta es legible y el menú marca la sección activa."""

import re

from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .utils import PASSWORD, crear_docente, crear_grupo, crear_sesion

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
