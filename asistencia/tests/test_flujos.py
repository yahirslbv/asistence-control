"""Flujos de extremo a extremo (fase H).

Cada prueba encadena varias pantallas como las usaría una persona: todo entra
por las URL y los formularios reales, sin tocar el ORM para preparar datos.
Reloj fijo: martes 20/10/2026, 18:00 en Tijuana.

El mundo que arman es este (grupo de 40 alumnos, «Alumno 00» a «Alumno 39»):

- sesiones lunes y miércoles del 5 al 21/10: 5, 7, 12, 14 y 19/10 (pasadas) y
  21/10 (futura);
- se pasa lista el 5, 7, 12 y 14/10; el 19/10 queda sin registrar (pendiente);
- Alumno 00: ausente el 5 y el 7 (el 7 se corrige después a justificado);
- Alumno 01: ausente el 12; Alumno 02: retardo en las cuatro; Alumno 03:
  justificado el 5; los demás, presentes.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from asistencia.models import Alumno, Asistencia, BitacoraCambio, Grupo, Sesion, Usuario
from asistencia.services.exportar import a_pdf
from asistencia.services.reportes import reporte_del_grupo, tabla_del_grupo

from .test_exportar import hoja_de, texto_del_pdf
from .test_justificantes import PDF
from .utils import (
    PASSWORD, MediaTemporalMixin, RelojFijoMixin, celdas_de_la_tabla,
    crear_administrador, datos_del_pase,
)

CLAVE_DEL_DOCENTE = 'Clave-Docente-2026#x'
CORREO_DEL_DOCENTE = 'maria@asistencia.test'

PRESENTE = Asistencia.Estado.PRESENTE
RETARDO = Asistencia.Estado.RETARDO
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO

PRIMERA_MATRICULA = 1300000


class FlujoBase(MediaTemporalMixin, RelojFijoMixin, TestCase):
    """Pasos de interfaz reutilizables. Cada uno comprueba su propio resultado."""

    @classmethod
    def setUpTestData(cls):
        cls.administrador = crear_administrador()

    # --- Administrador ---------------------------------------------------

    def dar_de_alta_al_docente(self):
        """El administrador da de alta al docente desde el admin de Django."""
        self.assertTrue(self.client.login(
            username='admin@asistencia.test', password=PASSWORD))
        respuesta = self.client.post('/admin/asistencia/usuario/add/', {
            'username': 'maria', 'usable_password': 'true',
            'password1': CLAVE_DEL_DOCENTE, 'password2': CLAVE_DEL_DOCENTE,
            'first_name': 'María', 'last_name': 'Pérez', 'email': CORREO_DEL_DOCENTE,
            'rol': Usuario.Rol.DOCENTE, '_save': 'Guardar',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.client.logout()
        docente = Usuario.objects.get(email=CORREO_DEL_DOCENTE)
        self.assertEqual(docente.rol, Usuario.Rol.DOCENTE)
        self.assertFalse(docente.is_staff)
        return docente

    # --- Docente ---------------------------------------------------------

    def entrar_como_docente(self, cliente=None):
        cliente = cliente or self.client
        respuesta = cliente.post(reverse('login'), {
            'username': CORREO_DEL_DOCENTE, 'password': CLAVE_DEL_DOCENTE})
        self.assertRedirects(respuesta, reverse('inicio'), fetch_redirect_response=False)
        inicio = cliente.get(reverse('inicio'))
        self.assertEqual(inicio.status_code, 200)
        for destino in ('grupos', 'pase_de_lista_inicio', 'reportes'):
            self.assertContains(inicio, reverse(destino))
        return inicio

    def crear_el_grupo(self):
        respuesta = self.client.post(reverse('grupo_crear'), {
            'clave': 'ADM-101', 'materia': 'Administración de Proyectos',
            'periodo': '2026-2'})
        grupo = Grupo.objects.get()
        self.assertRedirects(respuesta, reverse('grupo_detalle', args=[grupo.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(grupo.docente.email, CORREO_DEL_DOCENTE)
        return grupo

    def importar_la_lista(self, grupo):
        """40 alumnos buenos y 2 filas con error: los errores se informan por
        fila y no abortan el resto del archivo."""
        filas = ['matricula,nombre,correo']
        filas += [f'{PRIMERA_MATRICULA + i},Alumno {i:02d},alumno{i:02d}@ejemplo.mx'
                  for i in range(40)]
        filas.append(',Sin matrícula,')
        filas.append(f'{PRIMERA_MATRICULA + 3},Repetido,')
        archivo = SimpleUploadedFile(
            'lista.csv', '\n'.join(filas).encode('utf-8'), content_type='text/csv')

        respuesta = self.client.post(
            reverse('alumnos_importar', args=[grupo.pk]), {'archivo': archivo}, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Matrícula repetida en el archivo')
        self.assertEqual(grupo.inscripciones.count(), 40)
        return list(Alumno.objects.filter(inscripciones__grupo=grupo).order_by('nombre'))

    def generar_las_sesiones(self, grupo):
        respuesta = self.client.post(reverse('sesiones_generar', args=[grupo.pk]), {
            'dias': ['0', '2'], 'hora_inicio': '08:00', 'hora_fin': '10:00',
            'fecha_inicio': '2026-10-05', 'fecha_fin': '2026-10-21'}, follow=True)

        self.assertContains(respuesta, 'Se programaron 6 sesiones.')
        sesiones = list(grupo.sesiones.order_by('fecha'))
        self.assertEqual([s.fecha.day for s in sesiones], [5, 7, 12, 14, 19, 21])
        return sesiones

    def pasar_lista(self, sesion, alumnos, **excepciones):
        """Primer pase de lista: todos presentes, salvo `excepciones` por
        posición (`a0=AUSENTE`). Es un único envío."""
        estados = {a.pk: PRESENTE for a in alumnos}
        for clave, valor in excepciones.items():
            estados[alumnos[int(clave[1:])].pk] = valor
        respuesta = self.client.post(
            reverse('pase_de_lista', args=[sesion.pk]),
            datos_del_pase('captura', estados), follow=True)
        self.assertContains(respuesta, 'Pase de lista guardado: 40 registros.')
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, Sesion.Estado.REALIZADA)
        return respuesta

    def armar_el_ciclo(self):
        """Pasos 1 a 5 del ciclo: del alta del docente a cuatro pases de lista."""
        self.dar_de_alta_al_docente()
        self.entrar_como_docente()
        self.grupo = self.crear_el_grupo()
        self.alumnos = self.importar_la_lista(self.grupo)
        self.sesiones = self.generar_las_sesiones(self.grupo)
        s1, s2, s3, s4, self.s5, self.futura = self.sesiones
        self.pasar_lista(s1, self.alumnos, a0=AUSENTE, a2=RETARDO, a3=JUSTIFICADO)
        self.pasar_lista(s2, self.alumnos, a0=AUSENTE, a2=RETARDO)
        self.pasar_lista(s3, self.alumnos, a1=AUSENTE, a2=RETARDO)
        self.pasar_lista(s4, self.alumnos, a2=RETARDO)
        self.s1, self.s2, self.s3, self.s4 = s1, s2, s3, s4

    def corregir_y_justificar(self):
        """El 7/10 el Alumno 00 resulta tener justificante: se corrige su
        registro a «justificado» y se adjunta el PDF."""
        estados = {a.pk: PRESENTE for a in self.alumnos}
        estados[self.alumnos[0].pk] = JUSTIFICADO
        estados[self.alumnos[2].pk] = RETARDO
        respuesta = self.client.post(
            reverse('pase_de_lista', args=[self.s2.pk]),
            datos_del_pase('correccion', estados), follow=True)
        self.assertContains(respuesta, 'Corrección guardada: 1 cambio.')

        respuesta = self.client.post(
            reverse('justificante', args=[self.s2.pk, self.alumnos[0].pk]),
            {'archivo': SimpleUploadedFile(
                'constancia.pdf', PDF, content_type='application/pdf')}, follow=True)
        self.assertContains(respuesta, 'Justificante adjuntado.')

    def celdas_del_reporte(self):
        respuesta = self.client.get(reverse('reporte_grupo', args=[self.grupo.pk]))
        self.assertEqual(respuesta.status_code, 200)
        return celdas_de_la_tabla(respuesta.content), respuesta

    def fila(self, celdas, posicion):
        matricula = str(PRIMERA_MATRICULA + posicion)
        return next(f for f in celdas['filas'] if f[0] == matricula)


class CicloCompletoDelDocenteTests(FlujoBase):

    def test_del_alta_del_docente_al_reporte_exportado(self):
        self.armar_el_ciclo()

        # El pase de lista del 19/10 sigue pendiente: el menú y el reporte lo avisan.
        inicio = self.client.get(reverse('pase_de_lista_inicio'))
        self.assertContains(inicio, '19/10/2026')
        self.assertContains(self.client.get(reverse('grupo_detalle', args=[self.grupo.pk])),
                            '19/10/2026')

        # Corrección con bitácora y justificante.
        self.corregir_y_justificar()
        cambio = BitacoraCambio.objects.get()
        self.assertEqual(
            (cambio.asistencia.alumno, cambio.valor_anterior, cambio.valor_nuevo, cambio.usuario.email),
            (self.alumnos[0], AUSENTE, JUSTIFICADO, CORREO_DEL_DOCENTE))
        historial = self.client.get(reverse('pase_de_lista', args=[self.s2.pk]))
        self.assertContains(historial, 'Alumno 00')
        descarga = self.client.get(
            reverse('justificante_archivo', args=[self.s2.pk, self.alumnos[0].pk]))
        self.assertEqual(b''.join(descarga.streaming_content), PDF)

        # Reporte con la sesión pendiente: cuatro sesiones cuentan, y lo avisa.
        celdas, respuesta = self.celdas_del_reporte()
        self.assertEqual(self.fila(celdas, 0)[2:], ['4', '2', '0', '1', '1', '3', '75.0 %', 'Bajo el mínimo'])
        self.assertEqual(self.fila(celdas, 1)[2:], ['4', '3', '0', '1', '0', '3', '75.0 %', 'Bajo el mínimo'])
        self.assertEqual(self.fila(celdas, 2)[2:], ['4', '0', '4', '0', '0', '4', '100.0 %', 'Cumple'])
        self.assertEqual(self.fila(celdas, 3)[2:], ['4', '3', '0', '0', '1', '4', '100.0 %', 'Cumple'])
        self.assertEqual(self.fila(celdas, 4)[2:], ['4', '4', '0', '0', '0', '4', '100.0 %', 'Cumple'])
        self.assertEqual(
            celdas['pie'][0][1:], ['Grupo (ponderado)', '160', '152', '4', '2', '2', '158', '98.7 %', ''])
        self.assertContains(respuesta, 'Hay 1 sesión sin pase de lista')

        # Las exportaciones traen las mismas cifras que la pantalla.
        todas = celdas['encabezado'] + [c for f in celdas['filas'] + celdas['pie'] for c in f]
        excel = self.client.get(reverse('reporte_grupo_exportar', args=[self.grupo.pk, 'xlsx']))
        hoja = hoja_de(b''.join(excel.streaming_content))
        valores = {str(c.value) for fila in hoja.iter_rows() for c in fila if c.value is not None}
        for celda in filter(None, todas):
            self.assertIn(celda, valores, f'falta «{celda}» en el Excel')
        pdf = self.client.get(reverse('reporte_grupo_exportar', args=[self.grupo.pk, 'pdf']))
        self.assertTrue(b''.join(pdf.streaming_content).startswith(b'%PDF'))
        texto = texto_del_pdf(a_pdf(tabla_del_grupo(reporte_del_grupo(self.grupo)), comprimir=False))
        for celda in filter(None, todas):
            self.assertIn(celda, texto, f'falta «{celda}» en el PDF')

        # Al pasar lista del 19/10, el aviso desaparece y la regla del 80 % se
        # aplica con enteros: exactamente 80.0 % no está bajo el mínimo.
        self.pasar_lista(self.s5, self.alumnos)
        celdas, respuesta = self.celdas_del_reporte()
        self.assertEqual(self.fila(celdas, 0)[2:], ['5', '3', '0', '1', '1', '4', '80.0 %', 'Cumple'])
        self.assertEqual(self.fila(celdas, 1)[2:], ['5', '4', '0', '1', '0', '4', '80.0 %', 'Cumple'])
        self.assertEqual(celdas['pie'][0][2:4], ['200', '192'])
        self.assertNotContains(respuesta, 'sin pase de lista')
        self.assertContains(respuesta, 'Alumnos bajo el mínimo: 0.')
        self.assertNotContains(self.client.get(reverse('pase_de_lista_inicio')), '19/10/2026')

    def test_un_registro_con_justificante_no_se_cambia_hasta_quitarlo(self):
        self.armar_el_ciclo()
        self.corregir_y_justificar()
        estados = {a.pk: PRESENTE for a in self.alumnos}
        estados[self.alumnos[2].pk] = RETARDO
        estados[self.alumnos[0].pk] = AUSENTE

        respuesta = self.client.post(
            reverse('pase_de_lista', args=[self.s2.pk]),
            datos_del_pase('correccion', estados), follow=True)

        self.assertContains(respuesta, 'tiene un justificante adjunto')
        registro = Asistencia.objects.get(sesion=self.s2, alumno=self.alumnos[0])
        self.assertEqual(registro.estado, JUSTIFICADO)
        self.assertEqual(BitacoraCambio.objects.count(), 1)

        self.client.post(reverse('justificante_quitar', args=[self.s2.pk, self.alumnos[0].pk]))
        respuesta = self.client.post(
            reverse('pase_de_lista', args=[self.s2.pk]),
            datos_del_pase('correccion', estados), follow=True)

        self.assertContains(respuesta, 'Corrección guardada: 1 cambio.')
        self.assertEqual(BitacoraCambio.objects.count(), 2)


class BajasYEliminacionTests(FlujoBase):

    def test_un_alumno_dado_de_baja_deja_de_contar_y_si_vuelve_vuelve_a_contar(self):
        self.armar_el_ciclo()
        self.corregir_y_justificar()
        alumno = self.alumnos[0]

        confirmacion = self.client.get(reverse('alumno_baja', args=[self.grupo.pk, alumno.pk]))
        self.assertContains(confirmacion, 'Alumno 00')
        self.client.post(reverse('alumno_baja', args=[self.grupo.pk, alumno.pk]))

        celdas, _ = self.celdas_del_reporte()
        self.assertEqual(len(celdas['filas']), 39)
        self.assertEqual(celdas['pie'][0][2:4], ['156', '150'])    # sin los 4 registros de Alumno 00
        self.assertEqual(celdas['pie'][0][8], '99.3 %')
        self.assertEqual(
            self.client.get(reverse('reporte_alumno', args=[self.grupo.pk, alumno.pk])).status_code, 404)
        # Sus registros siguen en la sesión donde existen.
        self.assertContains(
            self.client.get(reverse('pase_de_lista', args=[self.s1.pk])), 'Alumno 00')
        self.assertEqual(Asistencia.objects.filter(alumno=alumno).count(), 4)

        self.client.post(reverse('alumno_agregar', args=[self.grupo.pk]), {
            'matricula': str(PRIMERA_MATRICULA), 'nombre': 'Alumno 00', 'correo': ''})
        celdas, _ = self.celdas_del_reporte()
        self.assertEqual(len(celdas['filas']), 40)
        self.assertEqual(celdas['pie'][0][8], '98.7 %')
        self.assertEqual(self.fila(celdas, 0)[8:], ['75.0 %', 'Bajo el mínimo'])

    def test_un_docente_desactivado_pierde_el_acceso_aunque_tenga_la_sesion_abierta(self):
        self.armar_el_ciclo()
        docente = Usuario.objects.get(email=CORREO_DEL_DOCENTE)
        self.assertEqual(self.client.get(reverse('grupos')).status_code, 200)

        administrador = Client()
        self.assertTrue(administrador.login(username='admin@asistencia.test', password=PASSWORD))
        ruta = f'/admin/asistencia/usuario/{docente.pk}/change/'
        respuesta = administrador.post(ruta, {
            'username': docente.username, 'first_name': docente.first_name,
            'last_name': docente.last_name, 'email': docente.email,
            'rol': docente.rol, '_save': 'Guardar'})   # sin `is_active`: se desactiva
        self.assertEqual(respuesta.status_code, 302)
        docente.refresh_from_db()
        self.assertFalse(docente.is_active)

        self.assertRedirects(
            self.client.get(reverse('grupos')),
            f"{reverse('login')}?next={reverse('grupos')}", fetch_redirect_response=False)
        nuevo = Client()
        respuesta = nuevo.post(reverse('login'), {
            'username': CORREO_DEL_DOCENTE, 'password': CLAVE_DEL_DOCENTE})
        self.assertContains(respuesta, 'Correo o contraseña incorrectos.')
        # Su historial se conserva: los usuarios no se borran.
        self.assertEqual(Asistencia.objects.count(), 160)

    def test_eliminar_el_grupo_borra_su_historial_y_los_archivos_pero_no_a_los_alumnos(self):
        self.armar_el_ciclo()
        self.corregir_y_justificar()
        self.assertEqual(len(self.archivos_de_justificantes()), 1)

        confirmacion = self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk]))
        self.assertContains(confirmacion, '6 sesiones')
        self.assertContains(confirmacion, '40 inscripciones')
        self.assertContains(confirmacion, '160 registros de asistencia')
        self.assertContains(confirmacion, '1 correcci')
        self.assertContains(confirmacion, '1 justificante')
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertRedirects(respuesta, reverse('grupos'), fetch_redirect_response=False)
        self.assertEqual(
            [Grupo.objects.count(), Sesion.objects.count(), Asistencia.objects.count(),
             BitacoraCambio.objects.count()], [0, 0, 0, 0])
        self.assertEqual(self.archivos_de_justificantes(), [])
        self.assertEqual(Alumno.objects.count(), 40)   # el padrón no se toca


class SesionesCanceladasYFuturasTests(FlujoBase):

    def test_una_sesion_cancelada_no_admite_registros_y_deja_de_ser_pendiente(self):
        self.armar_el_ciclo()
        self.assertContains(self.client.get(reverse('reporte_grupo', args=[self.grupo.pk])),
                            'Hay 1 sesión sin pase de lista')

        self.client.post(reverse('sesion_cancelar', args=[self.s5.pk]))
        self.s5.refresh_from_db()
        self.assertEqual(self.s5.estado, Sesion.Estado.CANCELADA)
        self.assertNotContains(self.client.get(reverse('reporte_grupo', args=[self.grupo.pk])),
                               'sin pase de lista')

        pantalla = self.client.get(reverse('pase_de_lista', args=[self.s5.pk]))
        self.assertNotContains(pantalla, 'name="modo"')
        self.client.post(
            reverse('pase_de_lista', args=[self.s5.pk]),
            datos_del_pase('captura', {a.pk: PRESENTE for a in self.alumnos}))
        self.assertFalse(Asistencia.objects.filter(sesion=self.s5).exists())
        self.assertEqual(Asistencia.objects.count(), 160)

    def test_una_sesion_futura_no_admite_pase_de_lista(self):
        self.armar_el_ciclo()

        pantalla = self.client.get(reverse('pase_de_lista', args=[self.futura.pk]))
        self.assertEqual(pantalla.status_code, 200)
        self.assertNotContains(pantalla, 'name="modo"')
        self.client.post(
            reverse('pase_de_lista', args=[self.futura.pk]),
            datos_del_pase('captura', {a.pk: PRESENTE for a in self.alumnos}))

        self.futura.refresh_from_db()
        self.assertEqual(self.futura.estado, Sesion.Estado.PROGRAMADA)
        self.assertFalse(Asistencia.objects.filter(sesion=self.futura).exists())


class DobleEnvioTests(FlujoBase):

    def test_enviar_dos_veces_el_mismo_pase_no_duplica_ni_falla(self):
        self.armar_el_ciclo()
        datos = datos_del_pase('captura', {a.pk: PRESENTE for a in self.alumnos})

        self.client.post(reverse('pase_de_lista', args=[self.s5.pk]), datos)
        segundo = self.client.post(reverse('pase_de_lista', args=[self.s5.pk]), datos, follow=True)

        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(Asistencia.objects.filter(sesion=self.s5).count(), 40)
        self.assertEqual(BitacoraCambio.objects.count(), 0)
