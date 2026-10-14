"""Pruebas de la carga de alumnos desde CSV (RF-04)."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from asistencia.models import Alumno, Inscripcion
from asistencia.services.importar_alumnos import (
    MAX_FILAS, TAMANO_MAXIMO_BYTES, ErrorDeArchivo, importar_alumnos,
)

from .utils import PASSWORD, crear_docente, crear_grupo


def csv_en_memoria(texto, codificacion='utf-8'):
    return io.BytesIO(texto.encode(codificacion))


class ImportarAlumnosServicioTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)

    def test_importa_alumnos_y_los_inscribe(self):
        archivo = csv_en_memoria(
            'matricula,nombre,correo\n'
            '1200001,Ana García,ana@ejemplo.mx\n'
            '1200002,Luis Martínez,\n'
        )

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual((resultado.filas, resultado.alumnos_nuevos, resultado.inscritos), (2, 2, 2))
        self.assertEqual(resultado.errores, [])
        self.assertEqual(self.grupo.inscripciones.count(), 2)
        ana = Alumno.objects.get(matricula='1200001')
        self.assertEqual((ana.nombre, ana.correo), ('Ana García', 'ana@ejemplo.mx'))
        self.assertIsNone(Alumno.objects.get(matricula='1200002').correo)

    def test_lee_utf8_con_bom_como_lo_guarda_excel(self):
        archivo = csv_en_memoria('matricula,nombre\n1200001,José Peña\n', 'utf-8-sig')

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual(resultado.inscritos, 1)
        self.assertEqual(Alumno.objects.get().nombre, 'José Peña')

    def test_el_correo_es_opcional_y_el_encabezado_tolera_acentos_y_mayusculas(self):
        archivo = csv_en_memoria('Matrícula,NOMBRE\n1200001,Ana García\n')

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual(resultado.inscritos, 1)

    def test_reutiliza_al_alumno_que_ya_existe_en_otro_grupo(self):
        otro_grupo = crear_grupo(self.docente, clave='BD-201')
        importar_alumnos(otro_grupo, csv_en_memoria('matricula,nombre\n1200001,Ana García\n'))

        # En el segundo archivo el nombre viene distinto: se conserva el del padrón.
        resultado = importar_alumnos(
            self.grupo, csv_en_memoria('matricula,nombre\n1200001,Ana G. López\n'))

        self.assertEqual((resultado.alumnos_nuevos, resultado.inscritos), (0, 1))
        self.assertEqual(Alumno.objects.count(), 1)
        self.assertEqual(Alumno.objects.get().nombre, 'Ana García')
        self.assertEqual(Inscripcion.objects.count(), 2)

    def test_repetir_la_importacion_no_duplica_nada(self):
        texto = 'matricula,nombre\n1200001,Ana García\n1200002,Luis Martínez\n'
        importar_alumnos(self.grupo, csv_en_memoria(texto))

        resultado = importar_alumnos(self.grupo, csv_en_memoria(texto))

        self.assertEqual((resultado.inscritos, resultado.ya_inscritos), (0, 2))
        self.assertEqual(Alumno.objects.count(), 2)
        self.assertEqual(Inscripcion.objects.count(), 2)

    def test_los_errores_por_fila_no_abortan_el_resto_del_archivo(self):
        archivo = csv_en_memoria(
            'matricula,nombre,correo\n'
            '1200001,Ana García,ana@ejemplo.mx\n'      # línea 2: válida
            ',Sin matrícula,\n'                          # línea 3
            '1200003,,\n'                                # línea 4
            '1200004,Mal correo,no-es-un-correo\n'       # línea 5
            f'{"9" * 16},Matrícula larga,\n'             # línea 6
            '1200006,Luis Martínez,\n'                   # línea 7: válida
        )

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual(resultado.inscritos, 2)
        self.assertEqual(
            [(e.linea, e.motivo) for e in resultado.errores],
            [
                (3, 'Falta la matrícula.'),
                (4, 'Falta el nombre.'),
                (5, 'El correo no es válido.'),
                (6, 'La matrícula excede 15 caracteres.'),
            ],
        )
        self.assertEqual(
            set(Alumno.objects.values_list('matricula', flat=True)), {'1200001', '1200006'})

    def test_una_matricula_repetida_en_el_archivo_se_informa(self):
        archivo = csv_en_memoria(
            'matricula,nombre\n1200001,Ana García\n1200001,Ana García\n')

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual(resultado.inscritos, 1)
        self.assertEqual([e.linea for e in resultado.errores], [3])
        self.assertIn('repetida', resultado.errores[0].motivo)

    def test_las_filas_vacias_se_ignoran(self):
        archivo = csv_en_memoria('matricula,nombre\n1200001,Ana García\n,\n\n,,\n')

        resultado = importar_alumnos(self.grupo, archivo)

        self.assertEqual((resultado.filas, resultado.errores), (1, []))

    def test_faltan_columnas_obligatorias(self):
        with self.assertRaisesRegex(ErrorDeArchivo, 'Faltan las columnas: nombre'):
            importar_alumnos(self.grupo, csv_en_memoria('matricula,correo\n1200001,a@b.mx\n'))
        self.assertFalse(Alumno.objects.exists())

    def test_un_archivo_con_punto_y_coma_da_una_pista(self):
        with self.assertRaisesRegex(ErrorDeArchivo, 'punto y coma'):
            importar_alumnos(self.grupo, csv_en_memoria('matricula;nombre\n1200001;Ana\n'))

    def test_un_archivo_que_no_es_utf8_se_rechaza(self):
        archivo = csv_en_memoria('matricula,nombre\n1200001,José\n', 'cp1252')

        with self.assertRaisesRegex(ErrorDeArchivo, 'UTF-8'):
            importar_alumnos(self.grupo, archivo)
        self.assertFalse(Alumno.objects.exists())

    def test_un_archivo_vacio_se_rechaza(self):
        with self.assertRaisesRegex(ErrorDeArchivo, 'vacío'):
            importar_alumnos(self.grupo, csv_en_memoria(''))

    def test_un_archivo_con_demasiadas_filas_no_importa_nada(self):
        filas = ''.join(f'{1200000 + i},Alumno {i}\n' for i in range(MAX_FILAS + 1))

        with self.assertRaisesRegex(ErrorDeArchivo, 'más de'):
            importar_alumnos(self.grupo, csv_en_memoria('matricula,nombre\n' + filas))
        self.assertFalse(Alumno.objects.exists())
        self.assertFalse(Inscripcion.objects.exists())


class ImportarAlumnosVistaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.docente = crear_docente()
        cls.grupo = crear_grupo(cls.docente)
        cls.url = reverse('alumnos_importar', args=[cls.grupo.pk])

    def setUp(self):
        self.client.login(username='docente@asistencia.test', password=PASSWORD)

    def subir(self, nombre, contenido, **extra):
        archivo = SimpleUploadedFile(nombre, contenido, content_type='text/csv')
        return self.client.post(self.url, {'archivo': archivo}, **extra)

    def test_subir_un_csv_inscribe_a_los_alumnos_y_muestra_el_resumen(self):
        respuesta = self.subir(
            'lista.csv',
            'matricula,nombre\n1200001,Ana García\n,Sin matrícula\n'.encode('utf-8'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['resultado'].inscritos, 1)
        self.assertContains(respuesta, 'Falta la matrícula.')
        self.assertEqual(self.grupo.inscripciones.count(), 1)

    def test_el_detalle_ofrece_la_carga_de_la_lista(self):
        respuesta = self.client.get(reverse('grupo_detalle', args=[self.grupo.pk]))

        self.assertContains(respuesta, self.url)

    def test_un_archivo_sin_extension_csv_se_rechaza(self):
        respuesta = self.subir('lista.xlsx', b'matricula,nombre\n1200001,Ana\n')

        self.assertContains(respuesta, 'extensión .csv')
        self.assertFalse(Alumno.objects.exists())

    def test_un_archivo_demasiado_grande_se_rechaza(self):
        contenido = b'matricula,nombre\n' + b'x' * (TAMANO_MAXIMO_BYTES + 1)

        respuesta = self.subir('lista.csv', contenido)

        self.assertContains(respuesta, 'pesa más de 1 MB')
        self.assertFalse(Alumno.objects.exists())

    def test_un_archivo_con_columnas_faltantes_muestra_el_error_en_el_formulario(self):
        respuesta = self.subir('lista.csv', b'nombre\nAna\n')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Faltan las columnas: matricula')

    def test_enviar_sin_archivo_muestra_error(self):
        respuesta = self.client.post(self.url, {})

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Alumno.objects.exists())
