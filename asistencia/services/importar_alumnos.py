"""Carga de la lista de alumnos de un grupo desde un CSV (RF-04).

Formato: encabezado `matricula,nombre,correo` (el correo es opcional),
separado por comas y guardado en UTF-8. Los errores se informan por fila y no
abortan el resto del archivo.
"""

import csv
import io
import unicodedata
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from ..models import Alumno
from .inscripciones import inscribir_alumno

TAMANO_MAXIMO_BYTES = 1024 * 1024
MAX_FILAS = 500

COLUMNAS_OBLIGATORIAS = ('matricula', 'nombre')

LONGITUD_MATRICULA = Alumno._meta.get_field('matricula').max_length
LONGITUD_NOMBRE = Alumno._meta.get_field('nombre').max_length
LONGITUD_CORREO = Alumno._meta.get_field('correo').max_length


class ErrorDeArchivo(Exception):
    """El archivo completo no se puede leer; no se importa nada."""


@dataclass
class ErrorDeFila:
    linea: int
    matricula: str
    motivo: str


@dataclass
class ResultadoImportacion:
    filas: int = 0            # filas con datos
    alumnos_nuevos: int = 0   # alumnos que no estaban en el padrón
    inscritos: int = 0        # inscripciones nuevas en el grupo
    ya_inscritos: int = 0     # alumnos que ya estaban en el grupo
    errores: list[ErrorDeFila] = field(default_factory=list)


def importar_alumnos(grupo, archivo):
    """Importa el CSV `archivo` (un archivo abierto en binario) al grupo."""
    lector = _abrir(archivo)
    columnas = _columnas(lector)

    resultado = ResultadoImportacion()
    vistas = set()

    with transaction.atomic():
        try:
            for fila in lector:
                valores = _valores(fila, columnas)
                if not any(valores.values()):
                    continue  # fila vacía
                resultado.filas += 1
                if resultado.filas > MAX_FILAS:
                    raise ErrorDeArchivo(
                        f'El archivo tiene más de {MAX_FILAS} filas. '
                        'Divide la lista en varios archivos.'
                    )

                motivo = _validar(valores)
                if motivo is None and valores['matricula'] in vistas:
                    motivo = 'Matrícula repetida en el archivo; se ignoró.'
                if motivo is not None:
                    resultado.errores.append(
                        ErrorDeFila(lector.line_num, valores['matricula'], motivo))
                    continue

                vistas.add(valores['matricula'])
                inscrito = inscribir_alumno(
                    grupo, valores['matricula'], valores['nombre'], valores['correo'])
                resultado.alumnos_nuevos += inscrito.alumno_nuevo
                if inscrito.inscripcion_nueva:
                    resultado.inscritos += 1
                else:
                    resultado.ya_inscritos += 1
        except csv.Error:
            raise ErrorDeArchivo('El archivo no tiene un formato CSV válido.')

    return resultado


def _abrir(archivo):
    contenido = archivo.read()
    try:
        texto = contenido.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ErrorDeArchivo(
            'El archivo no está en UTF-8. En Excel usa «Guardar como» y elige '
            '«CSV UTF-8 (delimitado por comas)».'
        )
    return csv.DictReader(io.StringIO(texto, newline=''))


def _normalizar(nombre):
    """'Matrícula ' -> 'matricula', para aceptar acentos y mayúsculas."""
    sin_acentos = unicodedata.normalize('NFKD', nombre or '')
    sin_acentos = ''.join(c for c in sin_acentos if not unicodedata.combining(c))
    return sin_acentos.strip().casefold()


def _columnas(lector):
    """Devuelve {nombre normalizado: nombre original} o lanza ErrorDeArchivo."""
    try:
        encabezado = lector.fieldnames
    except csv.Error:
        raise ErrorDeArchivo('El archivo no tiene un formato CSV válido.')
    if not encabezado:
        raise ErrorDeArchivo('El archivo está vacío.')

    columnas = {_normalizar(nombre): nombre for nombre in encabezado}
    faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in columnas]
    if faltantes:
        pista = ''
        if any(';' in nombre for nombre in encabezado):
            pista = ' Parece que el archivo usa punto y coma; guárdalo separado por comas.'
        raise ErrorDeArchivo(
            f"Faltan las columnas: {', '.join(faltantes)}. El encabezado debe "
            f'ser matricula,nombre,correo (el correo es opcional).{pista}'
        )
    return columnas


def _valores(fila, columnas):
    def dato(clave):
        original = columnas.get(clave)
        return (fila.get(original) or '').strip() if original else ''

    return {
        'matricula': dato('matricula'),
        'nombre': ' '.join(dato('nombre').split()),
        'correo': dato('correo'),
    }


def _validar(valores):
    """Devuelve el motivo del rechazo de la fila, o None si es válida."""
    matricula, nombre, correo = valores['matricula'], valores['nombre'], valores['correo']
    if not matricula:
        return 'Falta la matrícula.'
    if len(matricula) > LONGITUD_MATRICULA:
        return f'La matrícula excede {LONGITUD_MATRICULA} caracteres.'
    if not nombre:
        return 'Falta el nombre.'
    if len(nombre) > LONGITUD_NOMBRE:
        return f'El nombre excede {LONGITUD_NOMBRE} caracteres.'
    if correo:
        try:
            validate_email(correo)
        except ValidationError:
            return 'El correo no es válido.'
        if len(correo) > LONGITUD_CORREO:
            return f'El correo excede {LONGITUD_CORREO} caracteres.'
    return None
