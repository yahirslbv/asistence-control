"""Un periodo inactivo congela sus grupos: solo lectura y con reportes (RF-17)."""

from datetime import date, time

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, BitacoraCambio, Grupo, Inscripcion, Sesion
from asistencia.services.justificantes import adjuntar_justificante
from asistencia.services.pendientes import sesiones_pendientes
from asistencia.services.periodos import activar_periodo, desactivar_periodo

from .utils import (
    HOY, PASSWORD, MediaTemporalMixin, RelojFijoMixin, crear_docente, crear_grupo,
    crear_periodo, crear_sesion, datos_del_pase, inscribir_alumnos,
)

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


class PeriodoCongeladoBase(RelojFijoMixin, MediaTemporalMixin, TestCase):
    """Un grupo con una sesión programada, una realizada con sus registros y un justificante."""

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.otro = crear_docente('otro@asistencia.test', 'otro')
        cls.periodo = crear_periodo('2026-2', activo=True)
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 3)
        cls.programada = crear_sesion(cls.grupo, fecha=date(2026, 10, 19))
        cls.realizada = crear_sesion(cls.grupo, fecha=date(2026, 10, 12), estado=Sesion.Estado.REALIZADA)
        for alumno, estado in zip(cls.alumnos, ('presente', 'justificado', 'ausente')):
            Asistencia.objects.create(
                sesion=cls.realizada, alumno=alumno, estado=estado, registrado_por=cls.docente)
        adjuntar_justificante(
            cls.realizada.pk, cls.alumnos[1].pk,
            SimpleUploadedFile('constancia.pdf', PDF, 'application/pdf'))

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def congelar(self):
        desactivar_periodo(self.periodo)

    def foto(self):
        """Todo lo que podría cambiar si una acción se colara."""
        return {
            'grupos': list(Grupo.objects.order_by('pk').values_list('pk', 'clave', 'materia', 'periodo')),
            'alumnos': Alumno.objects.count(),
            'inscripciones': Inscripcion.objects.count(),
            'sesiones': list(Sesion.objects.order_by('pk').values_list('pk', 'fecha', 'hora_inicio', 'estado')),
            'asistencias': list(Asistencia.objects.order_by('pk').values_list('pk', 'estado', 'justificante')),
            'bitacora': BitacoraCambio.objects.count(),
            'archivos': self.archivos_de_justificantes(),
        }

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def assert_bloqueado(self, respuesta):
        self.assertRedirects(
            respuesta, reverse('grupo_detalle', args=[self.grupo.pk]), fetch_redirect_response=False)
        self.assertTrue(
            any('2026-2 está inactivo' in m and 'solo lectura' in m for m in self.mensajes(respuesta)),
            self.mensajes(respuesta))


class AccionesBloqueadasTests(PeriodoCongeladoBase):

    def acciones(self):
        """(nombre, método, url, datos) de cada pantalla que modifica un grupo, con datos válidos."""
        g, p, r, a = self.grupo.pk, self.programada.pk, self.realizada.pk, self.alumnos
        csv = SimpleUploadedFile('lista.csv', b'matricula,nombre,correo\n9990001,Nueva Alumna,\n', 'text/csv')
        return [
            ('editar grupo', 'post', reverse('grupo_editar', args=[g]),
             {'clave': 'CAMBIADA', 'materia': 'Otra', 'periodo': '2026-2'}),
            ('eliminar grupo', 'post', reverse('grupo_eliminar', args=[g]), {}),
            ('cargar CSV', 'post', reverse('alumnos_importar', args=[g]), {'archivo': csv}),
            ('inscribir alumno', 'post', reverse('alumno_agregar', args=[g]),
             {'matricula': '9990002', 'nombre': 'Otro Alumno', 'correo': ''}),
            ('dar de baja', 'post', reverse('alumno_baja', args=[g, a[0].pk]), {}),
            ('generar sesiones', 'post', reverse('sesiones_generar', args=[g]),
             {'dias': ['1'], 'hora_inicio': '10:00', 'hora_fin': '12:00',
              'fecha_inicio': '2026-11-02', 'fecha_fin': '2026-11-30'}),
            ('editar sesión', 'post', reverse('sesion_editar', args=[p]),
             {'fecha': '2026-10-26', 'hora_inicio': '09:00', 'hora_fin': '11:00'}),
            ('cancelar sesión', 'post', reverse('sesion_cancelar', args=[p]), {}),
            ('adjuntar justificante', 'post', reverse('justificante', args=[r, a[1].pk]),
             {'archivo': SimpleUploadedFile('otra.pdf', PDF, 'application/pdf')}),
            ('quitar justificante', 'post', reverse('justificante_quitar', args=[r, a[1].pk]), {}),
            ('guardar pase de lista', 'post', reverse('pase_de_lista', args=[p]),
             datos_del_pase('captura', {x.pk: 'ausente' for x in a})),
            ('corregir pase de lista', 'post', reverse('pase_de_lista', args=[r]),
             datos_del_pase('correccion', {a[0].pk: 'ausente', a[2].pk: 'presente'})),
        ]

    def test_cada_accion_que_modifica_un_grupo_se_rechaza_y_no_cambia_nada(self):
        self.congelar()
        antes = self.foto()

        for nombre, metodo, url, datos in self.acciones():
            with self.subTest(nombre):
                self.assert_bloqueado(getattr(self.client, metodo)(url, datos))

        self.assertEqual(self.foto(), antes)

    def test_las_pantallas_de_formulario_tampoco_se_abren(self):
        self.congelar()
        g, p, r, a = self.grupo.pk, self.programada.pk, self.realizada.pk, self.alumnos
        pantallas = {
            'editar grupo': reverse('grupo_editar', args=[g]),
            'eliminar grupo': reverse('grupo_eliminar', args=[g]),
            'cargar CSV': reverse('alumnos_importar', args=[g]),
            'inscribir alumno': reverse('alumno_agregar', args=[g]),
            'dar de baja': reverse('alumno_baja', args=[g, a[0].pk]),
            'generar sesiones': reverse('sesiones_generar', args=[g]),
            'editar sesión': reverse('sesion_editar', args=[p]),
            'cancelar sesión': reverse('sesion_cancelar', args=[p]),
            'adjuntar justificante': reverse('justificante', args=[r, a[1].pk]),
            'quitar justificante': reverse('justificante_quitar', args=[r, a[1].pk]),
        }
        for nombre, url in pantallas.items():
            with self.subTest(nombre):
                self.assert_bloqueado(self.client.get(url))

    def test_al_activar_de_nuevo_vuelven_a_funcionar(self):
        self.congelar()
        self.assert_bloqueado(self.client.post(
            reverse('alumno_agregar', args=[self.grupo.pk]),
            {'matricula': '9990002', 'nombre': 'Otro Alumno', 'correo': ''}))
        self.client.get(reverse('grupo_detalle', args=[self.grupo.pk]))   # muestra y consume el aviso

        activar_periodo(self.periodo)
        respuesta = self.client.post(
            reverse('alumno_agregar', args=[self.grupo.pk]),
            {'matricula': '9990002', 'nombre': 'Otro Alumno', 'correo': ''})

        self.assertEqual(Inscripcion.objects.filter(grupo=self.grupo).count(), 4)
        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[self.grupo.pk]))
        self.assertFalse(any('solo lectura' in m for m in self.mensajes(respuesta)))

    def test_un_grupo_cuyo_periodo_no_tiene_fila_no_se_congela(self):
        self.periodo.delete()
        respuesta = self.client.post(
            reverse('alumno_agregar', args=[self.grupo.pk]),
            {'matricula': '9990002', 'nombre': 'Otro Alumno', 'correo': ''})
        self.assertEqual(Inscripcion.objects.filter(grupo=self.grupo).count(), 4)
        self.assertFalse(any('solo lectura' in m for m in self.mensajes(respuesta)))

    def test_un_grupo_ajeno_sigue_respondiendo_404_aunque_su_periodo_este_inactivo(self):
        self.congelar()
        self.client.logout()
        self.client.login(username='otro@asistencia.test', password=PASSWORD)
        for url in (reverse('grupo_editar', args=[self.grupo.pk]),
                    reverse('sesion_editar', args=[self.programada.pk]),
                    reverse('pase_de_lista', args=[self.realizada.pk])):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 404)


class ConsultaPermitidaTests(PeriodoCongeladoBase):

    def test_se_puede_consultar_todo_lo_que_no_modifica(self):
        self.congelar()
        g, r, a = self.grupo.pk, self.realizada.pk, self.alumnos
        consultas = {
            'lista de grupos': reverse('grupos'),
            'detalle del grupo': reverse('grupo_detalle', args=[g]),
            'sesiones': reverse('sesiones', args=[g]),
            'lista de la sesión realizada': reverse('pase_de_lista', args=[r]),
            'lista de la sesión programada': reverse('pase_de_lista', args=[self.programada.pk]),
            'menú de pase de lista': reverse('pase_de_lista_inicio'),
            'reportes': reverse('reportes') + '?periodo=2026-2',
            'reporte del grupo': reverse('reporte_grupo', args=[g]),
            'reporte del alumno': reverse('reporte_alumno', args=[g, a[0].pk]),
            'excel del grupo': reverse('reporte_grupo_exportar', args=[g, 'xlsx']),
            'pdf del grupo': reverse('reporte_grupo_exportar', args=[g, 'pdf']),
            'descarga del justificante': reverse('justificante_archivo', args=[r, a[1].pk]),
        }
        for nombre, url in consultas.items():
            with self.subTest(nombre):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_la_lista_realizada_se_ve_con_los_botones_deshabilitados_y_sin_guardar(self):
        self.congelar()

        respuesta = self.client.get(reverse('pase_de_lista', args=[self.realizada.pk]))

        self.assertContains(respuesta, 'Consulta de solo lectura')
        self.assertContains(respuesta, 'id="aviso-periodo-inactivo"')
        self.assertNotContains(respuesta, 'id="guardar"')
        contenido = respuesta.content.decode()
        self.assertEqual(contenido.count('class="btn-check"'), 3 * 4)
        self.assertEqual(contenido.count('disabled'), 3 * 4)
        self.assertEqual(contenido.count('checked'), 3)          # el estado de cada alumno sigue visible
        # El justificante se puede ver, pero no reemplazar ni quitar.
        self.assertContains(respuesta, 'Justificante adjunto')
        self.assertContains(respuesta, reverse('justificante_archivo', args=[self.realizada.pk, self.alumnos[1].pk]))
        reemplazar = reverse('justificante', args=[self.realizada.pk, self.alumnos[1].pk])
        quitar = reverse('justificante_quitar', args=[self.realizada.pk, self.alumnos[1].pk])
        self.assertNotContains(respuesta, f'href="{reemplazar}"')   # con comillas: es prefijo de la URL de «Ver»
        self.assertNotContains(respuesta, f'href="{quitar}"')

    def test_una_sesion_sin_lista_no_ofrece_tomarla(self):
        self.congelar()

        respuesta = self.client.get(reverse('pase_de_lista', args=[self.programada.pk]))

        self.assertContains(respuesta, 'ya no se puede tomar lista')
        self.assertNotContains(respuesta, 'btn-check')
        self.assertNotContains(respuesta, 'id="guardar"')

    def test_los_reportes_siguen_avisando_de_las_sesiones_pendientes(self):
        self.congelar()
        respuesta = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))
        self.assertContains(respuesta, 'id="aviso-pendientes"')


class PantallasEnSoloLecturaTests(PeriodoCongeladoBase):

    def enlaces_de_acciones(self):
        g, p, a = self.grupo.pk, self.programada.pk, self.alumnos
        return {
            'detalle': (reverse('grupo_detalle', args=[g]), [
                reverse('grupo_editar', args=[g]), reverse('grupo_eliminar', args=[g]),
                reverse('alumno_agregar', args=[g]), reverse('alumnos_importar', args=[g]),
                reverse('alumno_baja', args=[g, a[0].pk])]),
            'sesiones': (reverse('sesiones', args=[g]), [
                reverse('sesiones_generar', args=[g]), reverse('sesion_editar', args=[p]),
                reverse('sesion_cancelar', args=[p]), reverse('pase_de_lista', args=[p])]),
        }

    def test_con_el_periodo_inactivo_se_ocultan_las_acciones_y_se_avisa(self):
        self.congelar()
        for pantalla, (url, enlaces) in self.enlaces_de_acciones().items():
            respuesta = self.client.get(url)
            self.assertContains(respuesta, 'id="aviso-periodo-inactivo"')
            self.assertContains(respuesta, 'Periodo 2026-2 inactivo')
            for enlace in enlaces:
                with self.subTest(f'{pantalla}: {enlace}'):
                    self.assertNotContains(respuesta, f'href="{enlace}"')

    def test_las_sesiones_realizadas_conservan_ver_asistencia(self):
        self.congelar()
        respuesta = self.client.get(reverse('sesiones', args=[self.grupo.pk]))
        self.assertContains(respuesta, 'Ver asistencia')
        self.assertContains(respuesta, f'href="{reverse("pase_de_lista", args=[self.realizada.pk])}"')

    def test_con_el_periodo_activo_se_ofrece_todo_y_no_hay_aviso(self):
        for pantalla, (url, enlaces) in self.enlaces_de_acciones().items():
            respuesta = self.client.get(url)
            self.assertNotContains(respuesta, 'id="aviso-periodo-inactivo"')
            for enlace in enlaces:
                with self.subTest(f'{pantalla}: {enlace}'):
                    self.assertContains(respuesta, f'href="{enlace}"')

    def test_la_lista_de_grupos_marca_los_de_periodos_inactivos(self):
        otro_periodo = crear_periodo('2026-1')
        crear_grupo(self.docente, clave='VIEJO-1', periodo='2026-1')

        respuesta = self.client.get(reverse('grupos'))

        contenido = respuesta.content.decode()
        self.assertEqual(contenido.count('Solo lectura'), 1)
        self.assertLess(contenido.index('VIEJO-1'), contenido.index('Solo lectura'))
        self.assertTrue(otro_periodo.pk)


class PendientesYPeriodosInactivosTests(PeriodoCongeladoBase):
    """Lo que ya no se puede atender no se avisa como pendiente (pero los reportes siguen contándolo)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.de_hoy = crear_sesion(cls.grupo, fecha=HOY, inicio=time(8, 0), fin=time(10, 0))

    def test_el_servicio_las_omite_solo_si_se_le_pide(self):
        self.congelar()
        con_todo = {s.pk for s in sesiones_pendientes(self.docente)}
        atendibles = {s.pk for s in sesiones_pendientes(self.docente, solo_atendibles=True)}

        self.assertEqual(con_todo, {self.programada.pk, self.de_hoy.pk})
        self.assertEqual(atendibles, set())

    def test_con_el_periodo_activo_las_pendientes_se_ven_igual(self):
        atendibles = {s.pk for s in sesiones_pendientes(self.docente, solo_atendibles=True)}
        self.assertEqual(atendibles, {self.programada.pk, self.de_hoy.pk})

    def test_sigue_siendo_una_sola_consulta(self):
        self.congelar()
        with self.assertNumQueries(1):
            sesiones_pendientes(self.docente, solo_atendibles=True)
        with self.assertNumQueries(1):
            sesiones_pendientes(self.docente)

    def test_las_alertas_de_la_lista_de_grupos_y_del_detalle_se_apagan(self):
        self.assertContains(self.client.get(reverse('grupos')), 'id="pendientes"')
        self.assertContains(self.client.get(reverse('grupo_detalle', args=[self.grupo.pk])), 'id="pendientes"')
        self.congelar()
        self.assertNotContains(self.client.get(reverse('grupos')), 'id="pendientes"')
        self.assertNotContains(self.client.get(reverse('grupo_detalle', args=[self.grupo.pk])), 'id="pendientes"')

    def test_el_menu_de_pase_de_lista_no_ofrece_las_sesiones_de_hoy_de_un_periodo_inactivo(self):
        respuesta = self.client.get(reverse('pase_de_lista_inicio'))
        self.assertContains(respuesta, 'ADM-101')

        self.congelar()
        respuesta = self.client.get(reverse('pase_de_lista_inicio'))
        self.assertNotContains(respuesta, 'ADM-101')
