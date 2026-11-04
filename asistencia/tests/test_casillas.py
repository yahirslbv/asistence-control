"""Pase de lista con casillas (RF-18) y fila compacta (RNF-10).

El pase de lista muestra cuatro casillas por alumno (presente, retardo, ausente y
justificado) con estas reglas:

- «Presente» o «Retardo» bloquean «Ausente» y «Justificado».
- «Ausente» bloquea «Presente» y «Retardo».
- «Justificado» es opcional y solo se puede marcar junto con «Ausente».

En la base de datos sigue habiendo un único estado por registro (sin cambios al
esquema): «ausente» con «justificado» se guarda como `justificado`; «presente» y
«retardo» juntos se guardan como `retardo`. El servidor vuelve a validar las reglas
aunque el navegador ya las aplique.
"""

import re

from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, BitacoraCambio, Sesion
from asistencia.services.asistencia import (
    CasillasIncompatibles, DatosInvalidos, FilaDeLista, casillas_de_estado,
    estado_de_casillas, estados_desde_casillas,
)

from .utils import (
    PASSWORD, RelojFijoMixin, casillas_de_la_pantalla, crear_docente, crear_grupo,
    crear_sesion, datos_del_pase, inscribir_alumnos, marcadas,
)

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO

LAS_CUATRO = {'presente', 'retardo', 'ausente', 'justificado'}


def mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


# ---------------------------------------------------------------------------
# Reglas puras (sin base de datos)
# ---------------------------------------------------------------------------

class EstadoDeLasCasillasTests(SimpleTestCase):

    def test_sin_casillas_no_hay_estado(self):
        self.assertIsNone(estado_de_casillas(set()))

    def test_cada_casilla_valida_da_su_estado(self):
        validos = {
            frozenset({'presente'}): PRESENTE,
            frozenset({'retardo'}): RETARDO,
            frozenset({'presente', 'retardo'}): RETARDO,     # llegó, con retraso
            frozenset({'ausente'}): AUSENTE,
            frozenset({'ausente', 'justificado'}): JUSTIFICADO,
        }
        for casillas, esperado in validos.items():
            with self.subTest(sorted(casillas)):
                self.assertEqual(estado_de_casillas(casillas), esperado)

    def test_presente_o_retardo_no_se_combinan_con_ausente(self):
        for casillas in ({'presente', 'ausente'}, {'retardo', 'ausente'},
                         {'presente', 'retardo', 'ausente'}):
            with self.subTest(sorted(casillas)):
                with self.assertRaises(CasillasIncompatibles):
                    estado_de_casillas(casillas)

    def test_justificado_solo_va_con_ausente(self):
        for casillas in ({'justificado'}, {'presente', 'justificado'},
                         {'retardo', 'justificado'}, {'presente', 'retardo', 'justificado'}):
            with self.subTest(sorted(casillas)):
                with self.assertRaises(CasillasIncompatibles):
                    estado_de_casillas(casillas)

    def test_las_cuatro_juntas_no_son_validas(self):
        with self.assertRaises(CasillasIncompatibles):
            estado_de_casillas(LAS_CUATRO)

    def test_una_casilla_que_no_existe_se_rechaza(self):
        with self.assertRaises(DatosInvalidos):
            estado_de_casillas({'volando'})

    def test_son_las_que_el_enunciado_permite_y_ninguna_otra(self):
        # De las 16 combinaciones posibles de cuatro casillas solo 6 son válidas
        # (ninguna, presente, retardo, presente y retardo, ausente, ausente y justificado).
        from itertools import combinations
        validas = []
        for n in range(5):
            for combo in combinations(sorted(LAS_CUATRO), n):
                try:
                    estado_de_casillas(set(combo))
                except CasillasIncompatibles:
                    continue
                validas.append(set(combo))
        self.assertEqual(len(validas), 6)

    def test_cada_estado_guardado_vuelve_a_marcar_las_mismas_casillas(self):
        self.assertEqual(casillas_de_estado(PRESENTE), {'presente'})
        self.assertEqual(casillas_de_estado(RETARDO), {'retardo'})
        self.assertEqual(casillas_de_estado(AUSENTE), {'ausente'})
        self.assertEqual(casillas_de_estado(JUSTIFICADO), {'ausente', 'justificado'})
        self.assertEqual(casillas_de_estado(None), set())

    def test_ida_y_vuelta_estado_casillas_estado(self):
        for estado in (PRESENTE, RETARDO, AUSENTE, JUSTIFICADO):
            with self.subTest(estado):
                self.assertEqual(estado_de_casillas(casillas_de_estado(estado)), estado)


class EstadosDesdeLasCasillasTests(SimpleTestCase):

    def filas(self, *nombres):
        return [FilaDeLista(Alumno(pk=i + 1, nombre=n, matricula=str(i)), None, None)
                for i, n in enumerate(nombres)]

    def test_traduce_a_estados_y_omite_a_quien_no_marco_nada(self):
        filas = self.filas('Ana', 'Beto', 'Carla')
        enviados = estados_desde_casillas(
            {1: {'presente'}, 2: {'ausente', 'justificado'}, 3: set()}, filas)

        self.assertEqual(enviados, {1: PRESENTE, 2: JUSTIFICADO})

    def test_ignora_a_los_alumnos_que_no_estan_en_la_lista_aunque_sus_casillas_sean_invalidas(self):
        filas = self.filas('Ana')

        enviados = estados_desde_casillas({1: {'presente'}, 99: {'presente', 'ausente'}}, filas)

        self.assertEqual(enviados, {1: PRESENTE})

    def test_una_combinacion_invalida_nombra_a_los_alumnos_y_no_devuelve_nada(self):
        filas = self.filas('Ana', 'Beto', 'Carla')

        with self.assertRaises(CasillasIncompatibles) as contexto:
            estados_desde_casillas(
                {1: {'presente'}, 2: {'presente', 'ausente'}, 3: {'justificado'}}, filas)

        mensaje = str(contexto.exception)
        self.assertIn('Beto', mensaje)
        self.assertIn('Carla', mensaje)
        self.assertNotIn('Ana', mensaje)
        self.assertIn('No se guardó nada', mensaje)


# ---------------------------------------------------------------------------
# La pantalla y el envío
# ---------------------------------------------------------------------------

class PantallaConCasillasTests(RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 4)
        cls.sesion = crear_sesion(cls.grupo)
        cls.url = reverse('pase_de_lista', args=[cls.sesion.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_cada_alumno_tiene_cuatro_casillas_y_solo_presente_viene_marcada(self):
        pantalla = casillas_de_la_pantalla(self.client.get(self.url))

        self.assertEqual(set(pantalla), {a.pk for a in self.alumnos})
        for alumno_id, casillas in pantalla.items():
            with self.subTest(alumno_id):
                self.assertEqual(set(casillas), LAS_CUATRO)
                self.assertEqual(marcadas(casillas), {'presente'})
                self.assertEqual(
                    {c['name'] for c in casillas.values()},
                    {f'{nombre}_{alumno_id}' for nombre in LAS_CUATRO})

    def test_las_casillas_son_checkbox_y_ya_no_hay_botones_de_radio(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'class="btn-check"', count=4 * 4)
        self.assertNotContains(respuesta, 'type="radio"')

    def test_la_lista_tiene_un_encabezado_con_los_cuatro_nombres(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'class="lista-cabecera"')
        for etiqueta in ('Presente', 'Retardo', 'Ausente', 'Justificado'):
            self.assertContains(respuesta, f'<span class="cab-largo">{etiqueta}</span>', count=1)

    def test_cada_casilla_tiene_nombre_accesible_con_el_alumno(self):
        respuesta = self.client.get(self.url)

        for etiqueta in ('Presente', 'Retardo', 'Ausente', 'Justificado'):
            self.assertContains(
                respuesta, f'<span class="estado-txt">{etiqueta}</span>', count=4)
        self.assertContains(respuesta, '<span class="visually-hidden"> de Alumno 00</span>', count=4)

    def test_la_pantalla_carga_las_reglas_de_las_casillas(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'asistencia/pase_de_lista.js')

    # --- Qué se guarda según las casillas ---

    def enviar(self, casillas_por_alumno, modo='captura'):
        datos = {'modo': modo}
        for alumno_id, casillas in casillas_por_alumno.items():
            for casilla in casillas:
                datos[f'{casilla}_{alumno_id}'] = 'on'
        return self.client.post(self.url, datos)

    def test_cada_combinacion_valida_guarda_su_estado(self):
        a = self.alumnos
        self.enviar({
            a[0].pk: {'presente'},
            a[1].pk: {'presente', 'retardo'},
            a[2].pk: {'ausente'},
            a[3].pk: {'ausente', 'justificado'},
        })

        guardado = {r.alumno_id: r.estado for r in Asistencia.objects.all()}
        self.assertEqual(guardado, {
            a[0].pk: PRESENTE, a[1].pk: RETARDO, a[2].pk: AUSENTE, a[3].pk: JUSTIFICADO})

    def test_retardo_solo_tambien_es_retardo(self):
        self.enviar({a.pk: {'presente'} for a in self.alumnos[:3]} | {self.alumnos[3].pk: {'retardo'}})

        self.assertEqual(
            Asistencia.objects.get(alumno=self.alumnos[3]).estado, RETARDO)

    def test_la_combinacion_invalida_rechaza_todo_el_envio_y_nombra_al_alumno(self):
        a = self.alumnos
        respuesta = self.client.post(self.url, {
            'modo': 'captura',
            f'presente_{a[0].pk}': 'on',
            f'presente_{a[1].pk}': 'on', f'ausente_{a[1].pk}': 'on',   # incompatibles
            f'presente_{a[2].pk}': 'on',
            f'presente_{a[3].pk}': 'on',
        }, follow=True)

        self.assertFalse(Asistencia.objects.exists())
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)
        self.assertContains(respuesta, 'Alumno 01')
        self.assertContains(respuesta, 'No se guardó nada')

    def test_justificado_sin_ausente_se_rechaza(self):
        a = self.alumnos
        datos = {'modo': 'captura', f'justificado_{a[0].pk}': 'on'}
        for alumno in a[1:]:
            datos[f'presente_{alumno.pk}'] = 'on'

        respuesta = self.client.post(self.url, datos, follow=True)

        self.assertFalse(Asistencia.objects.exists())
        self.assertContains(respuesta, 'Alumno 00')

    def test_las_casillas_invalidas_de_un_alumno_ajeno_se_ignoran(self):
        ajeno = Alumno.objects.create(matricula='8888888', nombre='No inscrito')
        datos = datos_del_pase('captura', {x.pk: PRESENTE for x in self.alumnos})
        datos[f'presente_{ajeno.pk}'] = 'on'
        datos[f'ausente_{ajeno.pk}'] = 'on'

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.count(), 4)
        self.assertFalse(Asistencia.objects.filter(alumno=ajeno).exists())

    def test_el_valor_de_la_casilla_no_importa_solo_que_venga_marcada(self):
        a = self.alumnos
        datos = datos_del_pase('captura', {x.pk: PRESENTE for x in a})
        datos[f'presente_{a[0].pk}'] = 'cualquier-cosa'

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.get(alumno=a[0]).estado, PRESENTE)

    def test_un_alumno_sin_casillas_queda_sin_registrar_y_se_avisa(self):
        estados = {a.pk: PRESENTE for a in self.alumnos[:3]}        # el cuarto no marcó nada

        respuesta = self.client.post(
            self.url, datos_del_pase('captura', estados), follow=True)

        self.assertEqual(Asistencia.objects.count(), 3)
        self.assertContains(respuesta, '1 alumno no venían en el envío y quedaron sin registrar')


class CorreccionConCasillasTests(RelojFijoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 5)
        cls.sesion = crear_sesion(cls.grupo, estado=Sesion.Estado.REALIZADA)
        a = cls.alumnos
        # El quinto alumno no tiene registro: «sin registrar».
        for alumno, estado in zip(a[:4], (PRESENTE, RETARDO, AUSENTE, JUSTIFICADO)):
            Asistencia.objects.create(
                sesion=cls.sesion, alumno=alumno, estado=estado, registrado_por=cls.docente)
        cls.url = reverse('pase_de_lista', args=[cls.sesion.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_cada_estado_guardado_marca_sus_casillas(self):
        a = self.alumnos
        pantalla = casillas_de_la_pantalla(self.client.get(self.url))

        self.assertEqual(marcadas(pantalla[a[0].pk]), {'presente'})
        self.assertEqual(marcadas(pantalla[a[1].pk]), {'retardo'})
        self.assertEqual(marcadas(pantalla[a[2].pk]), {'ausente'})
        self.assertEqual(marcadas(pantalla[a[3].pk]), {'ausente', 'justificado'})
        self.assertEqual(marcadas(pantalla[a[4].pk]), set())

    def test_corregir_de_presente_a_ausente_justificado_deja_la_bitacora(self):
        a = self.alumnos
        datos = {'modo': 'correccion'}
        for alumno, estado in zip(a[:4], (PRESENTE, RETARDO, AUSENTE, JUSTIFICADO)):
            for casilla in casillas_de_estado(estado):
                datos[f'{casilla}_{alumno.pk}'] = 'on'
        # Cambio: el primero pasa de presente a ausente con justificación.
        del datos[f'presente_{a[0].pk}']
        datos[f'ausente_{a[0].pk}'] = 'on'
        datos[f'justificado_{a[0].pk}'] = 'on'

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.get(alumno=a[0]).estado, JUSTIFICADO)
        cambio = BitacoraCambio.objects.get()
        self.assertEqual((cambio.valor_anterior, cambio.valor_nuevo), (PRESENTE, JUSTIFICADO))
        self.assertEqual(cambio.usuario, self.docente)

    def test_una_combinacion_invalida_en_la_correccion_no_cambia_nada(self):
        a = self.alumnos
        datos = {'modo': 'correccion',
                 f'presente_{a[0].pk}': 'on', f'ausente_{a[0].pk}': 'on'}

        respuesta = self.client.post(self.url, datos, follow=True)

        self.assertEqual(Asistencia.objects.get(alumno=a[0]).estado, PRESENTE)
        self.assertFalse(BitacoraCambio.objects.exists())
        self.assertContains(respuesta, 'No se guardó nada')

    def test_un_alumno_sin_registro_recibe_el_suyo_con_las_casillas(self):
        a = self.alumnos
        datos = {'modo': 'correccion', f'retardo_{a[4].pk}': 'on'}

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.get(alumno=a[4]).estado, RETARDO)


# ---------------------------------------------------------------------------
# Fila compacta (RNF-10)
# ---------------------------------------------------------------------------

class FilaCompactaTests(SimpleTestCase):
    """Valores de diseño que garantizan que la fila siga siendo táctil y legible."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = open(finders.find('asistencia/estilo.css'), encoding='utf-8').read()

    def valor(self, variable):
        encontrado = re.search(rf'--{variable}:\s*([^;]+);', self.css)
        self.assertIsNotNone(encontrado, f'Falta --{variable} en la hoja de estilos')
        return encontrado.group(1).strip()

    def test_el_alto_de_la_casilla_es_de_al_menos_44_px(self):
        self.assertGreaterEqual(int(self.valor('alto-casilla').removesuffix('px')), 44)

    def test_el_ancho_de_la_casilla_en_el_telefono_es_de_al_menos_44_px(self):
        self.assertGreaterEqual(int(self.valor('ancho-casilla').removesuffix('px')), 44)

    def test_cuatro_casillas_y_el_nombre_caben_en_375_px(self):
        # 375 px de pantalla - 2 x 16 px de margen de la página - 2 x 8 px de relleno de la fila
        ancho = int(self.valor('ancho-casilla').removesuffix('px'))
        hueco = int(self.valor('hueco-casilla').removesuffix('px'))
        quedan = 375 - 2 * 16 - 2 * 8 - 4 * ancho - 4 * hueco
        self.assertGreaterEqual(quedan, 130, 'Al nombre le deben quedar al menos 130 px')
