"""Pruebas de la gestión de grupos (RF-03)."""

from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from asistencia.models import (
    Alumno, Asistencia, BitacoraCambio, Grupo, Inscripcion, Sesion,
)

from .utils import PASSWORD, crear_docente, crear_grupo


class GruposTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.otro = crear_docente('otro@asistencia.test', 'otro')

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def datos(self, **cambios):
        return {'clave': 'ADM-101', 'materia': 'Administración de Proyectos',
                'periodo': '2026-2', **cambios}

    def test_la_lista_muestra_solo_mis_grupos(self):
        propio = crear_grupo(self.docente, clave='MIO-1')
        ajeno = crear_grupo(self.otro, clave='AJENO-1')

        respuesta = self.client.get(reverse('grupos'))

        self.assertContains(respuesta, propio.clave)
        self.assertNotContains(respuesta, ajeno.clave)

    def test_alta_de_grupo_queda_a_nombre_del_docente(self):
        respuesta = self.client.post(reverse('grupo_crear'), self.datos())

        grupo = Grupo.objects.get()
        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]))
        self.assertEqual(grupo.docente, self.docente)
        self.assertEqual((grupo.clave, grupo.periodo), ('ADM-101', '2026-2'))

    def test_el_alta_no_acepta_otro_docente_en_el_envio(self):
        self.client.post(reverse('grupo_crear'), self.datos(docente=self.otro.pk))

        self.assertEqual(Grupo.objects.get().docente, self.docente)

    def test_alta_con_clave_repetida_en_el_mismo_periodo_se_rechaza(self):
        crear_grupo(self.otro)  # la clave es única por periodo, de cualquier docente

        respuesta = self.client.post(reverse('grupo_crear'), self.datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe un grupo con esa clave en ese periodo.')
        self.assertEqual(Grupo.objects.count(), 1)

    def test_la_misma_clave_en_otro_periodo_es_valida(self):
        crear_grupo(self.docente, periodo='2026-1')

        self.client.post(reverse('grupo_crear'), self.datos(periodo='2026-2'))

        self.assertEqual(Grupo.objects.count(), 2)

    def test_alta_con_campos_vacios_muestra_errores(self):
        respuesta = self.client.post(reverse('grupo_crear'), {'clave': '', 'materia': '', 'periodo': ''})

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Grupo.objects.exists())

    def test_editar_un_grupo(self):
        grupo = crear_grupo(self.docente)

        respuesta = self.client.post(
            reverse('grupo_editar', args=[grupo.pk]),
            self.datos(materia='Ingeniería de Software'),
        )

        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]))
        grupo.refresh_from_db()
        self.assertEqual(grupo.materia, 'Ingeniería de Software')

    def test_editar_con_una_clave_que_ya_existe_se_rechaza(self):
        crear_grupo(self.docente, clave='OTRO-1')
        grupo = crear_grupo(self.docente, clave='ADM-101')

        respuesta = self.client.post(
            reverse('grupo_editar', args=[grupo.pk]), self.datos(clave='OTRO-1'),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe un grupo con esa clave en ese periodo.')
        grupo.refresh_from_db()
        self.assertEqual(grupo.clave, 'ADM-101')

    def test_guardar_un_grupo_sin_cambiar_la_clave_no_choca_consigo_mismo(self):
        grupo = crear_grupo(self.docente)

        respuesta = self.client.post(reverse('grupo_editar', args=[grupo.pk]), self.datos())

        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]))

    def test_el_detalle_lista_a_los_alumnos_inscritos(self):
        grupo = crear_grupo(self.docente)
        alumno = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        Inscripcion.objects.create(grupo=grupo, alumno=alumno, fecha_alta=date(2026, 10, 12))

        respuesta = self.client.get(reverse('grupo_detalle', args=[grupo.pk]))

        self.assertContains(respuesta, '1200001')
        self.assertContains(respuesta, 'Ana García')


class EliminarGrupoTests(TestCase):
    """Dar de baja un grupo borra su historial, así que exige confirmación."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.alumno = Alumno.objects.create(matricula='1200001', nombre='Ana García')
        Inscripcion.objects.create(
            grupo=cls.grupo, alumno=cls.alumno, fecha_alta=date(2026, 10, 12))
        cls.sesion = Sesion.objects.create(
            grupo=cls.grupo, fecha=date(2026, 10, 19),
            hora_inicio=time(8, 0), hora_fin=time(10, 0))
        asistencia = Asistencia.objects.create(
            sesion=cls.sesion, alumno=cls.alumno,
            estado=Asistencia.Estado.PRESENTE, registrado_por=cls.docente)
        # Una corrección: el disparador crea la fila de bitácora.
        asistencia.estado = Asistencia.Estado.AUSENTE
        asistencia.registrado_por = cls.docente
        asistencia.save()

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def test_la_confirmacion_muestra_lo_que_se_va_a_borrar_y_no_borra(self):
        respuesta = self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context['impacto'],
            {'sesiones': 1, 'inscripciones': 1, 'asistencias': 1, 'cambios': 1,
             'justificantes': 0},
        )
        self.assertTrue(Grupo.objects.filter(pk=self.grupo.pk).exists())

    def test_la_confirmacion_usa_el_singular_cuando_hay_uno(self):
        respuesta = self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertContains(respuesta, '1 sesión<')
        self.assertContains(respuesta, '1 inscripción de un alumno')
        self.assertContains(respuesta, '1 registro de asistencia')
        self.assertContains(respuesta, '1 corrección de la bitácora')

    def test_la_confirmacion_escribe_bien_los_plurales_con_acento(self):
        grupo = crear_grupo(self.docente, clave='PLURAL-1')
        for dia in (19, 20):
            Sesion.objects.create(grupo=grupo, fecha=date(2026, 10, dia),
                                  hora_inicio=time(8, 0), hora_fin=time(10, 0))
        for matricula in ('1200010', '1200011'):
            alumno = Alumno.objects.create(matricula=matricula, nombre=f'Alumno {matricula}')
            Inscripcion.objects.create(grupo=grupo, alumno=alumno, fecha_alta=date(2026, 10, 12))

        respuesta = self.client.get(reverse('grupo_eliminar', args=[grupo.pk]))

        self.assertContains(respuesta, '2 sesiones<')
        self.assertContains(respuesta, '2 inscripciones de alumnos')
        self.assertContains(respuesta, '0 registros de asistencia')
        self.assertContains(respuesta, '0 correcciones de la bitácora')
        self.assertNotContains(respuesta, 'ónes')

    def test_confirmar_borra_el_grupo_y_su_historial_pero_no_al_alumno(self):
        respuesta = self.client.post(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertRedirects(respuesta, reverse('grupos'))
        self.assertFalse(Grupo.objects.exists())
        self.assertFalse(Sesion.objects.exists())
        self.assertFalse(Inscripcion.objects.exists())
        self.assertFalse(Asistencia.objects.exists())
        self.assertFalse(BitacoraCambio.objects.exists())
        self.assertTrue(Alumno.objects.filter(pk=self.alumno.pk).exists())
