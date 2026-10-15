"""Pruebas de los justificantes de asistencia (RF-12)."""

import re
from datetime import date
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from asistencia.models import Asistencia, BitacoraCambio, Sesion
from asistencia.services.justificantes import (
    TAMANO_MAXIMO_BYTES, RegistroNoJustificado, adjuntar_justificante,
)

from .utils import (
    PASSWORD, MediaTemporalMixin, RelojFijoMixin, crear_administrador,
    crear_docente, crear_grupo, crear_sesion, datos_del_pase, inscribir_alumnos,
)

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n'
JPG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'\x00' * 32 + b'\xff\xd9'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32

PRESENTE = Asistencia.Estado.PRESENTE
AUSENTE = Asistencia.Estado.AUSENTE
JUSTIFICADO = Asistencia.Estado.JUSTIFICADO

NOMBRE_GUARDADO = re.compile(r'^justificantes/[0-9a-f]{32}\.(pdf|jpg|png)$')


def subir(nombre, contenido):
    return SimpleUploadedFile(nombre, contenido, content_type='application/octet-stream')


class JustificanteBase(MediaTemporalMixin, RelojFijoMixin, TestCase):
    """Una sesión realizada con cinco registros:

    a_pdf, a_jpg y a_png: justificados (los que reciben archivo)
    b: presente    c: ausente
    """

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.capturista = crear_docente('captura@asistencia.test', 'captura')
        cls.grupo = crear_grupo(cls.docente)
        cls.alumnos = inscribir_alumnos(cls.grupo, 5)
        cls.a_pdf, cls.a_jpg, cls.a_png, cls.b, cls.c = cls.alumnos
        cls.sesion = crear_sesion(cls.grupo, estado=Sesion.Estado.REALIZADA)
        estados = [JUSTIFICADO, JUSTIFICADO, JUSTIFICADO, PRESENTE, AUSENTE]
        Asistencia.objects.bulk_create([
            Asistencia(sesion=cls.sesion, alumno=alumno, estado=estado,
                       registrado_por=cls.capturista)
            for alumno, estado in zip(cls.alumnos, estados)
        ])

    def setUp(self):
        self.vaciar_justificantes()
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def url(self, nombre, alumno):
        return reverse(nombre, args=[self.sesion.pk, alumno.pk])

    def registro(self, alumno):
        return Asistencia.objects.get(sesion=self.sesion, alumno=alumno)

    def adjuntar(self, alumno, nombre, contenido, **extra):
        return self.client.post(
            self.url('justificante', alumno), {'archivo': subir(nombre, contenido)}, **extra)

    def guardado_en_disco(self, registro):
        return (self.media_temporal / registro.justificante.name).read_bytes()


class AdjuntarJustificanteTests(JustificanteBase):

    def test_adjunta_un_pdf_un_jpg_y_un_png_validos(self):
        casos = [(self.a_pdf, 'constancia.pdf', PDF, 'pdf'),
                 (self.a_jpg, 'foto.jpg', JPG, 'jpg'),
                 (self.a_png, 'captura.png', PNG, 'png')]
        for alumno, nombre, contenido, extension in casos:
            with self.subTest(extension):
                respuesta = self.adjuntar(alumno, nombre, contenido, follow=True)

                self.assertRedirects(respuesta, reverse('pase_de_lista', args=[self.sesion.pk]))
                self.assertContains(respuesta, 'Justificante adjuntado.')
                registro = self.registro(alumno)
                self.assertRegex(registro.justificante.name, NOMBRE_GUARDADO)
                self.assertTrue(registro.justificante.name.endswith(f'.{extension}'))
                self.assertEqual(self.guardado_en_disco(registro), contenido)
        self.assertEqual(len(self.archivos_de_justificantes()), 3)

    def test_adjuntar_no_toca_el_estado_el_autor_ni_la_bitacora(self):
        self.adjuntar(self.a_pdf, 'constancia.pdf', PDF)

        registro = self.registro(self.a_pdf)
        self.assertEqual(registro.estado, JUSTIFICADO)
        self.assertEqual(registro.registrado_por, self.capturista)   # no pasa a ser el docente
        self.assertFalse(BitacoraCambio.objects.exists())

    def test_la_extension_en_mayusculas_y_jpeg_se_aceptan(self):
        self.adjuntar(self.a_pdf, 'CONSTANCIA.PDF', PDF)
        self.adjuntar(self.a_jpg, 'foto.jpeg', JPG)

        self.assertTrue(self.registro(self.a_pdf).justificante.name.endswith('.pdf'))
        self.assertTrue(self.registro(self.a_jpg).justificante.name.endswith('.jpg'))

    def test_justo_5_mb_se_acepta(self):
        contenido = PDF + b'0' * (TAMANO_MAXIMO_BYTES - len(PDF))
        self.assertEqual(len(contenido), TAMANO_MAXIMO_BYTES)

        self.adjuntar(self.a_pdf, 'grande.pdf', contenido)

        self.assertTrue(self.registro(self.a_pdf).justificante)

    def test_se_rechaza_lo_que_no_es_pdf_jpg_o_png_sin_dejar_nada(self):
        casos = [
            ('virus.exe', b'MZ\x90\x00\x03', 'Solo se aceptan archivos PDF, JPG o PNG.'),
            ('pagina.html', b'<html><script>alert(1)</script></html>', 'Solo se aceptan'),
            ('imagen.svg', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', 'Solo se aceptan'),
            ('nota.txt', b'hola', 'Solo se aceptan'),
            ('sin_extension', PDF, 'Solo se aceptan'),
            ('falso.pdf', b'esto es texto, no un pdf', 'no corresponde a un PDF, JPG o PNG'),
            ('png_como_pdf.pdf', PNG, 'no coincide con su contenido'),
            ('pdf_como_png.png', PDF, 'no coincide con su contenido'),
            ('jpg_como_png.png', JPG, 'no coincide con su contenido'),
            ('vacio.pdf', b'', 'vacío'),
            ('enorme.pdf', PDF + b'0' * (TAMANO_MAXIMO_BYTES - len(PDF) + 1), 'más de 5 MB'),
        ]
        for nombre, contenido, mensaje in casos:
            with self.subTest(nombre):
                respuesta = self.adjuntar(self.a_pdf, nombre, contenido)

                self.assertEqual(respuesta.status_code, 200)    # vuelve al formulario
                self.assertContains(respuesta, mensaje)
                self.assertFalse(self.registro(self.a_pdf).justificante)
                self.assertEqual(self.archivos_de_justificantes(), [])

    def test_el_tipo_que_dice_el_cliente_no_cuenta(self):
        archivo = SimpleUploadedFile('falso.pdf', b'texto', content_type='application/pdf')

        respuesta = self.client.post(self.url('justificante', self.a_pdf), {'archivo': archivo})

        self.assertContains(respuesta, 'no corresponde a un PDF, JPG o PNG')

    def test_el_nombre_del_cliente_se_ignora(self):
        nombres = ['../../evil.pdf', 'Constancia médica niño.pdf', 'C:\\Windows\\sistema.pdf',
                   '..\\..\\otro.pdf', 'a' * 200 + '.pdf']
        for nombre in nombres:
            with self.subTest(nombre[:30]):
                self.vaciar_justificantes()
                Asistencia.objects.filter(pk=self.registro(self.a_pdf).pk).update(justificante=None)

                self.adjuntar(self.a_pdf, nombre, PDF)

                registro = self.registro(self.a_pdf)
                self.assertRegex(registro.justificante.name, NOMBRE_GUARDADO)
                self.assertEqual(len(self.archivos_de_justificantes()), 1)
                self.assertFalse((self.media_temporal.parent / 'evil.pdf').exists())
                self.assertFalse((self.media_temporal / 'evil.pdf').exists())

    def test_solo_un_registro_justificado_admite_justificante(self):
        for alumno, estado in ((self.b, 'Presente'), (self.c, 'Ausente')):
            with self.subTest(estado):
                respuesta = self.adjuntar(alumno, 'constancia.pdf', PDF, follow=True)

                self.assertContains(respuesta, 'Solo un registro justificado admite justificante')
                self.assertFalse(self.registro(alumno).justificante)
                self.assertEqual(self.archivos_de_justificantes(), [])

    def test_el_servicio_lanza_el_error_propio_y_no_un_error_de_base_de_datos(self):
        with self.assertRaises(RegistroNoJustificado):
            adjuntar_justificante(
                self.sesion.pk, self.b.pk, subir('constancia.pdf', PDF))
        self.assertEqual(self.archivos_de_justificantes(), [])

    def test_la_pantalla_de_un_registro_no_justificado_no_ofrece_el_formulario(self):
        respuesta = self.client.get(self.url('justificante', self.b))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Solo un registro <strong>justificado</strong>')
        self.assertNotContains(respuesta, 'type="file"')

    def test_la_pantalla_de_un_registro_justificado_ofrece_el_formulario(self):
        respuesta = self.client.get(self.url('justificante', self.a_pdf))

        self.assertContains(respuesta, 'type="file"')
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, 'PDF, JPG o PNG, de hasta 5 MB.')
        self.assertContains(respuesta, 'Adjuntar')

    def test_un_alumno_sin_registro_en_la_sesion_responde_404(self):
        sin_registro = inscribir_alumnos(self.grupo, 1, primera_matricula=7000000)[0]

        self.assertEqual(self.client.get(self.url('justificante', sin_registro)).status_code, 404)
        self.assertEqual(
            self.client.post(self.url('justificante', sin_registro),
                             {'archivo': subir('c.pdf', PDF)}).status_code, 404)


class ReemplazarYQuitarTests(JustificanteBase):

    def test_reemplazar_guarda_el_nuevo_y_borra_el_anterior(self):
        self.adjuntar(self.a_pdf, 'primero.pdf', PDF)
        anterior = self.registro(self.a_pdf).justificante.name

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.adjuntar(self.a_pdf, 'segundo.png', PNG, follow=True)

        self.assertContains(respuesta, 'Justificante reemplazado.')
        nuevo = self.registro(self.a_pdf).justificante.name
        self.assertNotEqual(nuevo, anterior)
        self.assertTrue(nuevo.endswith('.png'))
        self.assertEqual(self.archivos_de_justificantes(), [nuevo.split('/')[-1]])
        self.assertFalse((self.media_temporal / anterior).exists())

    def test_si_falla_la_base_al_reemplazar_el_anterior_queda_y_el_nuevo_no(self):
        self.adjuntar(self.a_pdf, 'primero.pdf', PDF)
        anterior = self.registro(self.a_pdf).justificante.name

        with mock.patch.object(Asistencia, 'save', side_effect=IntegrityError('falla simulada')):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(IntegrityError):
                    adjuntar_justificante(
                        self.sesion.pk, self.a_pdf.pk, subir('segundo.png', PNG))

        self.assertEqual(self.registro(self.a_pdf).justificante.name, anterior)
        self.assertEqual(self.archivos_de_justificantes(), [anterior.split('/')[-1]])
        self.assertEqual(self.guardado_en_disco(self.registro(self.a_pdf)), PDF)

    def test_si_una_transaccion_externa_se_deshace_el_archivo_anterior_no_se_pierde(self):
        """El archivo anterior se borra solo cuando la base confirma (on_commit):
        si todo se deshace después de adjuntar, la base vuelve a apuntar a él."""
        self.adjuntar(self.a_pdf, 'primero.pdf', PDF)
        anterior = self.registro(self.a_pdf).justificante.name

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    adjuntar_justificante(
                        self.sesion.pk, self.a_pdf.pk, subir('segundo.png', PNG))
                    raise RuntimeError('se deshace todo')

        self.assertEqual(self.registro(self.a_pdf).justificante.name, anterior)
        self.assertTrue((self.media_temporal / anterior).exists())
        self.assertEqual((self.media_temporal / anterior).read_bytes(), PDF)

    def test_la_confirmacion_de_quitar_no_quita_nada(self):
        self.adjuntar(self.a_pdf, 'constancia.pdf', PDF)

        respuesta = self.client.get(self.url('justificante_quitar', self.a_pdf))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Sí, quitar el justificante')
        self.assertTrue(self.registro(self.a_pdf).justificante)
        self.assertEqual(len(self.archivos_de_justificantes()), 1)

    def test_quitar_deja_null_y_borra_el_archivo(self):
        self.adjuntar(self.a_pdf, 'constancia.pdf', PDF)

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(self.url('justificante_quitar', self.a_pdf), follow=True)

        self.assertContains(respuesta, 'Justificante quitado.')
        valor = Asistencia.objects.filter(
            sesion=self.sesion, alumno=self.a_pdf).values_list('justificante', flat=True).get()
        self.assertIsNone(valor)                        # NULL, no una cadena vacía
        self.assertEqual(self.archivos_de_justificantes(), [])
        self.assertEqual(self.registro(self.a_pdf).estado, JUSTIFICADO)   # sigue justificado

    def test_quitar_sin_justificante_responde_404(self):
        self.assertEqual(
            self.client.get(self.url('justificante_quitar', self.a_pdf)).status_code, 404)
        self.assertEqual(
            self.client.post(self.url('justificante_quitar', self.a_pdf)).status_code, 404)

    def test_el_flujo_completo_bloqueo_quitar_y_luego_cambiar_el_estado(self):
        self.adjuntar(self.a_pdf, 'constancia.pdf', PDF)
        url_pase = reverse('pase_de_lista', args=[self.sesion.pk])
        estados = {a.pk: self.registro(a).estado for a in self.alumnos}
        cambio = {**estados, self.a_pdf.pk: AUSENTE}

        # 1. Con justificante, el cambio se bloquea con un mensaje (no hay error 500).
        respuesta = self.client.post(url_pase, datos_del_pase('correccion', cambio), follow=True)
        self.assertContains(respuesta, 'tiene un justificante adjunto')
        self.assertEqual(self.registro(self.a_pdf).estado, JUSTIFICADO)
        self.assertFalse(BitacoraCambio.objects.exists())

        # 2. Se quita el justificante...
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('justificante_quitar', self.a_pdf))

        # 3. ...y ahora el cambio funciona y queda en la bitácora.
        self.client.post(url_pase, datos_del_pase('correccion', cambio))
        self.assertEqual(self.registro(self.a_pdf).estado, AUSENTE)
        cambio_en_bitacora = BitacoraCambio.objects.get()
        self.assertEqual((cambio_en_bitacora.valor_anterior, cambio_en_bitacora.valor_nuevo),
                         (JUSTIFICADO, AUSENTE))
        self.assertEqual(cambio_en_bitacora.usuario, self.docente)


class DescargaDelJustificanteTests(JustificanteBase):

    def descargar(self, alumno):
        return self.client.get(self.url('justificante_archivo', alumno))

    def test_el_dueno_descarga_cada_tipo_con_las_cabeceras_esperadas(self):
        casos = [(self.a_pdf, 'c.pdf', PDF, 'application/pdf', 'pdf'),
                 (self.a_jpg, 'f.jpg', JPG, 'image/jpeg', 'jpg'),
                 (self.a_png, 'p.png', PNG, 'image/png', 'png')]
        for alumno, nombre, contenido, tipo, extension in casos:
            with self.subTest(extension):
                self.adjuntar(alumno, nombre, contenido)

                respuesta = self.descargar(alumno)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta['Content-Type'], tipo)
                self.assertEqual(
                    respuesta['Content-Disposition'],
                    f'attachment; filename="justificante_{alumno.matricula}_2026-10-19.{extension}"')
                self.assertEqual(respuesta['Cache-Control'], 'private, no-store')
                self.assertEqual(b''.join(respuesta.streaming_content), contenido)

    def test_un_grupo_ajeno_recibe_404_y_el_administrador_403_y_el_anonimo_va_al_login(self):
        self.adjuntar(self.a_pdf, 'c.pdf', PDF)
        url = self.url('justificante_archivo', self.a_pdf)
        crear_docente('intruso@asistencia.test', 'intruso')
        crear_administrador()

        self.client.logout()
        self.assertRedirects(
            self.client.get(url), f"{reverse('login')}?next={url}", fetch_redirect_response=False)
        self.client.login(username='intruso@asistencia.test', password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.login(username='admin@asistencia.test', password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_sin_registro_o_sin_archivo_responde_404(self):
        sin_registro = inscribir_alumnos(self.grupo, 1, primera_matricula=7000000)[0]

        self.assertEqual(self.descargar(self.a_pdf).status_code, 404)        # justificado, sin archivo
        self.assertEqual(self.descargar(self.b).status_code, 404)            # presente
        self.assertEqual(self.descargar(sin_registro).status_code, 404)      # sin registro

    def test_si_el_archivo_ya_no_esta_en_el_disco_responde_404(self):
        self.adjuntar(self.a_pdf, 'c.pdf', PDF)
        (self.media_temporal / self.registro(self.a_pdf).justificante.name).unlink()

        self.assertEqual(self.descargar(self.a_pdf).status_code, 404)

    def test_un_archivo_alterado_en_el_disco_no_se_entrega(self):
        self.adjuntar(self.a_pdf, 'c.pdf', PDF)
        (self.media_temporal / self.registro(self.a_pdf).justificante.name).write_bytes(
            b'<html><script>alert(1)</script></html>')

        self.assertEqual(self.descargar(self.a_pdf).status_code, 404)

    def test_no_hay_url_publica_del_archivo(self):
        self.adjuntar(self.a_pdf, 'c.pdf', PDF)
        nombre = self.registro(self.a_pdf).justificante.name       # justificantes/<hex>.pdf

        for ruta in (f'/media/{nombre}', f'/{nombre}', f'/static/{nombre}'):
            with self.subTest(ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)
        # Ni siquiera sin sesión iniciada.
        self.client.logout()
        self.assertEqual(self.client.get(f'/media/{nombre}').status_code, 404)

    def test_el_nombre_de_descarga_no_trae_el_del_cliente(self):
        self.adjuntar(self.a_pdf, '../../etc/passwd.pdf', PDF)

        disposicion = self.descargar(self.a_pdf)['Content-Disposition']

        self.assertNotIn('passwd', disposicion)
        self.assertNotIn('..', disposicion)


class PantallaDeCorreccionTests(JustificanteBase):

    def get(self):
        return self.client.get(reverse('pase_de_lista', args=[self.sesion.pk]))

    def test_los_enlaces_salen_solo_en_las_filas_justificadas(self):
        self.adjuntar(self.a_jpg, 'foto.jpg', JPG)

        respuesta = self.get()

        # a_pdf y a_png: justificados sin archivo -> «Adjuntar».
        for alumno in (self.a_pdf, self.a_png):
            self.assertContains(respuesta, self.url('justificante', alumno))
        # a_jpg: con archivo -> Ver, Reemplazar y Quitar.
        self.assertContains(respuesta, 'Justificante adjunto')
        self.assertContains(respuesta, self.url('justificante_archivo', self.a_jpg))
        self.assertContains(respuesta, self.url('justificante_quitar', self.a_jpg))
        # b (presente) y c (ausente): sin ningún enlace de justificante.
        for alumno in (self.b, self.c):
            self.assertNotContains(respuesta, self.url('justificante', alumno))
        self.assertContains(respuesta, 'Adjuntar justificante', count=2)

    def test_la_primera_captura_no_ofrece_justificantes(self):
        nueva = crear_sesion(self.grupo, fecha=date(2026, 10, 18))

        respuesta = self.client.get(reverse('pase_de_lista', args=[nueva.pk]))

        self.assertEqual(respuesta.context['modo'], 'captura')
        self.assertNotContains(respuesta, 'justificante')

    def test_la_pantalla_no_hace_una_consulta_por_justificante(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.get()
            return len(capturadas)

        sin_archivos = consultas()
        for i, alumno in enumerate((self.a_pdf, self.a_jpg, self.a_png)):
            Asistencia.objects.filter(sesion=self.sesion, alumno=alumno).update(
                justificante=f'justificantes/{i:032x}.pdf')
        con_archivos = consultas()

        self.assertEqual(sin_archivos, con_archivos)


class EliminarGrupoConJustificantesTests(JustificanteBase):

    def test_la_confirmacion_cuenta_los_justificantes(self):
        self.adjuntar(self.a_pdf, 'a.pdf', PDF)
        self.adjuntar(self.a_jpg, 'b.jpg', JPG)

        respuesta = self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertEqual(respuesta.context['impacto']['justificantes'], 2)
        self.assertContains(respuesta, '2 justificantes adjuntos')

    def test_la_confirmacion_usa_el_singular_y_el_cero(self):
        self.assertContains(
            self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk])),
            '0 justificantes adjuntos')
        self.adjuntar(self.a_pdf, 'a.pdf', PDF)

        respuesta = self.client.get(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertContains(respuesta, '1 justificante adjunto')
        self.assertNotContains(respuesta, '1 justificantes')

    def test_eliminar_el_grupo_borra_sus_archivos_pero_no_los_de_otro_grupo(self):
        self.adjuntar(self.a_pdf, 'a.pdf', PDF)
        self.adjuntar(self.a_jpg, 'b.jpg', JPG)
        # Otro grupo del mismo docente, con su propio justificante.
        otro = crear_grupo(self.docente, clave='OTRO-1')
        alumno = inscribir_alumnos(otro, 1, primera_matricula=7100000)[0]
        sesion = crear_sesion(otro, estado=Sesion.Estado.REALIZADA)
        Asistencia.objects.create(
            sesion=sesion, alumno=alumno, estado=JUSTIFICADO, registrado_por=self.docente)
        self.client.post(
            reverse('justificante', args=[sesion.pk, alumno.pk]), {'archivo': subir('c.pdf', PDF)})
        self.assertEqual(len(self.archivos_de_justificantes()), 3)

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertRedirects(respuesta, reverse('grupos'))
        self.assertFalse(Asistencia.objects.filter(sesion=self.sesion).exists())
        restante = Asistencia.objects.get(sesion=sesion).justificante.name
        self.assertEqual(self.archivos_de_justificantes(), [restante.split('/')[-1]])

    def test_si_el_borrado_del_archivo_falla_el_grupo_igual_se_elimino(self):
        self.adjuntar(self.a_pdf, 'a.pdf', PDF)
        nombre = self.registro(self.a_pdf).justificante.name
        (self.media_temporal / nombre).unlink()    # ya no está: no debe romper nada

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('grupo_eliminar', args=[self.grupo.pk]))

        self.assertRedirects(respuesta, reverse('grupos'))


class PermisosDeLasRutasDeJustificanteTests(JustificanteBase):

    def rutas(self):
        return [self.url(n, self.a_pdf)
                for n in ('justificante', 'justificante_archivo', 'justificante_quitar')]

    def preparar(self):
        self.adjuntar(self.a_pdf, 'a.pdf', PDF)      # para que existan archivo y quitar

    def test_un_docente_ajeno_recibe_404_en_cada_ruta_y_no_cambia_nada(self):
        self.preparar()
        antes = self.registro(self.a_pdf).justificante.name
        crear_docente('intruso@asistencia.test', 'intruso')
        self.client.login(username='intruso@asistencia.test', password=PASSWORD)

        for url in self.rutas():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(
                    self.client.post(url, {'archivo': subir('x.pdf', PDF)}).status_code, 404)
        self.assertEqual(self.registro(self.a_pdf).justificante.name, antes)
        self.assertEqual(len(self.archivos_de_justificantes()), 1)

    def test_el_administrador_recibe_403_en_cada_ruta(self):
        self.preparar()
        crear_administrador()
        self.client.login(username='admin@asistencia.test', password=PASSWORD)

        for url in self.rutas():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_sin_sesion_se_redirige_al_login_en_cada_ruta(self):
        self.preparar()
        self.client.logout()

        for url in self.rutas():
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url), f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False)

    def test_el_dueno_entra_a_la_pantalla_y_a_la_descarga(self):
        self.preparar()

        for nombre in ('justificante', 'justificante_archivo', 'justificante_quitar'):
            with self.subTest(nombre):
                self.assertEqual(self.client.get(self.url(nombre, self.a_pdf)).status_code, 200)
