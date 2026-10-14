"""Pruebas de la inscripción y baja individual de alumnos (RF-05)."""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, Inscripcion, Sesion

from .utils import PASSWORD, crear_docente, crear_grupo


class InscribirAlumnoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.url = reverse('alumno_agregar', args=[cls.grupo.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def datos(self, **cambios):
        return {'matricula': '1200001', 'nombre': 'Ana García',
                'correo': 'ana@ejemplo.mx', **cambios}

    def test_inscribe_a_un_alumno_nuevo(self):
        respuesta = self.client.post(self.url, self.datos())

        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[self.grupo.pk]))
        alumno = Alumno.objects.get()
        self.assertEqual((alumno.matricula, alumno.nombre), ('1200001', 'Ana García'))
        self.assertEqual(self.grupo.inscripciones.get().alumno, alumno)

    def test_el_correo_es_opcional(self):
        self.client.post(self.url, self.datos(correo=''))

        self.assertIsNone(Alumno.objects.get().correo)

    def test_reutiliza_al_alumno_del_padron_sin_cambiar_sus_datos(self):
        existente = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        otro_grupo = crear_grupo(self.docente, clave='BD-201')
        Inscripcion.objects.create(grupo=otro_grupo, alumno=existente, fecha_alta=date(2026, 10, 1))

        self.client.post(self.url, self.datos(nombre='Otro Nombre'))

        self.assertEqual(Alumno.objects.count(), 1)
        existente.refresh_from_db()
        self.assertEqual(existente.nombre, 'Ana García')
        self.assertEqual(Inscripcion.objects.filter(alumno=existente).count(), 2)

    def test_inscribir_dos_veces_al_mismo_alumno_no_duplica(self):
        self.client.post(self.url, self.datos())

        respuesta = self.client.post(self.url, self.datos(), follow=True)

        self.assertContains(respuesta, 'ya estaba inscrito en este grupo')
        self.assertEqual(Inscripcion.objects.count(), 1)

    def test_los_datos_obligatorios_se_validan(self):
        respuesta = self.client.post(self.url, self.datos(matricula='', nombre=''))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Alumno.objects.exists())

    def test_un_correo_invalido_se_rechaza(self):
        respuesta = self.client.post(self.url, self.datos(correo='no-es-correo'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Alumno.objects.exists())


class BajaAlumnoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumno = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        cls.inscripcion = Inscripcion.objects.create(
            grupo=cls.grupo, alumno=cls.alumno, fecha_alta=date(2026, 10, 12))
        cls.url = reverse('alumno_baja', args=[cls.grupo.pk, cls.alumno.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_la_confirmacion_no_da_de_baja(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ana García')
        self.assertTrue(Inscripcion.objects.filter(pk=self.inscripcion.pk).exists())

    def test_confirmar_quita_la_inscripcion_pero_no_al_alumno(self):
        respuesta = self.client.post(self.url)

        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[self.grupo.pk]))
        self.assertFalse(Inscripcion.objects.exists())
        self.assertTrue(Alumno.objects.filter(pk=self.alumno.pk).exists())

    def test_los_registros_de_asistencia_se_conservan(self):
        sesion = Sesion.objects.create(
            grupo=self.grupo, fecha=date(2026, 10, 19),
            hora_inicio=time(8, 0), hora_fin=time(10, 0))
        Asistencia.objects.create(
            sesion=sesion, alumno=self.alumno,
            estado=Asistencia.Estado.AUSENTE, registrado_por=self.docente)

        confirmacion = self.client.get(self.url)
        self.client.post(self.url)

        self.assertEqual(confirmacion.context['registros'], 1)
        self.assertContains(confirmacion, 'se conservan')
        self.assertEqual(Asistencia.objects.count(), 1)

    def test_el_alumno_dado_de_baja_puede_inscribirse_de_nuevo(self):
        self.client.post(self.url)

        self.client.post(reverse('alumno_agregar', args=[self.grupo.pk]), {
            'matricula': '1200001', 'nombre': 'Ana García', 'correo': ''})

        self.assertEqual(self.grupo.inscripciones.count(), 1)
        self.assertEqual(Alumno.objects.count(), 1)

    def test_el_detalle_ofrece_agregar_y_dar_de_baja(self):
        respuesta = self.client.get(reverse('grupo_detalle', args=[self.grupo.pk]))

        self.assertContains(respuesta, reverse('alumno_agregar', args=[self.grupo.pk]))
        self.assertContains(respuesta, self.url)
