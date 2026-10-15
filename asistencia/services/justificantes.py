"""Justificantes de asistencia (RF-12).

Un registro «justificado» admite un archivo (PDF, JPG o PNG de hasta 5 MB) como
justificante. Es un dato sensible y viene de un usuario, así que:
- Se valida la extensión Y la firma real del archivo, y deben coincidir. No se
  confía en el Content-Type que manda el cliente.
- Se guarda con un nombre aleatorio (`<uuid>.<ext>`), nunca con el del cliente.
- Solo se entrega por una vista con permisos (nunca por una URL pública).

Adjuntar o quitar un justificante no es una corrección del estado: se guarda
con `update_fields=['justificante']`, así que no toca `estado` ni
`registrado_por` y el disparador de la bitácora no interviene.
"""

import logging
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Asistencia

logger = logging.getLogger(__name__)

TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024

# Primeros bytes de cada tipo permitido.
FIRMAS = {
    'pdf': b'%PDF-',
    'jpg': b'\xff\xd8\xff',
    'png': b'\x89PNG\r\n\x1a\n',
}
TIPOS_DE_CONTENIDO = {
    'pdf': 'application/pdf',
    'jpg': 'image/jpeg',
    'png': 'image/png',
}
# Lo que dice la extensión del nombre -> el tipo que debe tener el contenido.
EXTENSIONES = {'pdf': 'pdf', 'jpg': 'jpg', 'jpeg': 'jpg', 'png': 'png'}
BYTES_DE_CABECERA = max(len(firma) for firma in FIRMAS.values())


class ErrorDeJustificante(Exception):
    """Base de los errores de este módulo; el mensaje se puede mostrar tal cual."""


class ArchivoNoValido(ErrorDeJustificante):
    """El archivo no cumple el tipo, el contenido o el tamaño permitidos."""


class RegistroNoJustificado(ErrorDeJustificante):
    """Solo un registro con estado «justificado» admite justificante."""


class SinJustificante(ErrorDeJustificante):
    """El registro no tiene un justificante adjunto."""


def detectar_tipo(cabecera):
    """'pdf', 'jpg' o 'png' según los primeros bytes, o None si no es ninguno."""
    for tipo, firma in FIRMAS.items():
        if cabecera.startswith(firma):
            return tipo
    return None


def validar_archivo(nombre, archivo):
    """Devuelve el tipo real del archivo ('pdf', 'jpg' o 'png') o lanza
    ArchivoNoValido. `archivo` es un archivo subido (tiene size, seek y read)."""
    if archivo.size == 0:
        raise ArchivoNoValido('El archivo está vacío.')
    if archivo.size > TAMANO_MAXIMO_BYTES:
        raise ArchivoNoValido('El archivo pesa más de 5 MB.')

    extension = nombre.strip().rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    if extension not in EXTENSIONES:
        raise ArchivoNoValido('Solo se aceptan archivos PDF, JPG o PNG.')

    archivo.seek(0)
    cabecera = archivo.read(BYTES_DE_CABECERA)
    archivo.seek(0)
    tipo = detectar_tipo(cabecera)
    if tipo is None:
        raise ArchivoNoValido('El contenido del archivo no corresponde a un PDF, JPG o PNG.')
    if tipo != EXTENSIONES[extension]:
        raise ArchivoNoValido('La extensión del archivo no coincide con su contenido.')
    return tipo


def _almacenamiento():
    return Asistencia._meta.get_field('justificante').storage


def borrar_archivos(nombres):
    """Borra archivos del almacenamiento. Nunca lanza: un archivo que ya no
    existe no debe romper la operación que lo originó."""
    almacenamiento = _almacenamiento()
    for nombre in nombres:
        try:
            almacenamiento.delete(nombre)
        except OSError:
            logger.warning('No se pudo borrar el justificante %s', nombre, exc_info=True)


def nombres_de_justificantes(grupo):
    """Nombres de los archivos de justificante de todos los registros del grupo."""
    nombres = (
        Asistencia.objects.filter(sesion__grupo=grupo, justificante__isnull=False)
        .exclude(justificante='')
        .values_list('justificante', flat=True)
    )
    return list(nombres)


def _registro_bloqueado(sesion_id, alumno_id):
    """El registro del alumno en la sesión, con su fila bloqueada hasta que
    termine la transacción."""
    try:
        return Asistencia.objects.select_for_update().get(
            sesion_id=sesion_id, alumno_id=alumno_id)
    except Asistencia.DoesNotExist:
        raise ErrorDeJustificante('El registro ya no existe.')


def adjuntar_justificante(sesion_id, alumno_id, archivo):
    """Adjunta (o reemplaza) el justificante del registro. Devuelve el registro.

    Escribe el archivo nuevo, actualiza la base y, si algo falla, borra el
    archivo nuevo. El archivo anterior se borra solo cuando la base ya confirmó.
    """
    tipo = validar_archivo(archivo.name, archivo)
    nombre = f'{uuid.uuid4().hex}.{tipo}'
    guardado = None
    try:
        with transaction.atomic():
            registro = _registro_bloqueado(sesion_id, alumno_id)
            if registro.estado != Asistencia.Estado.JUSTIFICADO:
                raise RegistroNoJustificado(
                    'Solo un registro justificado admite justificante. '
                    'Cambia primero el estado en la sesión.')

            anterior = registro.justificante.name if registro.justificante else None
            # upload_to del modelo ('justificantes/') pone la carpeta; aquí solo el nombre.
            registro.justificante.save(nombre, archivo, save=False)
            guardado = registro.justificante.name
            try:
                registro.clean()
            except ValidationError as error:
                raise RegistroNoJustificado(' '.join(error.messages))
            registro.save(update_fields=['justificante'])

            if anterior:
                transaction.on_commit(lambda: borrar_archivos([anterior]))
    except BaseException:
        if guardado:
            borrar_archivos([guardado])
        raise
    return registro


def quitar_justificante(sesion_id, alumno_id):
    """Deja el registro sin justificante (NULL) y borra el archivo, una vez
    confirmada la base de datos."""
    with transaction.atomic():
        registro = _registro_bloqueado(sesion_id, alumno_id)
        if not registro.justificante:
            raise SinJustificante('Este registro no tiene justificante.')
        anterior = registro.justificante.name
        # update() guarda NULL; save() de un FileField vacío guardaría ''.
        Asistencia.objects.filter(pk=registro.pk).update(justificante=None)
        transaction.on_commit(lambda: borrar_archivos([anterior]))


def abrir_justificante(registro):
    """(archivo abierto, tipo 'pdf'/'jpg'/'png', tipo de contenido) del
    justificante, según la firma del archivo. Lanza SinJustificante si no hay
    archivo o ya no se puede leer."""
    if not registro.justificante:
        raise SinJustificante('Este registro no tiene justificante.')
    try:
        archivo = registro.justificante.open('rb')
    except (FileNotFoundError, OSError):
        raise SinJustificante('El archivo del justificante ya no está disponible.')
    tipo = detectar_tipo(archivo.read(BYTES_DE_CABECERA))
    archivo.seek(0)
    if tipo is None:
        archivo.close()
        raise SinJustificante('El archivo del justificante no es válido.')
    return archivo, tipo, TIPOS_DE_CONTENIDO[tipo]
