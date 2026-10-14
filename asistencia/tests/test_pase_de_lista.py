"""Pruebas del pase de lista: primera captura (RF-08) y sin duplicados (RF-09)."""

import threading
from datetime import date

from django.contrib.messages import get_messages
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, Inscripcion, Sesion
from asistencia.services.asistencia import (
    ConflictoDeSesion, registrar_pase_de_lista,
)

from .utils import (
    PASSWORD, crear_docente, crear_grupo, crear_sesion, datos_del_pase,
    inscribir_alumnos,
)

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO


def mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class PrimeraCapturaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 5)
        cls.sesion = crear_sesion(cls.grupo)
        cls.url = reverse('pase_de_lista', args=[cls.sesion.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def todos(self, estado=PRESENTE, **excepciones):
        """{alumno_id: estado} de los cinco, con `excepciones` por posición: a1=AUSENTE."""
        estados = {a.pk: estado for a in self.alumnos}
        for clave, valor in excepciones.items():
            estados[self.alumnos[int(clave[1:])].pk] = valor
        return estados

    def enviar(self, estados, modo='captura'):
        return self.client.post(self.url, datos_del_pase(modo, estados))

    # --- La pantalla ---

    def test_la_primera_captura_lista_a_los_inscritos_por_nombre_todos_en_presente(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['modo'], 'captura')
        filas = respuesta.context['filas']
        self.assertEqual([f.alumno.nombre for f in filas], [f'Alumno {i:02d}' for i in range(5)])
        self.assertTrue(all(f.estado == PRESENTE and f.registro is None for f in filas))

    def test_cada_alumno_tiene_cuatro_botones_y_presente_viene_marcado(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'class="btn-check"', count=5 * 4)
        self.assertContains(respuesta, 'value="presente" checked', count=5)
        for etiqueta in ('Presente', 'Retardo', 'Ausente', 'Justificado'):
            self.assertContains(respuesta, f'>{etiqueta}</label>', count=5)
        self.assertContains(respuesta, 'Guardar pase de lista', count=1)

    def test_la_primera_captura_incluye_a_los_inscritos_aunque_su_alta_sea_posterior(self):
        tardio = Alumno.objects.create(matricula='9999999', nombre='Zoe Tardía')
        Inscripcion.objects.create(grupo=self.grupo, alumno=tardio, fecha_alta=date(2026, 12, 1))

        respuesta = self.client.get(self.url)

        self.assertIn(tardio, [f.alumno for f in respuesta.context['filas']])

    def test_un_alumno_de_otro_grupo_no_aparece(self):
        otro = crear_grupo(self.docente, clave='BD-201')
        ajeno = inscribir_alumnos(otro, 1, primera_matricula=7000000)[0]

        respuesta = self.client.get(self.url)

        self.assertNotIn(ajeno, [f.alumno for f in respuesta.context['filas']])

    # --- Guardar (RF-08) ---

    def test_guardar_crea_un_registro_por_alumno_y_deja_la_sesion_realizada(self):
        respuesta = self.enviar(self.todos(a1=AUSENTE, a3=RETARDO))

        self.assertRedirects(respuesta, self.url)
        registros = Asistencia.objects.filter(sesion=self.sesion)
        self.assertEqual(registros.count(), 5)
        self.assertEqual(
            {r.alumno_id: r.estado for r in registros},
            {self.alumnos[0].pk: PRESENTE, self.alumnos[1].pk: AUSENTE,
             self.alumnos[2].pk: PRESENTE, self.alumnos[3].pk: RETARDO,
             self.alumnos[4].pk: PRESENTE})
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.REALIZADA)

    def test_los_cuatro_estados_se_guardan(self):
        self.enviar(self.todos(a0=PRESENTE, a1=RETARDO, a2=AUSENTE, a3=JUSTIFICADO))

        guardados = set(Asistencia.objects.values_list('estado', flat=True))
        self.assertEqual(guardados, {PRESENTE, RETARDO, AUSENTE, JUSTIFICADO})

    def test_cada_registro_queda_a_nombre_de_quien_tomo_la_lista(self):
        self.enviar(self.todos())

        autores = set(Asistencia.objects.values_list('registrado_por', flat=True))
        self.assertEqual(autores, {self.docente.pk})
        self.assertFalse(Asistencia.objects.filter(hora_registro__isnull=True).exists())

    def test_tras_guardar_la_sesion_se_muestra_en_modo_correccion(self):
        self.enviar(self.todos())

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['modo'], 'correccion')
        self.assertContains(respuesta, 'Guardar correcciones')

    def test_el_mensaje_de_exito_cuenta_los_registros(self):
        respuesta = self.client.post(
            self.url, datos_del_pase('captura', self.todos()), follow=True)

        self.assertContains(respuesta, 'Pase de lista guardado: 5 registros.')

    # --- Sin duplicados (RF-09) ---

    def test_un_doble_envio_no_duplica_nada(self):
        self.enviar(self.todos(a1=AUSENTE))

        # El segundo envío trae estados distintos: no debe pisar ni duplicar.
        respuesta = self.client.post(
            self.url, datos_del_pase('captura', self.todos(AUSENTE)), follow=True)

        self.assertContains(respuesta, 'ya tenía el pase de lista guardado')
        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 5)
        estados = {r.alumno_id: r.estado for r in Asistencia.objects.all()}
        self.assertEqual(estados[self.alumnos[0].pk], PRESENTE)
        self.assertEqual(estados[self.alumnos[1].pk], AUSENTE)
        # Y la página recargada es la de corrección, sin error 500.
        self.assertEqual(respuesta.context['modo'], 'correccion')

    def test_la_base_de_datos_impide_dos_registros_del_mismo_alumno_en_la_sesion(self):
        """Defensa final: aunque la validación fallara, el duplicado se deshace."""
        Asistencia.objects.create(
            sesion=self.sesion, alumno=self.alumnos[0], estado=AUSENTE,
            registrado_por=self.docente)

        with self.assertRaises(ConflictoDeSesion):
            registrar_pase_de_lista(
                self.sesion.pk, {a.pk: PRESENTE for a in self.alumnos}, self.docente)

        # Sin ignore_conflicts: no se coló ninguna de las otras cuatro filas.
        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 1)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)

    # --- Validación del envío ---

    def test_un_estado_inventado_rechaza_todo_el_envio(self):
        respuesta = self.client.post(
            self.url, datos_del_pase('captura', self.todos(a2='volando')), follow=True)

        self.assertContains(respuesta, 'un estado que no existe')
        self.assertFalse(Asistencia.objects.exists())
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)

    def test_los_alumnos_ajenos_a_la_lista_se_ignoran(self):
        ajeno = Alumno.objects.create(matricula='8888888', nombre='No inscrito')
        datos = datos_del_pase('captura', self.todos())
        datos[f'estado_{ajeno.pk}'] = AUSENTE
        datos['estado_999999'] = AUSENTE      # ni siquiera existe
        datos['estado_abc'] = AUSENTE         # clave mal formada
        datos['otro_campo'] = AUSENTE

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 5)
        self.assertFalse(Asistencia.objects.filter(alumno=ajeno).exists())

    def test_un_estado_invalido_de_un_alumno_ajeno_se_ignora_con_el_alumno(self):
        ajeno = Alumno.objects.create(matricula='8888888', nombre='No inscrito')
        datos = datos_del_pase('captura', self.todos())
        datos[f'estado_{ajeno.pk}'] = 'volando'

        self.client.post(self.url, datos)

        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 5)

    def test_los_alumnos_que_el_envio_no_trae_quedan_sin_registrar_y_se_avisa(self):
        estados = self.todos()
        del estados[self.alumnos[3].pk]
        del estados[self.alumnos[4].pk]

        respuesta = self.client.post(
            self.url, datos_del_pase('captura', estados), follow=True)

        self.assertEqual(Asistencia.objects.filter(sesion=self.sesion).count(), 3)
        self.assertContains(respuesta, '2 alumnos no venían en el envío y quedaron sin registrar')
        self.assertEqual(respuesta.context['sin_registrar'], 2)

    def test_un_envio_sin_alumnos_no_guarda_ni_cambia_la_sesion(self):
        respuesta = self.client.post(self.url, {'modo': 'captura'}, follow=True)

        self.assertContains(respuesta, 'No hay alumnos para registrar')
        self.assertFalse(Asistencia.objects.exists())
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.PROGRAMADA)

    def test_un_envio_sin_modo_o_con_un_modo_desconocido_se_rechaza(self):
        for modo in (None, 'borrar', ''):
            with self.subTest(modo=modo):
                datos = datos_del_pase(modo or '', self.todos())
                if modo is None:
                    del datos['modo']
                respuesta = self.client.post(self.url, datos, follow=True)
                self.assertContains(respuesta, 'El formulario no es válido')
        self.assertFalse(Asistencia.objects.exists())


class SesionSinAlumnosONoAdmiteRegistrosTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_una_sesion_cancelada_no_muestra_formulario(self):
        inscribir_alumnos(self.grupo, 3)
        sesion = crear_sesion(self.grupo, estado=Sesion.Estado.CANCELADA)

        respuesta = self.client.get(reverse('pase_de_lista', args=[sesion.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'está cancelada y no admite registros')
        self.assertNotContains(respuesta, 'name="modo"')
        self.assertNotContains(respuesta, 'btn-check')

    def test_una_sesion_cancelada_no_admite_registros_por_envio_directo(self):
        alumnos = inscribir_alumnos(self.grupo, 3)
        sesion = crear_sesion(self.grupo, estado=Sesion.Estado.CANCELADA)
        url = reverse('pase_de_lista', args=[sesion.pk])

        for modo in ('captura', 'correccion'):
            with self.subTest(modo=modo):
                respuesta = self.client.post(
                    url, datos_del_pase(modo, {a.pk: PRESENTE for a in alumnos}), follow=True)
                self.assertContains(respuesta, 'está cancelada y no admite registros')
        self.assertFalse(Asistencia.objects.exists())
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.CANCELADA)

    def test_un_grupo_sin_alumnos_no_ofrece_el_formulario_ni_guarda(self):
        sesion = crear_sesion(self.grupo)
        url = reverse('pase_de_lista', args=[sesion.pk])

        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'no tiene alumnos inscritos')
        self.assertNotContains(respuesta, 'name="modo"')

        respuesta = self.client.post(url, {'modo': 'captura'}, follow=True)
        self.assertContains(respuesta, 'No hay alumnos para registrar')
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.PROGRAMADA)


class ConsultasDelPaseDeListaTests(TestCase):
    """RNF-01 y RNF-07: el número de consultas no crece con el de alumnos."""

    def setUp(self):
        self.docente = crear_docente()
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def sesion_con(self, cantidad, clave):
        grupo = crear_grupo(self.docente, clave=clave)
        alumnos = inscribir_alumnos(grupo, cantidad, primera_matricula=2000000 + cantidad * 100)
        return crear_sesion(grupo), alumnos

    def consultas(self, accion):
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = accion()
        return len(capturadas), respuesta

    def test_la_pantalla_de_primera_captura_no_hace_una_consulta_por_alumno(self):
        chica, _ = self.sesion_con(5, 'CHICO-1')
        grande, _ = self.sesion_con(40, 'GRANDE-1')

        n_chica, _ = self.consultas(
            lambda: self.client.get(reverse('pase_de_lista', args=[chica.pk])))
        n_grande, respuesta = self.consultas(
            lambda: self.client.get(reverse('pase_de_lista', args=[grande.pk])))

        self.assertEqual(len(respuesta.context['filas']), 40)
        self.assertEqual(n_chica, n_grande)
        self.assertLessEqual(n_grande, 10)

    def test_guardar_el_pase_no_hace_una_consulta_por_alumno(self):
        chica, alumnos_chica = self.sesion_con(5, 'CHICO-2')
        grande, alumnos_grande = self.sesion_con(40, 'GRANDE-2')

        n_chica, _ = self.consultas(lambda: self.client.post(
            reverse('pase_de_lista', args=[chica.pk]),
            datos_del_pase('captura', {a.pk: PRESENTE for a in alumnos_chica})))
        n_grande, _ = self.consultas(lambda: self.client.post(
            reverse('pase_de_lista', args=[grande.pk]),
            datos_del_pase('captura', {a.pk: PRESENTE for a in alumnos_grande})))

        self.assertEqual(Asistencia.objects.filter(sesion=grande).count(), 40)
        self.assertEqual(n_chica, n_grande)
        self.assertLessEqual(n_grande, 16)


class EnviosSimultaneosTests(TransactionTestCase):
    """Dos envíos al mismo tiempo, en hilos con su propia conexión a MySQL."""

    def setUp(self):
        self.docente = crear_docente()
        self.grupo = crear_grupo(self.docente)
        self.alumnos = inscribir_alumnos(self.grupo, 5)
        self.sesion = crear_sesion(self.grupo)

    def test_dos_envios_simultaneos_no_duplican_ni_fallan_con_un_error_inesperado(self):
        barrera = threading.Barrier(2)
        resultados = []

        def enviar(estado):
            try:
                barrera.wait(timeout=10)
                registrar_pase_de_lista(
                    self.sesion.pk, {a.pk: estado for a in self.alumnos}, self.docente)
                resultados.append('guardado')
            except ConflictoDeSesion:
                resultados.append('conflicto')
            except Exception as error:  # cualquier otro error es un fallo de la prueba
                resultados.append(f'error inesperado: {error!r}')
            finally:
                connection.close()

        hilos = [threading.Thread(target=enviar, args=(e,)) for e in (PRESENTE, AUSENTE)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)

        self.assertEqual(sorted(resultados), ['conflicto', 'guardado'])
        registros = Asistencia.objects.filter(sesion=self.sesion)
        self.assertEqual(registros.count(), 5)
        # Todos los registros vienen del mismo envío: el que ganó.
        self.assertEqual(registros.values('estado').distinct().count(), 1)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, Sesion.Estado.REALIZADA)
