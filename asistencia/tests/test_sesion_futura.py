"""El pase de lista solo se permite hasta hoy (fecha de Tijuana)."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Asistencia, Sesion
from asistencia.services.asistencia import (
    SesionFutura, corregir_pase_de_lista, registrar_pase_de_lista,
)

from .utils import (
    HOY, PASSWORD, RelojFijoMixin, crear_docente, crear_grupo, crear_sesion,
    datos_del_pase, hora_fija, inscribir_alumnos, momento,
)

AYER = date(2026, 10, 19)
MANANA = date(2026, 10, 21)
PRESENTE = Asistencia.Estado.PRESENTE


class PaseDeListaPorFechaTests(RelojFijoMixin, TestCase):
    """«Ahora» es martes 20/10/2026 a las 18:00 en Tijuana."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 3)

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def url(self, sesion):
        return reverse('pase_de_lista', args=[sesion.pk])

    def datos(self, modo='captura'):
        return datos_del_pase(modo, {a.pk: PRESENTE for a in self.alumnos})

    # --- Ayer y hoy: se permite ---

    def test_una_sesion_de_ayer_admite_pase_de_lista(self):
        sesion = crear_sesion(self.grupo, fecha=AYER)

        pantalla = self.client.get(self.url(sesion))
        self.assertContains(pantalla, 'name="modo"')
        self.assertContains(pantalla, 'Guardar pase de lista')

        self.client.post(self.url(sesion), self.datos())
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.REALIZADA)
        self.assertEqual(Asistencia.objects.filter(sesion=sesion).count(), 3)

    def test_una_sesion_de_hoy_admite_pase_de_lista_aunque_todavia_no_empiece(self):
        sesion = crear_sesion(self.grupo, fecha=HOY, inicio=time(20, 0), fin=time(22, 0))

        pantalla = self.client.get(self.url(sesion))
        self.assertContains(pantalla, 'name="modo"')

        self.client.post(self.url(sesion), self.datos())
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.REALIZADA)

    # --- Mañana: se rechaza ---

    def test_una_sesion_futura_muestra_un_mensaje_y_ningun_formulario(self):
        sesion = crear_sesion(self.grupo, fecha=MANANA)

        respuesta = self.client.get(self.url(sesion))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['futura'])
        self.assertContains(respuesta, 'Miércoles 21/10/2026')
        self.assertContains(respuesta, 'El pase de lista se habilita ese día')
        self.assertNotContains(respuesta, 'name="modo"')
        self.assertNotContains(respuesta, 'btn-check')
        self.assertNotContains(respuesta, 'Guardar')

    def test_un_envio_contra_una_sesion_futura_se_rechaza_sin_cambiar_nada(self):
        sesion = crear_sesion(self.grupo, fecha=MANANA)

        respuesta = self.client.post(self.url(sesion), self.datos(), follow=True)

        self.assertContains(respuesta, 'No se puede tomar lista de una sesión futura')
        self.assertContains(respuesta, 'se habilita el 21/10/2026')
        self.assertFalse(Asistencia.objects.exists())
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.PROGRAMADA)

    def test_el_servicio_rechaza_la_sesion_futura(self):
        sesion = crear_sesion(self.grupo, fecha=MANANA)

        with self.assertRaises(SesionFutura):
            registrar_pase_de_lista(
                sesion.pk, {a.pk: PRESENTE for a in self.alumnos}, self.docente)

        self.assertFalse(Asistencia.objects.exists())

    def test_una_correccion_contra_una_sesion_futura_tambien_se_rechaza(self):
        # Una sesión futura ya realizada (de antes de esta regla): ni se corrige.
        sesion = crear_sesion(self.grupo, fecha=MANANA, estado=Sesion.Estado.REALIZADA)
        Asistencia.objects.bulk_create([
            Asistencia(sesion=sesion, alumno=a, estado=PRESENTE, registrado_por=self.docente)
            for a in self.alumnos])

        respuesta = self.client.post(self.url(sesion), self.datos('correccion'), follow=True)
        pantalla = self.client.get(self.url(sesion))

        self.assertContains(respuesta, 'No se puede tomar lista de una sesión futura')
        self.assertNotContains(pantalla, 'name="modo"')
        with self.assertRaises(SesionFutura):
            corregir_pase_de_lista(
                sesion.pk, {self.alumnos[0].pk: Asistencia.Estado.AUSENTE}, self.docente)

    def test_una_sesion_cancelada_sigue_diciendo_que_esta_cancelada(self):
        sesion = crear_sesion(self.grupo, fecha=MANANA, estado=Sesion.Estado.CANCELADA)

        respuesta = self.client.get(self.url(sesion))

        self.assertContains(respuesta, 'está cancelada y no admite registros')
        self.assertNotContains(respuesta, 'se habilita ese día')

    # --- El calendario ---

    def test_el_calendario_oculta_el_boton_de_pase_de_lista_en_las_filas_futuras(self):
        ayer = crear_sesion(self.grupo, fecha=AYER)
        hoy = crear_sesion(self.grupo, fecha=HOY)
        manana = crear_sesion(self.grupo, fecha=MANANA)

        respuesta = self.client.get(reverse('sesiones', args=[self.grupo.pk]))

        self.assertContains(respuesta, self.url(ayer))
        self.assertContains(respuesta, self.url(hoy))
        self.assertNotContains(respuesta, self.url(manana))
        # Editar y cancelar una sesión futura (RF-07) siguen disponibles.
        self.assertContains(respuesta, reverse('sesion_editar', args=[manana.pk]))
        self.assertContains(respuesta, reverse('sesion_cancelar', args=[manana.pk]))


class FechaDeHoyEnTijuanaTests(TestCase):
    """«Hoy» es la fecha de Tijuana, no la de UTC."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 2)
        cls.del_20 = crear_sesion(cls.grupo, fecha=date(2026, 10, 20))
        cls.del_21 = crear_sesion(cls.grupo, fecha=date(2026, 10, 21))

    def intentar(self, sesion, instante):
        with hora_fija(instante):
            try:
                registrar_pase_de_lista(
                    sesion.pk, {a.pk: PRESENTE for a in self.alumnos}, self.docente)
            except SesionFutura:
                return False
        return True

    def test_a_las_23_30_de_tijuana_ya_es_otro_dia_en_utc_pero_no_en_tijuana(self):
        # 23:30 del 20/10 en Tijuana = 06:30 UTC del 21/10.
        instante = momento(date(2026, 10, 20), time(23, 30))
        self.assertEqual(instante.astimezone(ZoneInfo('UTC')).date(), date(2026, 10, 21))

        self.assertFalse(self.intentar(self.del_21, instante))   # en UTC sería «hoy»
        self.assertTrue(self.intentar(self.del_20, instante))

    def test_a_las_00_30_de_tijuana_ya_es_el_dia_siguiente(self):
        instante = datetime(2026, 10, 21, 0, 30, tzinfo=ZoneInfo('America/Tijuana'))

        self.assertTrue(self.intentar(self.del_21, instante))
